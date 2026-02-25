from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd
import pytest


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "", json_data: Any = None):
        self.status_code = status_code
        self._text = text
        self._json_data = json_data

    @property
    def text(self) -> str:
        return self._text

    def json(self) -> Any:
        if self._json_data is None:
            raise ValueError("No JSON")
        return self._json_data


def _parse_matrix_tsv(payload: Any) -> pd.DataFrame:
    """
    Minimal parser for a TSV square matrix of the form LDlink returns, where the first
    header line begins with a TAB (blank top-left cell), followed by column SNP IDs.

    IMPORTANT: Do not .strip() the whole payload, because that removes the leading TAB
    and breaks header parsing.

    Example:
        \\trs1\\trs2
        rs1\\t1\\t0.2
        rs2\\t0.2\\t1
    """
    if not isinstance(payload, str):
        raise TypeError("Expected matrix payload as string")

    # Keep leading TABs; just normalize line endings and drop fully empty lines.
    raw_lines = payload.splitlines()
    lines = [ln.rstrip("\r\n") for ln in raw_lines if ln.strip() != ""]
    if not lines:
        raise ValueError("Empty matrix payload")

    header_parts = lines[0].split("\t")
    if len(header_parts) < 2:
        raise ValueError("Matrix header does not contain column labels")

    cols = header_parts[1:]
    data = []
    idx = []

    for ln in lines[1:]:
        parts = ln.split("\t")
        if len(parts) != len(cols) + 1:
            raise ValueError("Row length does not match header length")
        idx.append(parts[0])
        data.append([float(x) for x in parts[1:]])

    return pd.DataFrame(data, index=idx, columns=cols)


def test_ldmatrix_auto_get_params(monkeypatch: pytest.MonkeyPatch) -> None:
    from ldlinkpython.endpoints import ldmatrix as ldmatrix_mod

    calls: Dict[str, Any] = {}

    def fake_request(
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> _FakeResponse:
        calls["method"] = method
        calls["url"] = url
        calls["headers"] = headers
        calls["params"] = params
        calls["json"] = json
        calls["timeout"] = timeout
        return _FakeResponse(status_code=200, text="\trs1\trs2\nrs1\t1\t0.2\nrs2\t0.2\t1\n")

    monkeypatch.setattr(ldmatrix_mod, "parse_matrix", _parse_matrix_tsv)
    monkeypatch.setattr(ldmatrix_mod.requests, "request", fake_request)

    df = ldmatrix_mod.ldmatrix(
        snps=["rs1", "rs2"],
        pop="CEU",
        r2d="r2",
        genome_build="grch37",
        token="test-token",
        return_type="dataframe",
        request_method="auto",
    )

    assert calls["method"] == "GET"
    assert calls["url"].endswith("/ldmatrix")
    assert calls["params"] == {
        "snps": "rs1+rs2",
        "pop": "CEU",
        "r2_d": "r2",
        "genome_build": "grch37",
    }
    assert calls["json"] is None

    assert isinstance(df, pd.DataFrame)
    assert df.shape == (2, 2)
    assert list(df.index) == ["rs1", "rs2"]
    assert list(df.columns) == ["rs1", "rs2"]


def test_ldmatrix_auto_post_json_body(monkeypatch: pytest.MonkeyPatch) -> None:
    from ldlinkpython.endpoints import ldmatrix as ldmatrix_mod

    calls: Dict[str, Any] = {}

    def fake_request(
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> _FakeResponse:
        calls["method"] = method
        calls["url"] = url
        calls["headers"] = headers
        calls["params"] = params
        calls["json"] = json
        calls["timeout"] = timeout
        return _FakeResponse(status_code=200, text="\trs1\trs2\nrs1\t1\t0.2\nrs2\t0.2\t1\n")

    monkeypatch.setattr(ldmatrix_mod, "parse_matrix", _parse_matrix_tsv)
    monkeypatch.setattr(ldmatrix_mod.requests, "request", fake_request)

    snps = [f"rs{i}" for i in range(1, 302)]  # 301 SNPs -> POST when request_method="auto"
    _ = ldmatrix_mod.ldmatrix(
        snps=snps,
        pop="CEU",
        r2d="r2",
        genome_build="grch37",
        token="test-token",
        return_type="dataframe",
        request_method="auto",
    )

    assert calls["method"] == "POST"
    assert calls["url"].endswith("/ldmatrix")
    assert calls["params"] is None
    assert calls["json"] == {
        "snps": snps,
        "pop": "CEU",
        "r2_d": "r2",
        "genome_build": "grch37",
    }


def test_ldmatrix_parses_matrix_to_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    from ldlinkpython.endpoints import ldmatrix as ldmatrix_mod

    def fake_request(
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> _FakeResponse:
        matrix_tsv = "\trsA\trsB\nrsA\t1\t0.75\nrsB\t0.75\t1\n"
        return _FakeResponse(status_code=200, text=matrix_tsv, json_data=None)

    monkeypatch.setattr(ldmatrix_mod, "parse_matrix", _parse_matrix_tsv)
    monkeypatch.setattr(ldmatrix_mod.requests, "request", fake_request)

    df = ldmatrix_mod.ldmatrix(
        snps=["rsA", "rsB"],
        token="test-token",
        return_type="dataframe",
        request_method="get",
    )

    assert df.shape == (2, 2)
    assert list(df.index) == ["rsA", "rsB"]
    assert list(df.columns) == ["rsA", "rsB"]
    assert df.loc["rsA", "rsA"] == 1.0
    assert df.loc["rsA", "rsB"] == 0.75
    assert df.loc["rsB", "rsA"] == 0.75
    assert df.loc["rsB", "rsB"] == 1.0
