from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Sequence, Union, Optional, Literal

import pandas as pd
import requests

from ldlinkpython import DEFAULT_API_ROOT

try:
    # Expected to exist elsewhere in the package
    from ldlinkpython.parsers import parse_matrix  # type: ignore
except Exception:  # pragma: no cover
    parse_matrix = None  # type: ignore


_REQUEST_LOCK = threading.Lock()


def _normalize_snps(snps: Union[str, Sequence[str]]) -> List[str]:
    if snps is None:
        raise ValueError("snps is required and must be a string or a sequence of strings.")

    if isinstance(snps, str):
        # Accept common separators. Prefer treating whitespace/comma/newline as delimiters.
        raw = (
            snps.replace("\n", " ")
            .replace("\r", " ")
            .replace("\t", " ")
            .replace(",", " ")
        )
        parts = [p.strip() for p in raw.split(" ") if p.strip()]
        if not parts:
            raise ValueError("snps must contain at least one SNP identifier.")
        return parts

    if isinstance(snps, (list, tuple)):
        parts = [str(s).strip() for s in snps if str(s).strip()]
        if not parts:
            raise ValueError("snps must contain at least one SNP identifier.")
        return parts

    # Generic sequence support
    try:
        parts = [str(s).strip() for s in snps if str(s).strip()]  # type: ignore[arg-type]
    except TypeError as e:
        raise ValueError("snps must be a string or a sequence of strings.") from e

    if not parts:
        raise ValueError("snps must contain at least one SNP identifier.")
    return parts


def _get_token(token: Optional[str]) -> str:
    tok = token or os.getenv("LDLINK_TOKEN")
    if not tok:
        raise ValueError(
            "LDlink API token missing. Provide token=... or set environment variable LDLINK_TOKEN."
        )
    return tok


def _validate_choice(name: str, value: str, allowed: Sequence[str]) -> str:
    v = str(value).strip()
    if not v:
        raise ValueError(f"{name} is required.")
    v_lower = v.lower()
    allowed_lower = {a.lower(): a for a in allowed}
    if v_lower not in allowed_lower:
        raise ValueError(f"{name} must be one of {list(allowed)} (got {value!r}).")
    return allowed_lower[v_lower]


def _request_json(
    method: Literal["GET", "POST"],
    url: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Any:
    with _REQUEST_LOCK:
        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=120,
            )
        except requests.RequestException as e:
            raise RuntimeError(f"Network error calling LDlink endpoint: {e}") from e

    if resp.status_code >= 400:
        # Try to provide helpful diagnostics
        text = ""
        try:
            text = resp.text or ""
        except Exception:
            text = ""
        msg = f"LDlink request failed ({resp.status_code}) for {method} {url}"
        if text.strip():
            msg += f": {text.strip()}"
        raise RuntimeError(msg)

    # LDlink sometimes returns JSON or plain text; attempt JSON first
    try:
        return resp.json()
    except ValueError:
        return resp.text


def ldmatrix(
    snps: Union[str, Sequence[str]],
    pop: str = "CEU",
    r2d: str = "r2",
    genome_build: str = "grch37",
    token: Optional[str] = None,
    api_root: str = DEFAULT_API_ROOT,
    return_type: str = "dataframe",
    request_method: str = "auto",
) -> Union[pd.DataFrame, Any]:
    """
    Call the LDlink 'ldmatrix' endpoint.

    Parameters
    ----------
    snps:
        SNP identifiers. String or sequence of strings. If string, common separators
        (whitespace, comma, newline) are supported.
    pop:
        1000G population code (e.g., "CEU").
    r2d:
        "r2" or "d" (LD measure).
    genome_build:
        "grch37" or "grch38".
    token:
        LDlink API token. If None, reads environment variable LDLINK_TOKEN.
    api_root:
        Base LDlink REST API root.
    return_type:
        "dataframe" to parse with parse_matrix; otherwise returns the raw response.
    request_method:
        "auto" (GET if len(snps)<=300 else POST), or "get", or "post".

    Returns
    -------
    pandas.DataFrame or raw response
    """
    snp_list = _normalize_snps(snps)

    pop = str(pop).strip()
    if not pop:
        raise ValueError("pop is required.")

    r2d = _validate_choice("r2d", r2d, allowed=["r2", "d"])
    genome_build = _validate_choice("genome_build", genome_build, allowed=["grch37", "grch38"])

    return_type_norm = str(return_type).strip().lower()
    if return_type_norm not in {"dataframe", "raw"}:
        raise ValueError("return_type must be 'dataframe' or 'raw'.")

    req_method = str(request_method).strip().lower()
    if req_method not in {"auto", "get", "post"}:
        raise ValueError("request_method must be 'auto', 'get', or 'post'.")

    if req_method == "auto":
        req_method = "get" if len(snp_list) <= 300 else "post"

    tok = _get_token(token)
    api_root_clean = str(api_root).rstrip("/")
    url = f"{api_root_clean}/ldmatrix"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {tok}",
    }

    if req_method == "get":
        params = {
            "snps": "+".join(snp_list),
            "pop": pop,
            "r2_d": r2d,
            "genome_build": genome_build,
        }
        data = _request_json("GET", url, headers=headers, params=params, json_body=None)
    else:
        body = {
            "snps": snp_list,
            "pop": pop,
            "r2_d": r2d,
            "genome_build": genome_build,
        }
        data = _request_json("POST", url, headers=headers, params=None, json_body=body)

    if return_type_norm == "raw":
        return data

    if parse_matrix is None:
        raise RuntimeError(
            "parse_matrix is not available. Ensure ldlinkpython.parsers.parse_matrix exists."
        )

    try:
        df = parse_matrix(data)  # type: ignore[misc]
    except Exception as e:
        raise RuntimeError(f"Failed to parse ldmatrix response with parse_matrix: {e}") from e

    if not isinstance(df, pd.DataFrame):
        raise RuntimeError("parse_matrix did not return a pandas.DataFrame as expected.")
    return df
