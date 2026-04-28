class EmptyOutputError(RuntimeError):
    """Base class for API responses that completed but produced no usable output."""


class EmptyTextOutputError(EmptyOutputError):
    """Raised when a text API call returns an empty final text."""


class EmptyImageOutputError(EmptyOutputError):
    """Raised when an image API call returns no usable images."""
