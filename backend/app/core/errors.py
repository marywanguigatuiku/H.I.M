"""Small, typed errors. Services raise these; main.py turns them into JSON {"detail": ...}."""


class AppError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BadRequest(AppError):
    status_code = 400


class Unauthorized(AppError):
    status_code = 401


class Forbidden(AppError):
    status_code = 403


class NotFound(AppError):
    status_code = 404


class Conflict(AppError):
    status_code = 409


class TooLarge(AppError):
    status_code = 413


class Invalid(AppError):
    status_code = 422
