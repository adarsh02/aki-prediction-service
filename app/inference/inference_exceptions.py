class InferenceEngineError(Exception):
    """Custom exception for errors in the AKI inference engine."""

    def __init__(self, message: str):
        super().__init__(message)  # initialize base Exception with message
