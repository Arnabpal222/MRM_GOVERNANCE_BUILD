"""Domain errors raised by services and mapped to HTTP responses in app.main.

Messages must be human-readable (BRD §66).
"""


class ServiceError(Exception):
    status_code = 400

    def __init__(self, message: str, details: list[dict] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


class NotFoundError(ServiceError):
    status_code = 404


class ValidationFailedError(ServiceError):
    status_code = 422


class ConflictError(ServiceError):
    status_code = 409


class ForbiddenError(ServiceError):
    status_code = 403
