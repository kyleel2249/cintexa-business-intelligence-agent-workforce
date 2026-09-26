"""Standard application errors — never leak raw DB errors to clients."""

from __future__ import annotations


class AppError(Exception):
    code = "internal_error"
    http_status = 500

    def __init__(self, message: str = "", *, details: dict | None = None):
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details or {}


class ValidationError(AppError):
    code = "validation_error"
    http_status = 400


class AuthenticationError(AppError):
    code = "authentication_error"
    http_status = 401


class AuthorizationError(AppError):
    code = "authorization_error"
    http_status = 403


class NotFoundError(AppError):
    code = "not_found"
    http_status = 404


class ConflictError(AppError):
    code = "conflict"
    http_status = 409


class PersistenceError(AppError):
    code = "persistence_error"
    http_status = 500


class ExternalServiceError(AppError):
    code = "external_service_error"
    http_status = 502


class ExecutionError(AppError):
    code = "execution_error"
    http_status = 500


class InternalError(AppError):
    code = "internal_error"
    http_status = 500
