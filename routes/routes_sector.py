"""
routes_sector.py — Blueprint: /sector, /api/sector
RULE: Routing only. All aggregation done via DB query here (sector is pure aggregation).
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request, redirect
from core.auth import is_authed
from config import WIB, SECTORS
from core.utils import parse_date, date_range
from core.db import get_db, fetchall
from data.price_fetch import get_gains_batch

bp_sector = Blueprint("sector", __name__)


@bp_sector.route("/sector")
def sector_page():
    if not is_authed():
        return redirect("/")
    return render_template("sector.html")


@bp_sector.route("/api/sector")
def sector_api():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

    today_wib = datetime.now(WIB).strftime("%d-%m-%Y")
    date_from = request.args.get("date_from", today_wib)
    date_to   = request.args.get("date_to",   today_wib)

    try:
        parse_date(date_from)
        parse_date(date_to)
    except ValueError:
        return jsonify({"error": "Format tanggal salah"}), 400

    dates = date_range(date_from, date_to)

    all_tickers = list({t for tlist in SECTORS.values() for t in tlist})
    conn = get_db()

    try:
        rows_sm_bm = fetchall(conn, """
            SELECT ticker, channel, SUM(mf_delta_numeric) AS mf
            FROM raw_messages
            WHERE ticker = ANY(%s) AND date = ANY(%s)
            GROUP BY ticker, channel
        """, [all_tickers, dates])

        rows_mf = fetchall(conn, """
            SELECT ticker, channel, SUM(mf_numeric) AS mf
            FROM raw_mf_messages
            WHERE ticker = ANY(%s) AND date = ANY(%s)
            GROUP BY ticker, channel
        """, [all_tickers, dates])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    tdata: dict = {}
    for row in rows_sm_bm:
        t = row["ticker"]
        tdata.setdefault(t, {"sm": 0, "bm": 0, "mfp": 0, "mfm": 0})
        if row["channel"] == "smart":
            tdata[t]["sm"] += row["mf"] or 0
        else:
            tdata[t]["bm"] += abs(row["mf"] or 0)

    for row in rows_mf:
        t = row["ticker"]
        tdata.setdefault(t, {"sm": 0, "bm": 0, "mfp": 0, "mfm": 0})
        if row["channel"] == "mf_plus":
            tdata[t]["mfp"] += row["mf"] or 0
        elif row["channel"] == "mf_minus":
            tdata[t]["mfm"] += abs(row["mf"] or 0)

    gains = get_gains_batch(all_tickers, date_from, date_to)

    sectors = []
    for name, members in SECTORS.items():
        sm  = sum(tdata.get(t, {}).get("sm",  0) for t in members)
        bm  = sum(tdata.get(t, {}).get("bm",  0) for t in members)
        mfp = sum(tdata.get(t, {}).get("mfp", 0) for t in members)
        mfm = sum(tdata.get(t, {}).get("mfm", 0) for t in members)
        gvals = [gains.get(t, {}).get("gain") for t in members if gains.get(t, {}).get("gain") is not None]
        sectors.append({
            "name":         name,
            "sm_val":       round(sm,  2),
            "bm_val":       round(bm,  2),
            "cm":           round(sm - bm, 2),
            "mf_plus":      round(mfp, 2) if mfp else None,
            "mf_minus":     round(mfm, 2) if mfm else None,
            "net_mf":       round(mfp - mfm, 2) if (mfp or mfm) else None,
            "gain_pct":     round(sum(gvals) / len(gvals), 2) if gvals else None,
            "ticker_count": len(members),
        })

    sectors.sort(key=lambda x: x["cm"], reverse=True)
    return jsonify({"sectors": sectors, "date_from": date_from, "date_to": date_to})
