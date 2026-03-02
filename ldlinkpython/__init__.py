from __future__ import annotations

DEFAULT_API_ROOT = "https://ldlink.nih.gov/LDlinkRest"
__version__ = "0.1.0"

from ldlinkpython.client import LDlinkClient
from ldlinkpython.endpoints.ldproxy import ldproxy
from ldlinkpython.endpoints.ldtrait import ldtrait

__all__ = [
    "DEFAULT_API_ROOT",
    "__version__",
    "LDlinkClient",
    "ldproxy",
]
