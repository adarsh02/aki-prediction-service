# inference/features.py
import numpy as np

def build_features(age, sex, creatinine_values):
    """
    Convert raw patient data into ML feature vector.
    Returns: np.ndarray shape (1, 7)
    """
    # remove None or NaN values
    creatinine_values = [v for v in creatinine_values if v is not None and not np.isnan(v)]
    
    if not creatinine_values:
        raise ValueError(f"Creatinine history required: {creatinine_values}")

    baseline = creatinine_values[0]
    last = creatinine_values[-1]
    delta = last - baseline
    mean = np.mean(creatinine_values)
    std = np.std(creatinine_values)

    sex_binary = 1 if str(sex).lower() in ("m", "male") else 0

    return np.array([[
        age,
        sex_binary,
        baseline,
        last,
        delta,
        mean,
        std
    ]])
