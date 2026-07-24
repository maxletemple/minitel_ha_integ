"""Exceptions raised by the wm-server protocol client."""


class WmError(Exception):
    """Base exception for all wmclient errors."""


class WmConnectionError(WmError):
    """Raised when the TCP connection to wm-server cannot be established or is lost."""


class WmProtocolError(WmError):
    """Raised when a response from wm-server cannot be parsed."""


class WmTimeoutError(WmError):
    """Raised when a response from wm-server does not arrive in time."""
