"""Deterministic pooled Ridge model for the frozen candidate procedure."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from coal_forecasting.candidate_features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    V2_NUMERIC_FEATURES,
)


PROCEDURE_ID = "pooled_direct_ridge_log_change_v1"
ALPHA_GRID = (0.1, 1.0, 10.0, 100.0)
V2_PROCEDURE_ID = "pooled_direct_ridge_raw_delta_v2"
V2_ALPHA_GRID = (1.0, 100.0, 10000.0, 1000000.0)


@dataclass(frozen=True)
class CandidateFit:
    predictions: pd.DataFrame
    coefficients: pd.DataFrame
    intercept: float
    training_rows: int


def _preprocessor(numeric_features: tuple[str, ...]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), list(numeric_features)),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                list(CATEGORICAL_FEATURES),
            ),
        ],
        sparse_threshold=0.0,
        verbose_feature_names_out=True,
    )


def fit_predict_ridge(
    training: pd.DataFrame,
    prediction: pd.DataFrame,
    *,
    alpha: float,
) -> CandidateFit:
    """Fit one outer-origin/horizon Ridge model and return finite forecasts."""
    required_training = {
        *NUMERIC_FEATURES,
        *CATEGORICAL_FEATURES,
        "response",
    }
    required_prediction = {*NUMERIC_FEATURES, *CATEGORICAL_FEATURES}
    missing_training = required_training.difference(training.columns)
    missing_prediction = required_prediction.difference(prediction.columns)
    if missing_training:
        raise ValueError(
            f"Candidate training rows are missing: {', '.join(sorted(missing_training))}"
        )
    if missing_prediction:
        raise ValueError(
            "Candidate prediction rows are missing: "
            + ", ".join(sorted(missing_prediction))
        )
    if training.empty:
        raise ValueError("Candidate training rows are empty")
    if training[list(required_training)].isna().any().any():
        raise ValueError("Candidate training rows contain missing model values")
    if prediction[list(required_prediction)].isna().any().any():
        raise ValueError("Candidate prediction rows contain missing model values")
    if not np.isfinite(float(alpha)) or alpha <= 0:
        raise ValueError("Ridge alpha must be finite and positive")

    transformer = _preprocessor(NUMERIC_FEATURES)
    x_train = transformer.fit_transform(training)
    x_prediction = transformer.transform(prediction)
    estimator = Ridge(alpha=float(alpha), fit_intercept=True, solver="svd")
    estimator.fit(x_train, training["response"].to_numpy(dtype=float))
    predicted_change = estimator.predict(x_prediction)

    result = prediction.copy().reset_index(drop=True)
    result["predicted_change"] = predicted_change
    unconstrained = result["log_level_t"].to_numpy(dtype=float) + predicted_change
    result["zero_floor_applied"] = unconstrained < 0
    result["predicted_log_level"] = np.maximum(0.0, unconstrained)
    result["forecast"] = np.expm1(result["predicted_log_level"])
    seen_states = set(training["state_code"].astype(str))
    result["state_seen_in_training"] = result["state_code"].astype(str).isin(
        seen_states
    )
    if not np.isfinite(result["forecast"]).all():
        raise ValueError("Candidate produced a non-finite point forecast")
    if result["forecast"].lt(0).any():
        raise ValueError("Candidate produced a negative point forecast")

    coefficients = pd.DataFrame(
        {
            "feature": transformer.get_feature_names_out(),
            "coefficient": estimator.coef_.astype(float),
        }
    )
    return CandidateFit(
        predictions=result,
        coefficients=coefficients,
        intercept=float(estimator.intercept_),
        training_rows=len(training),
    )


def fit_predict_v2_ridge(
    training: pd.DataFrame,
    prediction: pd.DataFrame,
    *,
    alpha: float,
) -> CandidateFit:
    """Fit the no-intercept raw-delta v2 model and forecast from persistence."""
    required_training = {
        *V2_NUMERIC_FEATURES,
        *CATEGORICAL_FEATURES,
        "response",
    }
    required_prediction = {*V2_NUMERIC_FEATURES, *CATEGORICAL_FEATURES}
    missing_training = required_training.difference(training.columns)
    missing_prediction = required_prediction.difference(prediction.columns)
    if missing_training:
        raise ValueError(
            f"Candidate v2 training rows are missing: "
            f"{', '.join(sorted(missing_training))}"
        )
    if missing_prediction:
        raise ValueError(
            "Candidate v2 prediction rows are missing: "
            + ", ".join(sorted(missing_prediction))
        )
    if training.empty:
        raise ValueError("Candidate v2 training rows are empty")
    if training[sorted(required_training)].isna().any().any():
        raise ValueError("Candidate v2 training rows contain missing model values")
    if prediction[sorted(required_prediction)].isna().any().any():
        raise ValueError("Candidate v2 prediction rows contain missing model values")
    if not np.isfinite(float(alpha)) or alpha <= 0:
        raise ValueError("Ridge alpha must be finite and positive")

    transformer = _preprocessor(V2_NUMERIC_FEATURES)
    x_train = transformer.fit_transform(training)
    x_prediction = transformer.transform(prediction)
    estimator = Ridge(alpha=float(alpha), fit_intercept=False, solver="svd")
    estimator.fit(x_train, training["response"].to_numpy(dtype=float))
    predicted_delta = estimator.predict(x_prediction)

    result = prediction.copy().reset_index(drop=True)
    result["predicted_delta"] = predicted_delta
    unconstrained = result["level_t"].to_numpy(dtype=float) + predicted_delta
    result["zero_floor_applied"] = unconstrained < 0
    result["forecast"] = np.maximum(0.0, unconstrained)
    seen_states = set(training["state_code"].astype(str))
    result["state_seen_in_training"] = result["state_code"].astype(str).isin(
        seen_states
    )
    if not np.isfinite(result["forecast"]).all():
        raise ValueError("Candidate v2 produced a non-finite point forecast")

    coefficients = pd.DataFrame(
        {
            "feature": transformer.get_feature_names_out(),
            "coefficient": estimator.coef_.astype(float),
        }
    )
    return CandidateFit(
        predictions=result,
        coefficients=coefficients,
        intercept=0.0,
        training_rows=len(training),
    )


def select_shared_alpha(
    metrics: pd.DataFrame,
    *,
    tie_tolerance: float = 0.0001,
) -> tuple[float, pd.DataFrame]:
    """Select one alpha by equal-weight mean horizon WAPE skill."""
    required = {
        "alpha",
        "horizon",
        "wape",
        "comparator_wape",
        "prediction_coverage",
    }
    missing = required.difference(metrics.columns)
    if missing:
        raise ValueError(f"Alpha metrics are missing: {', '.join(sorted(missing))}")
    if metrics.duplicated(["alpha", "horizon"]).any():
        raise ValueError("Alpha metrics contain duplicate alpha-horizon rows")
    if metrics["comparator_wape"].le(0).any():
        raise ValueError("Comparator WAPE must be positive")

    frame = metrics.copy()
    frame["wape_skill"] = 1.0 - frame["wape"].div(frame["comparator_wape"])
    summary = frame.groupby("alpha", as_index=False).agg(
        mean_wape_skill=("wape_skill", "mean"),
        minimum_prediction_coverage=("prediction_coverage", "min"),
        horizons=("horizon", "nunique"),
    )
    summary["eligible"] = summary["minimum_prediction_coverage"].eq(1.0)
    eligible = summary.loc[summary["eligible"]]
    if eligible.empty:
        raise ValueError("No alpha has complete prediction coverage")
    best = eligible["mean_wape_skill"].max()
    tied = eligible.loc[eligible["mean_wape_skill"].ge(best - tie_tolerance)]
    selected = float(tied["alpha"].max())
    summary["selected"] = summary["alpha"].eq(selected)
    return selected, summary.sort_values("alpha").reset_index(drop=True)
