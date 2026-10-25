import argparse
import json
import math
from pathlib import Path

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ml.preprocessing import FEATURE_COLUMNS, load_dataset


def _build_pipeline(classifier):
    preprocessing = ColumnTransformer(
        [
            (
                "responses",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("encode", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                FEATURE_COLUMNS,
            )
        ]
    )
    return Pipeline([("preprocessing", preprocessing), ("classifier", classifier)])


def train(dataset_path, target_column, output_dir, group_column=None, test_size=0.2):
    features, target, groups = load_dataset(dataset_path, target_column, group_column)
    if len(features) < 5:
        raise ValueError("Сургалт, үнэлгээнд дата мөр хүрэлцэхгүй байна.")

    if groups is not None:
        splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=42)
        train_indices, test_indices = next(splitter.split(features, target, groups))
        if set(groups.iloc[train_indices]).intersection(set(groups.iloc[test_indices])):
            raise RuntimeError("Нэг оролцогч сургалт ба тестэд давхар орсон байна.")
    else:
        counts = target.value_counts()
        test_count = math.ceil(len(features) * test_size)
        train_count = len(features) - test_count
        stratify = (
            target
            if counts.min() >= 2
            and test_count >= target.nunique()
            and train_count >= target.nunique()
            else None
        )
        train_indices, test_indices = train_test_split(
            np.arange(len(features)),
            test_size=test_size,
            random_state=42,
            stratify=stratify,
        )

    x_train, x_test = features.iloc[train_indices], features.iloc[test_indices]
    y_train, y_test = target.iloc[train_indices], target.iloc[test_indices]
    if y_train.nunique() != 2 or y_test.nunique() != 2:
        raise ValueError(
            "Хуваарилалтын сургалт болон тест хэсэгт хоёуланд нь хоёр ангилал байх шаардлагатай."
        )

    candidates = {
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=42),
        "random_forest": RandomForestClassifier(
            n_estimators=300, random_state=42, class_weight="balanced"
        ),
    }
    evaluated = {}
    for name, classifier in candidates.items():
        pipeline = _build_pipeline(classifier)
        pipeline.fit(x_train, y_train)
        predictions = pipeline.predict(x_test)
        evaluated[name] = {
            "pipeline": pipeline,
            "precision": float(precision_score(y_test, predictions, zero_division=0)),
            "recall": float(recall_score(y_test, predictions, zero_division=0)),
            "f1": float(f1_score(y_test, predictions, zero_division=0)),
            "confusion_matrix": confusion_matrix(
                y_test, predictions, labels=[0, 1]
            ).tolist(),
        }

    selected_name = max(evaluated, key=lambda name: evaluated[name]["f1"])
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    joblib.dump(evaluated[selected_name]["pipeline"], destination / "screening_model.joblib")
    report = {
        "selected_model": selected_name,
        "metrics": {
            name: {key: value for key, value in result.items() if key != "pipeline"}
            for name, result in evaluated.items()
        },
        "feature_columns": FEATURE_COLUMNS,
        "dataset": Path(dataset_path).name,
        "grouped_split": groups is not None,
        "clinical_use": False,
    }
    (destination / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Зөвшөөрөлтэй өгөгдөл дээр судалгааны зориулалттай загвар үнэлэх."
    )
    parser.add_argument("--dataset", required=True, help="Зөвшөөрөлтэй CSV файлын зам")
    parser.add_argument("--target-column", required=True, help="Хоёр ангиллын 0/1 шошго")
    parser.add_argument("--group-column", help="Нэг хүүхдийг таних, давхардалгүй хуваах багана")
    parser.add_argument("--output-dir", default="ml/artifacts")
    parser.add_argument(
        "--authorized-dataset",
        action="store_true",
        required=True,
        help="Өгөгдөл ашиглах зөвшөөрөлтэй гэдгээ батлах шаардлагатай",
    )
    args = parser.parse_args()
    report = train(
        args.dataset,
        args.target_column,
        args.output_dir,
        args.group_column,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
