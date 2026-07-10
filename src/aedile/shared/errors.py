class AedileError(Exception):
    """Base exception class for all Aedile errors."""

    pass


class ConfigError(AedileError):
    """Raised when there is an issue reading, parsing, or validating the configuration."""

    pass


class ParserError(AedileError):
    """Raised when a source file cannot be parsed or has syntactical issues."""

    pass


class RuleError(AedileError):
    """Raised when rules are misconfigured or fail during validation execution."""

    pass


class BaselineError(AedileError):
    """Raised when the baseline file is invalid, missing, or corrupt."""

    pass


class CacheError(AedileError):
    """Raised when the scan cache fails to read or write."""

    pass
