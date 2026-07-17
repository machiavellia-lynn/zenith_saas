"""
api_auth.py — Zenith 2.0 External Data API Authentication
RULE: Single static key from config.API_KEY. Timing-safe comparison only.
"""
import hmac
from flask import request, jsonify
import config


def require_api_key():
    """before_request guard for bp_api. Returns a 401 response on failure, else None."""
    supplied = request.headers.get("X-API-Key") or request.args.get("api_key") or ""
    if not config.API_KEY or not hmac.compare_digest(supplied, config.API_KEY):
        return jsonify({"error": "unauthorized"}), 401
    return None
