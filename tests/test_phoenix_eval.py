"""The code evaluators for the `precedent-legal` experiments (#64): offline, no network, no model."""

from app.agents import NO_AUTHORITY
from tools import phoenix_cases as cases
from tools.phoenix_eval import evaluate, run_case

GUN = next(c for c in cases.DEV if c["id"] == "gun-carry-no-licence")
OFF = next(c for c in cases.DEV if c["id"] == "off-topic-greeting")
GOOD_SG = {"regex_pass": True, "support": {"ran": True, "abstain": False, "answer_confidence": 0.9}}


def _out(titles, answer="**Short answer:** x [1]", sg=GOOD_SG):
    return {"answer": answer, "citations": [{"ref": f"[{i + 1}]", "title": t, "passage": t} for i, t in enumerate(titles)], "safeguard": sg}


def test_the_3_nov_gun_licence_citations_fail():
    out = _out(["United States v. Watson, carrying a firearm in Indiana", "People v. Boulden, a valid driver's license", "Squire Restaurant liquor license"])
    scores = evaluate(GUN, out)
    assert scores["no_wrong_subject_citations"]["score"] == 0.0
    assert scores["on_topic_citations"]["score"] < 0.5 and scores["on_topic_citations"]["label"] == "fail"


def test_on_topic_citations_pass():
    out = _out(["Trinen v. Denver, weapons ordinances", "Robertson v. Denver, a license to carry a concealed deadly weapon"])
    scores = evaluate(GUN, out)
    assert all(r["score"] == 1.0 for r in scores.values())


def test_an_abstaining_support_check_fails_the_case():
    out = _out(["Trinen v. Denver, a firearm case"], sg={"regex_pass": True, "support": {"ran": True, "abstain": True, "answer_confidence": 0.01}})
    assert evaluate(GUN, out)["support_check"]["score"] == 0.0


def test_off_topic_must_be_refused():
    assert evaluate(OFF, {"answer": NO_AUTHORITY, "citations": []})["refuses_off_topic"]["score"] == 1.0
    assert evaluate(OFF, _out(["Some case"]))["refuses_off_topic"]["score"] == 0.0


def test_a_refusal_of_an_on_topic_question_fails():
    assert evaluate(GUN, {"answer": NO_AUTHORITY, "citations": []})["answers_on_topic"]["score"] == 0.0


def test_a_conversation_is_asked_in_order_and_the_last_answer_is_prev():
    asked = []

    def fake(question, prev):
        asked.append((question, (prev or {}).get("tag")))
        return {"answer": "a", "citations": [], "tag": question}

    case = next(c for c in cases.DEV if c["id"] == "gun-followup-chain-i-meant")
    run_case(case, fake)
    assert [q for q, _ in asked] == case["history"] + [case["question"]]
    assert asked[0][1] is None and asked[-1][1] == case["history"][-1]


def test_dev_and_holdout_do_not_share_questions():
    dev = {c["question"].lower() for c in cases.DEV}
    assert not dev & {c["question"].lower() for c in cases.HOLDOUT}
    assert len({c["id"] for c in cases.DEV + cases.HOLDOUT}) == len(cases.DEV + cases.HOLDOUT)


def test_an_on_subject_authority_that_mentions_a_wrong_word_in_passing_is_not_wrong_subject():
    out = _out(["Godfrey v. County, a firearm statute; the opinion also mentions a theater"])
    assert evaluate(GUN, out)["no_wrong_subject_citations"]["score"] == 1.0
