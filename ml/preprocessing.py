from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [f"q{i}" for i in range(1, 11)]
VALID_RESPONSES = {"A", "B", "C", "D", "E"}


def load_dataset(
    dataset_path: str,
    target_column: str,
    group_column: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.Series, Optional[pd.Series]]:
    """Load an explicitly supplied dataset; never create or infer training labels."""
    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"Өгөгдлийн файл олдсонгүй: {path}")
    if path.suffix.lower() != ".csv":
        raise ValueError("Зөвхөн CSV форматтай дата багц ашиглана уу.")

    data = pd.read_csv(path)
    required = set(FEATURE_COLUMNS + [target_column])
    if group_column:
        required.add(group_column)
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Шаардлагатай багана дутуу байна: {', '.join(missing)}")

    features = data[FEATURE_COLUMNS].copy()
    for column in FEATURE_COLUMNS:
        features[column] = data[column].map(
            lambda value: str(value).strip().upper() if pd.notna(value) else np.nan
        )
        if features[column].notna().sum() == 0:
            raise ValueError(f"{column} баганад ашиглах хариулт байхгүй байна.")
        invalid = features[column].notna() & ~features[column].isin(VALID_RESPONSES)
        if invalid.any():
            raise ValueError(f"{column} баганад A–E-ээс өөр утга байна.")

    raw_target = data[target_column]
    target = pd.to_numeric(raw_target, errors="coerce")
    invalid_target = raw_target.notna() & target.isna()
    if invalid_target.any():
        raise ValueError("Зорилтот шошго нь зөвхөн 0 эсвэл 1 утгатай байна.")
    if ((target.dropna() % 1) != 0).any() or not set(target.dropna().unique()).issubset(
        {0, 1}
    ):
        raise ValueError("Зорилтот шошго нь зөвхөн 0 эсвэл 1 бүхэл утгатай байна.")
    valid_target = target.notna()
    if not valid_target.any():
        raise ValueError("Шошготой мөр олдсонгүй.")
    target = target.loc[valid_target].astype(int)
    if not set(target.unique()).issubset({0, 1}) or target.nunique() != 2:
        raise ValueError("Зорилтот шошго нь хоёр ангиллын 0, 1 утгатай байна.")

    features = features.loc[valid_target].reset_index(drop=True)
    target = target.reset_index(drop=True)
    groups = None
    if group_column:
        groups = data.loc[valid_target, group_column].reset_index(drop=True)
        if groups.isna().any():
            raise ValueError("Нэг хүүхдийн бүртгэлийг бүлэглэх баганад хоосон утга байна.")
    return features, target, groups
