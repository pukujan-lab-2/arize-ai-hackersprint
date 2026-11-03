"""A citation belongs to the sentence it follows, even when the writer puts it after the full stop."""

from app import agents

LONG = "Generally no because Colorado requires a warrant before searching a car once probable cause exists"


def test_a_citation_after_the_full_stop_counts_for_that_sentence():
    text = f"**Short answer:** {LONG}, absent a recognized exception. [1][4]\n\nMore words follow here and are cited [2]."
    assert agents.uncited_claims(text) == []


def test_a_citation_before_the_full_stop_still_counts():
    assert agents.uncited_claims(f"{LONG} [1].") == []


def test_a_sentence_with_no_citation_is_still_flagged():
    text = f"{LONG}, absent a recognized exception. [1][4] This second sentence makes a claim with no source at all."
    flagged = agents.uncited_claims(text)
    assert len(flagged) == 1
    assert flagged[0].startswith("This second sentence")


def test_a_lone_citation_group_is_never_a_sentence_of_its_own():
    assert agents.split_sentences("One thing is true here for sure. [1][4] Another is true too. [2]") == [
        "One thing is true here for sure. [1][4]",
        "Another is true too. [2]",
    ]


def test_support_claims_take_the_whole_sentence_when_the_citation_follows_the_stop(monkeypatch):
    monkeypatch.setattr(agents, "_cited_span", lambda cite, sentence: ("chunk-1", "the cited passage"))
    cites = [{"ref": "[1]", "id": "case-1"}]
    claims, unchecked = agents.support_claims(f"{LONG}, absent a recognized exception. [1]", cites)
    assert unchecked == []
    assert len(claims) == 1
    assert claims[0]["text"].startswith("Generally no because")
    assert claims[0]["citation"] == "[1]"


def test_a_quoted_claim_checks_the_passage_not_just_the_quote():
    # Returning only the quoted words asked the checker whether six words entail the claim, which it
    # answered by abstaining, so every answer failed the support gate.
    passage = (
        "Under the automobile exception, an officer may search a vehicle without a warrant when "
        "there is probable cause to believe it contains evidence of a crime. The scope of the search "
        "is limited by the object of the search."
    )
    cite = {"ref": "[1]", "chunk_id": "c1", "passages": [{"chunk_id": "c1", "text": passage}]}
    sentence = 'The court held that "an officer may search a vehicle without a warrant" when cause exists [1].'
    chunk_id, cited = agents._cited_span(cite, sentence)
    assert chunk_id == "c1"
    assert len(cited) > len("an officer may search a vehicle without a warrant")
    assert "automobile exception" in cited


def test_a_claim_without_a_quote_still_checks_the_passage():
    passage = "Probable cause to search a car requires specific facts, not a hunch."
    cite = {"ref": "[2]", "chunk_id": "c2", "passages": [{"chunk_id": "c2", "text": passage}]}
    chunk_id, cited = agents._cited_span(cite, "A hunch is not enough to search a car [2].")
    assert (chunk_id, cited) == ("c2", passage)


def test_a_quotation_verbatim_in_its_passage_needs_no_model_check(monkeypatch):
    passage = 'Under the automobile exception, "an officer may search a vehicle without a warrant" when there is probable cause to believe it holds evidence.'
    cite = {"ref": "[1]", "chunk_id": "c1", "passages": [{"chunk_id": "c1", "text": passage}]}
    text = 'The court held that "an officer may search a vehicle without a warrant" in that situation [1].'

    def boom(*args, **kwargs):
        raise AssertionError("a verbatim quotation should not be sent to the checker")

    monkeypatch.setattr(agents.engine, "check", boom)
    support = agents._support(text, [cite])
    assert support["ran"] is True
    assert support["abstain"] is False
    assert support["verbatim_claims"] == 1
    assert support["claims"] == 0


def test_a_claim_that_is_not_a_quotation_still_goes_to_the_checker(monkeypatch):
    cite = {"ref": "[2]", "chunk_id": "c2", "passages": [{"chunk_id": "c2", "text": "Probable cause requires specific facts."}]}
    seen = {}

    def fake(claims):
        seen["claims"] = claims
        return {"abstain": False, "answer_confidence": 0.9}

    monkeypatch.setattr(agents.engine, "check", fake)
    support = agents._support("A hunch is not enough to search a car here [2].", [cite])
    assert support["verbatim_claims"] == 0
    assert seen["claims"] == [{"text": "A hunch is not enough to search a car here [2].", "cited_text": "Probable cause requires specific facts."}]


def test_a_quote_that_differs_only_by_curly_punctuation_is_still_verbatim():
    # The source prints vehicle’s with a curly apostrophe; the model wrote it straight. The words are the
    # same, so the claim is the evidence and must not be sent to the checker (stored run 224353-1b3398).
    passage = "Thus, “the police may conduct a warrantless search if the vehicle’s unavailability is a risk.” Meyer."
    cite = {"ref": "[1]", "chunk_id": "c1", "passages": [{"chunk_id": "c1", "text": passage}]}
    text = 'Thiret [1] - "the police may conduct a warrantless search if the vehicle\'s unavailability is a risk".'
    claims, _ = agents.support_claims(text, [cite])
    assert [c["verbatim"] for c in claims] == [True]


def _cites(*scores):
    return [{"title": f"Case {i}", "passage": "some text", "score": x} for i, x in enumerate(scores)]


def test_a_reranked_retrieval_with_low_scores_is_off_corpus():
    # 'I meant a gun license' retrieved driver's, liquor and contract licence cases; the reranker scored the best at -1.57.
    assert agents._coverage("I meant a gun license", _cites(-1.57, -3.96, -4.76), reranked=True) == "off_corpus"
    assert agents._coverage("Hello", _cites(0.06, 0.06, 0.05), reranked=True) == "off_corpus"


def test_a_reranked_retrieval_with_high_scores_is_on_point():
    assert agents._coverage("Where is it illegal to carry a firearm in Colorado?", _cites(5.26, 5.16, 4.01), reranked=True) == "on_point"


def test_without_a_rerank_stage_the_old_test_stands():
    assert agents._coverage("gun license", _cites(0.08, 0.08), reranked=False) == "on_point"


def test_the_no_authority_answer_is_not_a_failed_check():
    class _Run:
        def claim(self, *a, **k): pass
        def event(self, *a, **k): pass
        def release(self, *a, **k): pass

    out = agents.safeguard(_Run(), "q", {"citations": []}, {"text": agents.NO_AUTHORITY, "provider": "scope:no-authority"})
    assert out["pass"] is True and out["used"] == []
