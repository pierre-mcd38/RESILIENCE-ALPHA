"""Module Machine Learning (AIOps) de PROJECT RESILIENCE-ALPHA.

Ce paquet contient :
- `ml.features` : extraction, validation, normalisation des 7 variables par fenêtre de 5s
  et explication locale des anomalies (`top_contributing_features`).
- `ml.generate_dataset` : génération reproductible sans fuite de données des sessions
  d'entraînement, de validation et de test.
- `ml.train_evaluate` : entraînement et évaluation comparative (`IsolationForest` vs
  `OneClassSVM` vs `EllipticEnvelope` / Z-score robuste), calibration du seuil et export
  des artefacts dans `ml/artifacts/`.
"""

from ml.features import (
    EXPENSIVE_ENDPOINTS,
    FEATURE_NAMES,
    WINDOW_SECONDS,
    compute_ip_entropy,
    compute_top_contributing_features,
    extract_window_features,
    features_to_vector,
    normalize_feature_dict,
)

__all__ = [
    "EXPENSIVE_ENDPOINTS",
    "FEATURE_NAMES",
    "WINDOW_SECONDS",
    "compute_ip_entropy",
    "compute_top_contributing_features",
    "extract_window_features",
    "features_to_vector",
    "normalize_feature_dict",
]
