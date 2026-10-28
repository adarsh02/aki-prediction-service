class HL7ValidationError(Exception):
    """
    Raised when an HL7 message fails validation.
    Carries optional info about segment and field.
    """

    def __init__(self, message: str, segment: str = None, field: str | int = None):
        super().__init__(message)
        self.segment = segment
        self.field = field

    def __str__(self):
        details = []
        if self.segment:
            details.append(f"Segment={self.segment}")
        if self.field:
            details.append(f"Field={self.field}")
        if details:
            return f"{super().__str__()} ({', '.join(details)})"
        return super().__str__()
