class UrlShortenerError(Exception):
    """Base exception — all custom errors inherit from this."""
    status_code: int = 500
    message: str = "Internal server error"


class InvalidUrlError(UrlShortenerError):
    status_code = 400
    message = "The provided URL is invalid"


class CodeNotFoundError(UrlShortenerError):
    status_code = 404
    message = "Short code not found or expired"


class RateLimitExceededError(UrlShortenerError):
    status_code = 429
    message = "Rate limit exceeded — try again later"
