"""Everyday words are searched together with the statute's own words (never instead of them)."""

from app import agents


def test_a_gun_licence_question_gains_the_statutory_words():
    q = "Is it legal to carry a gun without a license in Colorado?"
    assert agents.expand_query(q) == q + " (firearm, concealed handgun, permit)"


def test_a_gun_question_without_a_licence_does_not_gain_permit():
    assert agents.expand_query("Can I keep a pistol at home?") == "Can I keep a pistol at home? (firearm, concealed handgun)"


def test_other_questions_are_untouched():
    for q in ("When can police search a car without a warrant in Colorado?", "A license to practise law", "hello"):
        assert agents.expand_query(q) == q


def test_the_original_wording_is_kept_so_nothing_is_lost():
    q = "Do I need a gun license?"
    assert agents.expand_query(q).startswith(q)
