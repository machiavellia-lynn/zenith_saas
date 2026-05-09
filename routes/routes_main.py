"""
routes_main.py — Blueprint: /, /hub, /chart, /flow, /sector pages
RULE: Routing + render only. Zero business logic or calculations here.
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, request, jsonify

from core.auth import is_authed, login, logout as auth_logout
from config import WIB, YF_HEADERS
from core.db import fetchone, get_db
from data.price_fetch import fetch_gain_range
import requests

bp_main = Blueprint("main", __name__)


@bp_main.route("/", methods=["GET", "POST"])
def login_page():
    if is_authed():
        return redirect("/hub")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if login(username, password):
            return jsonify({"ok": True})
        return jsonify({"ok": False})
    return render_template("login.html")


@bp_main.route("/logout")
def logout():
    auth_logout()
    return redirect("/")


@bp_main.route("/hub")
def hub():
    if not is_authed():
        return redirect("/")
    return render_template("hub.html")


@bp_main.route("/chart")
def chart_page():
    if not is_authed():
        return redirect("/")
    return render_template("chart.html")


@bp_main.route("/flow")
def flow_page():
    if not is_authed():
        return redirect("/")
    return render_template("flow.html")


@bp_main.route("/api/last-date")
def last_date():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401
    row = fetchone(get_db(),
        "SELECT date FROM eod_summary ORDER BY TO_DATE(date, 'DD-MM-YYYY') DESC LIMIT 1")
    date_str = row["date"].replace("-", "/") if row and row["date"] else None
    return jsonify({"date": date_str})


@bp_main.route("/api/ihsg")
def ihsg():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401
    try:
        resp = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EJKSE",
            headers=YF_HEADERS,
            params={"interval": "1d", "range": "5d"},
            timeout=5,
        )
        result = resp.json().get("chart", {}).get("result", [None])[0]
        if not result:
            return jsonify({"price": None, "gain_pct": None})

        meta = result.get("meta", {})
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")

        gain_pct = None
        if price and prev and prev > 0:
            gain_pct = round((price - prev) / prev * 100, 2)

        return jsonify({
            "price": round(float(price), 2) if price else None,
            "gain_pct": gain_pct,
        })
    except Exception as e:
        return jsonify({"price": None, "gain_pct": None, "error": str(e)})
