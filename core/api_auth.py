"""
api_auth.py — Zenith 2.0 External Data API Authentication
RULE: Keys are SHA-256 hashed and looked up in api_keys. The legacy single
      static key from config.API_KEY is still accepted (timing-safe) so
      existing consumers don't break when the multi-key table is empty.
"""
import hashlib
import hmac
from flask import request, jsonify
import config
from core.db import get_db, execute, fetchone


def require_api_key():
    """before_request guard for bp_api. Returns a 401 response on failure, else None."""
    supplied = request.headers.get("X-API-Key") or request.args.get("api_key") or ""
    if not supplied:
        return jsonify({"error": "unauthorized"}), 401

    key_hash = hashlib.sha256(supplied.encode()).hexdigest()
    conn = get_db()
    row = fetchone(conn,
        "SELECT id FROM api_keys WHERE key_hash = %s AND revoked = FALSE", [key_hash])
    if row:
        execute(conn, "UPDATE api_keys SET last_used_at = NOW() WHERE id = %s", [row["id"]])
        conn.commit()
        return None

    if config.API_KEY and hmac.compare_digest(supplied, config.API_KEY):
        return None

    return jsonify({"error": "unauthorized"}), 401
