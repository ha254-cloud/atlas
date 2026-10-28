class ProcessingError(Exception):
    pass


class ValidationError(ProcessingError):
    def __init__(self, missing_columns):
        self.missing_columns = missing_columns
        message = f"Validation failed, missing columns: {missing_columns}"
        super().__init__(message)


class CSVSchemaError(ProcessingError):
    """
    Raised when an uploaded file is missing required columns entirely — a
    fail-fast, whole-file rejection (before any row is processed), distinct
    from ValidationError/ClaimValidationError which reject one row at a time.
    """

    def __init__(self, missing_columns: list[str]):
        self.missing_columns = missing_columns
        message = f"Missing required columns: {', '.join(missing_columns)}"
        super().__init__(message)


class PersistenceError(ProcessingError):
    pass


class DuplicateClaimError(ProcessingError):
    pass


class ClaimValidationError(ProcessingError):
    """Raised when the ValidationEngine finds one or more blocking issues."""

    def __init__(self, issues):
        self.issues = issues
        message = "; ".join(f"[{i.code}] {i.message}" for i in issues)
        super().__init__(message or "Claim failed validation")
