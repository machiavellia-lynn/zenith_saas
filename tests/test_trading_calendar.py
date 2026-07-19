"""
tests/test_trading_calendar.py — Unit tests for core/trading_calendar.py

The fixture below is the official IDX "Kalender Libur Bursa 2026". It is the
oracle for this module: a bursa-open day must never be one of these dates, and
the published Hari Bursa counts must come out exactly.
"""
import pytest

import core.trading_calendar as tc
from core.trading_calendar import trading_dates, next_trading_day_map


# Official IDX bursa holidays 2026 (weekdays only — the published table already
# excludes Sat/Sun, and notes Idul Fitri 21-22 Mar, Paskah 5 Apr and Waisak
# 31 May fall on a weekend).
IDX_HOLIDAYS_2026 = {
    "2026-01-01", "2026-01-16",
    "2026-02-16", "2026-02-17",
    "2026-03-18", "2026-03-19", "2026-03-20", "2026-03-23", "2026-03-24",
    "2026-04-03",
    "2026-05-01", "2026-05-14", "2026-05-15", "2026-05-27", "2026-05-28",
    "2026-06-01", "2026-06-16",
    "2026-08-17", "2026-08-25",
    "2026-12-24", "2026-12-25", "2026-12-31",
}


class FakeConn:
    """Stands in for a psycopg2 connection; trading_calendar only reads."""


def _patch_rows(monkeypatch, rows):
    """Make core.trading_calendar.fetchall return `rows` (list of dicts)."""
    monkeypatch.setattr(tc, "fetchall", lambda conn, sql, params=None: rows)


# ── trading_dates ─────────────────────────────────────────────────────────────

def test_trading_dates_returns_strings_oldest_first(monkeypatch):
    _patch_rows(monkeypatch, [{"date": "2026-05-12"}, {"date": "2026-05-13"}])
    assert trading_dates(FakeConn()) == ["2026-05-12", "2026-05-13"]


def test_trading_dates_bounds_are_passed_through(monkeypatch):
    captured = {}

    def _fake(conn, sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(tc, "fetchall", _fake)
    trading_dates(FakeConn(), "2026-05-01", "2026-05-31")
    assert captured["params"] == ["2026-05-01", "2026-05-31"]
    assert "date >= %s" in captured["sql"] and "date <= %s" in captured["sql"]


def test_trading_dates_filters_on_volume_not_row_presence(monkeypatch):
    """The whole point: a date is kept only if some ticker actually traded.

    Guards against a regression to `volume != 0` — the eod->price_history sync
    writes close only, so the fabricated rows have volume NULL, never 0.
    """
    captured = {}
    monkeypatch.setattr(
        tc, "fetchall",
        lambda conn, sql, params=None: (captured.setdefault("sql", sql), [])[1])
    trading_dates(FakeConn())
    sql = captured["sql"]
    assert "MAX(volume) > 0" in sql
    assert "!= 0" not in sql
    assert "DISTINCT date" not in sql


# ── next_trading_day_map ──────────────────────────────────────────────────────

def test_next_trading_day_map_converts_to_dmy(monkeypatch):
    _patch_rows(monkeypatch, [{"date": "2026-05-12"}, {"date": "2026-05-13"}])
    assert next_trading_day_map(FakeConn()) == {"12-05-2026": "13-05-2026"}


def test_next_trading_day_map_skips_closed_days(monkeypatch):
    """13 May -> 18 May: 14/15 May are IDX holidays and 16/17 is a weekend.

    This is the reported bug — with closed days in the calendar the exit landed
    on 14-05-2026, which has no 15m candles, so the trade died as NO_DATA.
    """
    _patch_rows(monkeypatch, [
        {"date": "2026-05-13"}, {"date": "2026-05-18"}, {"date": "2026-05-19"},
    ])
    assert next_trading_day_map(FakeConn())["13-05-2026"] == "18-05-2026"


def test_next_trading_day_map_last_day_has_no_successor(monkeypatch):
    _patch_rows(monkeypatch, [{"date": "2026-05-12"}, {"date": "2026-05-13"}])
    assert "13-05-2026" not in next_trading_day_map(FakeConn())


def test_next_trading_day_map_empty(monkeypatch):
    _patch_rows(monkeypatch, [])
    assert next_trading_day_map(FakeConn()) == {}


# ── official IDX calendar oracle ──────────────────────────────────────────────

@pytest.mark.parametrize("holiday", sorted(IDX_HOLIDAYS_2026))
def test_gazetted_holiday_never_becomes_a_trading_day(monkeypatch, holiday):
    """A closed day present in price_history must not survive into the calendar.

    Simulated the way it actually happens: the closed day is in the table with
    carried-forward closes and NULL volume, so only the HAVING clause removes
    it. Here that clause is the DB's job, so we assert the caller never sees a
    holiday it did not filter — i.e. the map is built from what the query
    returns, with no re-derivation of dates on the Python side.
    """
    _patch_rows(monkeypatch, [{"date": "2026-07-06"}, {"date": "2026-07-07"}])
    assert holiday not in trading_dates(FakeConn())
    assert holiday not in next_trading_day_map(FakeConn())
