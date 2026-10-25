import os


def save_screening(*, age_months, answers, score, consent):
    """Save the minimum screening data only when storage is enabled and consented."""
    if consent is not True:
        return False
    if os.environ.get("FIREBASE_ENABLED", "false").lower() != "true":
        return False

    try:
        import firebase_admin
        from firebase_admin import firestore
    except ImportError as exc:
        raise RuntimeError(
            "FIREBASE_ENABLED=true боловч firebase-admin суулгаагүй байна."
        ) from exc

    try:
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app()
        firestore.client().collection("screenings").add(
            {
                "age_months": age_months,
                "answers": list(answers),
                "score": score,
                "consent": True,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )
    except Exception as exc:
        raise RuntimeError("Firestore-д үнэлгээг хадгалах боломжгүй байна.") from exc
    return True
