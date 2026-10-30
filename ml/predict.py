import math
from numbers import Real
from pathlib import Path
from typing import Mapping

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline


MODEL_FEATURES = (
    "tracking_ratio",
    "ball_visible_rate",
    "pointing_rate",
    "eyes_rate",
    "face_rate",
    "Age",
)
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "data" / "synora_model.joblib"


class ResearchPredictionInputError(ValueError):
    pass


def _load_model_bundle(model_path):
    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"Судалгааны загвар олдсонгүй: {path}")

    bundle = joblib.load(path)
    if not isinstance(bundle, dict):
        raise ValueError("Загварын файл model bundle форматтай биш байна.")
    if bundle.get("features") != list(MODEL_FEATURES):
        raise ValueError("Загварын feature нэр эсвэл дараалал хүлээгдсэнтэй таарахгүй байна.")
    if not isinstance(bundle.get("model"), Pipeline):
        raise ValueError("Загварын bundle-д sklearn Pipeline алга байна.")
    classes = bundle.get("classes")
    if not isinstance(classes, dict) or not {0, 1}.issubset(classes):
        raise ValueError("Загварын ангиллын тайлбар дутуу байна.")

    return bundle


def predict_research_label(features: Mapping, model_path=DEFAULT_MODEL_PATH):
    """Run the stored research model with its exact, ordered numeric feature schema."""
    if not isinstance(features, Mapping):
        raise ResearchPredictionInputError(
            "features нь feature нэр ба numeric утгатай объект байна."
        )

    supplied = set(features)
    required = set(MODEL_FEATURES)
    missing = required - supplied
    extra = supplied - required
    if missing or extra:
        details = []
        if missing:
            details.append(f"дутуу: {', '.join(sorted(missing))}")
        if extra:
            details.append(f"илүү: {', '.join(sorted(map(str, extra)))}")
        raise ResearchPredictionInputError(
            f"Feature баганын бүрдэл буруу ({'; '.join(details)})."
        )

    ordered_values = {}
    for name in MODEL_FEATURES:
        value = features[name]
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ResearchPredictionInputError(
                f"{name} нь finite numeric утгатай байх ёстой."
            )
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ResearchPredictionInputError(
                f"{name} нь finite numeric утгатай байх ёстой."
            )
        ordered_values[name] = numeric_value

    bundle = _load_model_bundle(model_path)
    model_input = pd.DataFrame([ordered_values], columns=MODEL_FEATURES)
    class_id = int(bundle["model"].predict(model_input)[0])
    return {
        "class_id": class_id,
        "label": bundle["classes"][class_id],
        "purpose": bundle.get(
            "purpose", "Experimental research prototype; not a diagnostic tool"
        ),
    }
