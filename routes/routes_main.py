"""
routes_main.py — Blueprint: /, /hub, /chart, /flow, /sector pages
RULE: Routing + render only. Zero business logic or calculations here.
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, request, jsonify

from core.auth import is_authed, login, logout as auth_logout
from config import WIB
from core.db import fetchone, get_db
from data.price_fetch import fetch_gain_range

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
    today = datetime.now(WIB).strftime("%d-%m-%Y")
    gain_pct, price = fetch_gain_range("^JKSE", today, today)
    return jsonify({"gain_pct": gain_pct, "price": price})
