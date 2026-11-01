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
