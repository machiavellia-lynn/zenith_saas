"""
app.py — Zenith 2.0 Entry Point
RULE: Flask init + register blueprints only. Zero business logic here.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from flask import Flask

import config
from routes.routes_main import bp_main
from routes.routes_flow import bp_flow
from routes.routes_sector import bp_sector
from routes.routes_backtest import bp_backtest
from routes.routes_journal import bp_journal
from routes.routes_admin import bp_admin

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.WARNING),
    format="[%(asctime)s] %(name)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET
app.config["SESSION_TYPE"]     = config.SESSION_TYPE
app.config["SESSION_FILE_DIR"] = config.SESSION_DIR
os.makedirs(config.SESSION_DIR, exist_ok=True)

app.register_blueprint(bp_main)
app.register_blueprint(bp_flow)
app.register_blueprint(bp_sector)
app.register_blueprint(bp_backtest)
app.register_blueprint(bp_journal)
app.register_blueprint(bp_admin)

from startup import do_startup
do_startup(app)

if __name__ == "__main__":
    app.run(debug=config.IS_LOCAL, host="0.0.0.0", port=5000)
