class RobinhoodError(Exception):
    """Base exception for package-specific errors."""


class OrderFailedError(RobinhoodError):
    """Raised when an order submission fails."""


class InstruemtNotFoundError(RobinhoodError):
    """Raised when a requested instrument cannot be found."""


class AccountIdNotFoundError(RobinhoodError):
    """Raised when an authenticated account id is unavailable."""


class MalformedOrderError(RobinhoodError):
    """Raised when an order payload is invalid before submission."""


class ConfigurationError(RobinhoodError):
    """Raised for invalid local configuration."""


class AuthenticationError(RobinhoodError):
    """Raised for authentication failures."""


class TokenExtractionError(AuthenticationError):
    """Raised when local browser token extraction fails."""
