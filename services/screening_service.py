from typing import Sequence, Tuple


VALID_ANSWERS = frozenset({"A", "B", "C", "D", "E"})
_FORWARD_SCORES = {"A": 0, "B": 0, "C": 1, "D": 1, "E": 1}
_REVERSE_SCORES = {"A": 1, "B": 1, "C": 1, "D": 0, "E": 0}


class ScreeningValidationError(ValueError):
    """Raised when screening input does not meet the questionnaire requirements."""


def score_answers(age_months: int, answers: Sequence[str]) -> int:
    if isinstance(age_months, bool) or not isinstance(age_months, int):
        raise ScreeningValidationError("Хүүхдийн насыг сараар бүхэл тоогоор оруулна уу.")
    if not 18 <= age_months <= 24:
        raise ScreeningValidationError("Энэхүү үнэлгээ 18–24 сартай хүүхдэд зориулагдсан.")
    if not isinstance(answers, (list, tuple)) or len(answers) != 10:
        raise ScreeningValidationError("Яг 10 асуултад хариулна уу.")
    if any(not isinstance(answer, str) or answer not in VALID_ANSWERS for answer in answers):
        raise ScreeningValidationError("Хариулт бүр A, B, C, D эсвэл E байна.")

    return sum(_FORWARD_SCORES[answer] for answer in answers[:9]) + _REVERSE_SCORES[
        answers[9]
    ]


def interpret_score(score: int) -> Tuple[bool, str, str]:
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 10:
        raise ValueError("Q-CHAT-10 оноо 0–10 бүхэл тоо байх ёстой.")
    if score <= 2:
        return (
            False,
            "Энэхүү асуулгын лавлагааны босго оноонд хүрээгүй байна.",
            "Энэ үр дүн нь аутизм байхгүйг батлахгүй. Хэрэв хүүхдийн хөгжилтэй холбоотой санаа зовж буй зүйл байвал мэргэжлийн эмчид хандаарай.",
        )
    return (
        True,
        "Энэхүү асуулгын лавлагааны босго оноонд хүрсэн байна.",
        "Хүүхдийн хөгжлийн талаар мэргэжлийн үнэлгээ хийлгэх шаардлагатай эсэхийг хүүхдийн эмч болон холбогдох мэргэжилтэнтэй зөвлөлдөхийг зөвлөж байна.",
    )
