from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import ErrorDetail
from rest_framework.response import Response
from rest_framework.views import exception_handler


VALIDATION_ERROR_CODE = "validation_error"
VALIDATION_ERROR_MESSAGE = "Validation error."

ERROR_PAYLOADS = {
    status.HTTP_401_UNAUTHORIZED: (
        "not_authenticated",
        "Authentication credentials were not provided.",
    ),
    status.HTTP_403_FORBIDDEN: (
        "permission_denied",
        "You do not have permission to perform this action.",
    ),
    status.HTTP_404_NOT_FOUND: (
        "not_found",
        "Resource not found.",
    ),
    status.HTTP_500_INTERNAL_SERVER_ERROR: (
        "server_error",
        "An internal server error occurred.",
    ),
}


def _build_error_payload(status_code: int) -> dict:
    code, message = ERROR_PAYLOADS[status_code]
    return {
        "status": status_code,
        "code": code,
        "message": message,
        "errors": {},
    }


def _is_preformatted_error_object(value) -> bool:
    return (
        isinstance(value, dict)
        and "code" in value
        and ("message" in value or "field" in value)
    )


def normalize_validation_errors(errors):
    """Convert DRF validation details into JSON-friendly objects with explicit codes."""
    if isinstance(errors, ErrorDetail):
        return {
            "code": getattr(errors, "code", "invalid") or "invalid",
            "message": str(errors),
        }

    if _is_preformatted_error_object(errors):
        return errors

    if isinstance(errors, dict):
        return {key: normalize_validation_errors(value) for key, value in errors.items()}

    if isinstance(errors, (list, tuple)):
        return [normalize_validation_errors(item) for item in errors]

    if errors is None:
        return None

    return {
        "code": "invalid",
        "message": str(errors),
    }


def _build_validation_error_payload(errors) -> dict:
    if errors is None:
        normalized_errors = {}
    elif isinstance(errors, dict):
        normalized_errors = normalize_validation_errors(errors)
    else:
        normalized_errors = {
            "non_field_errors": normalize_validation_errors(errors)
        }

    return {
        "status": status.HTTP_400_BAD_REQUEST,
        "code": VALIDATION_ERROR_CODE,
        "message": VALIDATION_ERROR_MESSAGE,
        "errors": normalized_errors,
    }


def _is_standard_error_payload(data) -> bool:
    return (
        isinstance(data, dict)
        and {"status", "code", "message", "errors"}.issubset(data.keys())
    )


def standardized_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        if settings.DEBUG:
            return None
        return Response(
            _build_error_payload(status.HTTP_500_INTERNAL_SERVER_ERROR),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if _is_standard_error_payload(response.data):
        return response

    if response.status_code == status.HTTP_400_BAD_REQUEST:
        response.data = _build_validation_error_payload(response.data)
    elif response.status_code in ERROR_PAYLOADS:
        response.data = _build_error_payload(response.status_code)

    return response
