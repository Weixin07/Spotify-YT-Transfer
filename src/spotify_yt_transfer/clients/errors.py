"""Shared client exceptions."""


class OAuthCredentialsMissing(RuntimeError):
    """
    Raised when OAuth credentials are unavailable in headless environments.

    Signals that the user must complete the authorization flow manually.
    """

