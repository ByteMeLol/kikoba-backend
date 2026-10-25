from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class VicobaException(Exception):
    """Base class for VICOBA custom exceptions."""
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class BusinessRuleViolationException(VicobaException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=status.HTTP_400_BAD_REQUEST)


class ResourceNotFoundException(VicobaException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND)


class ConflictException(VicobaException):
    def __init__(self, message: str = "Resource conflict or already processed"):
        super().__init__(message=message, status_code=status.HTTP_409_CONFLICT)


class InsufficientPermissionsException(VicobaException):
    def __init__(self, message: str = "Insufficient permissions for this action"):
        super().__init__(message=message, status_code=status.HTTP_403_FORBIDDEN)


def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(VicobaException)
    async def vicoba_exception_handler(request: Request, exc: VicobaException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "status_code": exc.status_code}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "details": exc.errors(),
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY
            }
        )
