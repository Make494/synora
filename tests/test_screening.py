import pytest

from services.screening_service import (
    ScreeningValidationError,
    interpret_score,
    score_answers,
)


def test_forward_scoring_for_questions_one_to_nine():
    answers = ["A", "B", "C", "D", "E", "A", "B", "C", "D", "E"]
    assert score_answers(20, answers) == 5


def test_reverse_scoring_for_question_ten():
    base = ["A"] * 9
    assert score_answers(20, base + ["A"]) == 1
    assert score_answers(20, base + ["B"]) == 1
    assert score_answers(20, base + ["C"]) == 1
    assert score_answers(20, base + ["D"]) == 0
    assert score_answers(20, base + ["E"]) == 0


def test_minimum_score_is_zero():
    assert score_answers(18, ["A"] * 9 + ["E"]) == 0


def test_maximum_score_is_ten():
    assert score_answers(24, ["E"] * 9 + ["A"]) == 10


def test_threshold_starts_at_three():
    assert interpret_score(2)[0] is False
    assert interpret_score(3)[0] is True


@pytest.mark.parametrize(
    "answers",
    [
        ["A"] * 9,
        ["A"] * 9 + ["F"],
        ["A"] * 9 + [1],
        "A" * 10,
    ],
)
def test_invalid_or_missing_answers_are_rejected(answers):
    with pytest.raises(ScreeningValidationError):
        score_answers(20, answers)


@pytest.mark.parametrize("age", [17, 25, True, "20", None])
def test_invalid_age_is_rejected(age):
    with pytest.raises(ScreeningValidationError):
        score_answers(age, ["A"] * 9 + ["E"])
