"""
routes_journal.py — Blueprint: /journal, /api/journal/*
RULE: Routing only. All trade journal logic in journal.py.
"""
from flask import Blueprint, render_template, jsonify, request, redirect

from core.auth import is_authed
from core.db import get_db, transaction
from data.journal import open_position, close_position, get_journal_list, get_trade_detail

bp_journal = Blueprint("journal", __name__)


@bp_journal.route("/journal")
def journal_page():
    if not is_authed():
        return redirect("/")
    return render_template("journal.html")


@bp_journal.route("/api/journal")
def journal_list():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_journal_list(get_db()))


@bp_journal.route("/api/journal/open", methods=["POST"])
def journal_open():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json()
    if not data or not all(k in data for k in ("ticker", "phase", "date", "price")):
        return jsonify({"error": "ticker, phase, date, price required"}), 400
    conn = get_db()
    with transaction(conn):
        open_position(conn, data["ticker"], data["phase"], data["date"], float(data["price"]))
    return jsonify({"ok": True})


@bp_journal.route("/api/journal/close", methods=["POST"])
def journal_close():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json()
    if not data or not all(k in data for k in ("ticker", "date", "price")):
        return jsonify({"error": "ticker, date, price required"}), 400
    conn = get_db()
    with transaction(conn):
        n = close_position(conn, data["ticker"], data["date"], float(data["price"]), data.get("reason", "manual"))
    return jsonify({"ok": True, "closed": n})


@bp_journal.route("/api/journal/trade-detail")
def trade_detail():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401
    ticker   = request.args.get("ticker", "").upper()
    date_str = request.args.get("date", "")
    if not ticker or not date_str:
        return jsonify({"error": "ticker and date required"}), 400
    detail = get_trade_detail(get_db(), ticker, date_str)
    if not detail:
        return jsonify({"error": "not found"}), 404
    return jsonify(detail)
