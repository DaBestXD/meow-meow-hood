class RobinhoodError(Exception):
    """Base exception for package-specific errors."""


class OrderFailedError(RobinhoodError):
    """Raised when an order submission fails."""


class EndpointNotFoundError(RobinhoodError):
    """Raise when an endpoint returns 404"""


class InvalidTypeError(RobinhoodError):
    """Raised when an robinhood object id returns none"""


class NoFutureProductsReturnedError(RobinhoodError):
    """Raised when no futures products are returned"""


class FailedToCreateWatchlistError(RobinhoodError):
    """When a watchlist fails to be created"""


class FailedToDeleteWatchlistError(RobinhoodError):
    """When a watchlist fails to be deleted"""


class FailedToModifyWatchlistError(RobinhoodError):
    """When a watchlist failes to be added/deleted"""


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
