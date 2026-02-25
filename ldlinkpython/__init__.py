"""
ldlinkpython package public interface.
"""

from __future__ import annotations

from typing import Any, Callable, List

DEFAULT_API_ROOT: str = "https://ldlink.nih.gov/LDlinkRest"
__version__: str = "0.1.0"


class LDlinkClient:
    """LDlink REST API client (placeholder until implemented)."""

    def __init__(self, token: str | None = None, api_root: str = DEFAULT_API_ROOT) -> None:
        self.token = token
        self.api_root = api_root


def _not_implemented(*args: Any, **kwargs: Any) -> None:
    raise NotImplementedError(
        "This endpoint function is a stub and has not been implemented yet."
    )


# Endpoint function stubs (to be implemented in their respective modules)
ldproxy: Callable[..., Any] = _not_implemented
ldmatrix: Callable[..., Any] = _not_implemented
ldpair: Callable[..., Any] = _not_implemented
ldtrait: Callable[..., Any] = _not_implemented
ldexpress: Callable[..., Any] = _not_implemented
ldpop: Callable[..., Any] = _not_implemented
ldhap: Callable[..., Any] = _not_implemented
snpclip: Callable[..., Any] = _not_implemented
snpchip: Callable[..., Any] = _not_implemented

__all__: List[str] = [
    "DEFAULT_API_ROOT",
    "LDlinkClient",
    "__version__",
    "ldproxy",
    "ldmatrix",
    "ldpair",
    "ldtrait",
    "ldexpress",
    "ldpop",
    "ldhap",
    "snpclip",
    "snpchip",
]
