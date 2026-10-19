"""Microservice d'inférence ML de détection d'anomalies (`services/detector`)."""

from services.detector.app import AnomalyDetectorEngine, app, create_app, detector_engine

__all__ = ["AnomalyDetectorEngine", "app", "create_app", "detector_engine"]
