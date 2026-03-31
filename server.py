#!/usr/bin/env python3
import json, os, sqlite3, time, requests
from pathlib import Path
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder=".")

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", str(BASE_DIR))) / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH  = DATA_DIR / "trading.db"
PORT     = int(os.environ.get("PORT", 5010))
COINGECKO = "https://api.coingecko.com/api/v3"
_cache = {"coins":[], "ts":0}

def get_db():
    if not DB_PATH.exists(): return None
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; return conn

def fetch_prices():
    now = time.time()
    if now - _cache["ts"] < 120: return _cache["coins"]
    try:
        r = requests.get(f"{COINGECKO}/coins/markets", params={
            "vs_currency":"usd","order":"market_cap_desc","per_page":50,
            "page":1,"sparkline":"false","price_change_percentage":"24h,7d"
        }, timeout=12)
        r.raise_for_status(); _cache["coins"] = r.json(); _cache["ts"] = now
    except Exception as e: print("CoinGecko:", e)
    return _cache["coins"]

@app.route("/api/status")
def api_status():
    conn = get_db()
    if not conn: return jsonify({"db":False,"message":"DB not found"})
    c = conn.cursor()
    c.execute("SELECT ts,regime,capital,cash,gross_exposure,realized_pnl FROM portfolio ORDER BY ts DESC LIMIT 1")
    row = c.fetchone(); conn.close()
    if not row: return jsonify({"db":True,"message":"No data yet"})
    return jsonify({"db":True,"last_cycle":row["ts"],"regime":row["regime"],
        "capital":row["capital"],"cash":row["cash"],
        "gross_exposure":row["gross_exposure"],"realized_pnl":row["realized_pnl"],"starting_capital":100000})

@app.route("/api/positions")
def api_positions():
    conn = get_db()
    if not conn: return jsonify([])
    c = conn.cursor(); c.execute("SELECT * FROM positions ORDER BY opened_at DESC LIMIT 50")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return jsonify(rows)

@app.route("/api/decisions")
def api_decisions():
    conn = get_db()
    if not conn: return jsonify([])
    c = conn.cursor()
    c.execute("SELECT ts,symbol,decision,entry_price,stop_price,target_price,position_size_usd,risk_usd,reason,confidence FROM decisions ORDER BY ts DESC LIMIT 30")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return jsonify(rows)

@app.route("/api/portfolio_history")
def api_portfolio_history():
    conn = get_db()
    if not conn: return jsonify([])
    c = conn.cursor()
    c.execute("SELECT ts,capital,cash,gross_exposure,realized_pnl,regime FROM portfolio ORDER BY ts DESC LIMIT 200")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return jsonify(list(reversed(rows)))

@app.route("/api/prices")
def api_prices(): return jsonify(fetch_prices())

@app.route("/health")
def health(): return jsonify({"status":"ok"})

@app.route("/")
def index(): return send_from_directory(".", "dashboard.html")

if __name__ == "__main__":
    print(f"\n  Crypto Monitor — port {PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
