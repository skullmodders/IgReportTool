import os
import logging
from anticheat import create_verification_app

# ================== CONFIG ==================

PORT = int(os.environ.get("PORT", 8000))
DB_PATH = os.environ.get("DB_PATH", "/data/bot_database.db")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "NeturalPredictorbot")

# ================== LOGGING ==================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.info("🚀 Starting IP Verification Server...")
logging.info(f"📂 DB_PATH: {DB_PATH}")
logging.info(f"🤖 BOT_USERNAME: {BOT_USERNAME}")

# ================== CREATE APP ==================

app = create_verification_app(
    DB_PATH=DB_PATH,
    BOT_USERNAME=BOT_USERNAME
)

# ================== EXTRA ROUTES ==================

@app.route("/debug")
def debug_info():
    return {
        "status": "running",
        "db_path": DB_PATH,
        "bot": BOT_USERNAME,
        "env_vars": list(os.environ.keys())
    }

@app.route("/ping")
def ping():
    return "pong"

# ================== ERROR HANDLING ==================

@app.errorhandler(404)
def not_found(e):
    return {
        "error": "Not Found",
        "message": "Invalid route"
    }, 404

@app.errorhandler(500)
def server_error(e):
    return {
        "error": "Server Error",
        "message": "Something went wrong"
    }, 500

# ================== START ==================

if __name__ == "__main__":
    logging.info(f"🌐 Running on port {PORT}")
    app.run(host="0.0.0.0", port=PORT)
