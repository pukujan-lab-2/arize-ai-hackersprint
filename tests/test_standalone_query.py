"""A follow-up is searched as a standalone query, not as its words with the history stuck on."""

from app import agents, llm

PRIOR = ("So do i need a license or not", "The authorities do not say whether a license is required to carry a gun in Colorado")


def test_the_model_rewrite_is_the_query(monkeypatch):
    monkeypatch.setattr(llm, "complete", lambda *a, **k: ("Colorado gun license requirement to own or carry a firearm\n", "inferhub/x"))
    assert agents.standalone_query("I meant a gun license", PRIOR) == "Colorado gun license requirement to own or carry a firearm"


def test_the_prompt_carries_the_earlier_bottom_line(monkeypatch):
    seen = {}

    def fake(system, prompt, max_tokens, **k):
        seen["prompt"] = prompt
        return "Colorado gun license", "inferhub/x"

    monkeypatch.setattr(llm, "complete", fake)
    agents.standalone_query("I meant a gun license", PRIOR)
    assert "carry a gun" in seen["prompt"] and "I meant a gun license" in seen["prompt"]


def test_without_a_model_the_old_query_is_used(monkeypatch):
    monkeypatch.setattr(llm, "complete", lambda *a, **k: ("", "template (offline)"))
    assert agents.standalone_query("I meant a gun license", PRIOR) == "I meant a gun license — in context of: So do i need a license or not"


def test_a_failing_model_does_not_break_the_run(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "complete", boom)
    assert agents.standalone_query("x y z", PRIOR).startswith("x y z — in context of")
