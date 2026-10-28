# inference/model.py
import lightgbm as lgb
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

_aki_model = None

BASE_DIR = Path(__file__).resolve().parents[1]
model_path = BASE_DIR / "data" / "model.txt"

def get_model():
    global _aki_model

    if _aki_model is not None:
        return _aki_model

    if not model_path.exists():
        logger.error(f"AKI model file not found: {model_path}")
        raise FileNotFoundError(f"AKI model file not found {model_path}")

    try:
        _aki_model = lgb.Booster(model_file=str(model_path))
    except Exception as e:
        logger.exception("Failed to load AKI model from file")
        raise RuntimeError("AKI model could not be loaded") from e

    return _aki_model
