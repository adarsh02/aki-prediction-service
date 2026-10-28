class DBError(Exception):
    """Base class for all database-related errors."""
    pass

class DBConnectionError(DBError):
    """Raised when connecting to the database fails."""
    pass

class DBTransactionError(DBError):
    """Raised when a transaction fails (rollback needed)."""
    pass

class DBExecError(DBError):
    """Raised when a query/fetch fails."""
    def __init__(self, message, mrn=None):
        super().__init__(message)
        self.mrn = mrn