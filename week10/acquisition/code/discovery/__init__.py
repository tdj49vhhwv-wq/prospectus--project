#!/usr/bin/env python3
"""Exchange discovery adapters — one route per exchange/board.

``discover(exchange, ...)`` dispatches to the matching adapter and returns a
list of :class:`~discovery.base.Candidate` objects.  Discovery is transport
only; the acquire pipeline re-validates document identity before anything is
accepted into the canonical registry.
"""
from __future__ import annotations

from .base import Candidate
from .sse import discover as discover_sse
from .szse import discover as discover_szse
from .bse import discover as discover_bse

ADAPTERS = {
    "SSE": discover_sse,
    "SZSE": discover_szse,
    "BSE": discover_bse,
}


def discover(exchange, stock_code, company_name, date_range):
    fn = ADAPTERS.get((exchange or "").upper())
    if fn is None:
        raise ValueError(f"no discovery adapter for exchange {exchange!r}")
    return fn(stock_code, company_name, date_range)
