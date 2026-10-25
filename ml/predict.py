from pathlib import Path

import joblib
import pandas as pd

from ml.preprocessing import FEATURE_COLUMNS, VALID_RESPONSES


def predict_research_label(model_path, answers):
    """Return an experimental model label; intentionally not wired into the website."""
    if not isinstance(answers, (list, tuple)) or len(answers) != 10:
        raise ValueError("Яг 10 хариулт шаардлагатай.")
    if any(not isinstance(answer, str) or answer not in VALID_RESPONSES for answer in answers):
        raise ValueError("Хариулт бүр A, B, C, D эсвэл E байна.")
    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"Сургасан загвар олдсонгүй: {path}")
    model = joblib.load(path)
    features = pd.DataFrame([dict(zip(FEATURE_COLUMNS, answers))])
    return int(model.predict(features)[0])
