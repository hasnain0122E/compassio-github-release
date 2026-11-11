"""Decision-engine input errors (mapped to {code, message} JSON by api/errors.py)."""


class DecisionInputError(ValueError):
    """422: the request is valid JSON but cannot be answered honestly as asked."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
