from core import bot, ADMIN_ID, FORCE_JOIN_CHANNELS, NOTIFICATION_CHANNEL
import handlers  # noqa: F401 - registers all bot handlers on import
import time
import requests

print("=" * 50)
print("  UPI Loot Pay Bot Starting...")
print(f"  Admin ID: {ADMIN_ID}")
print(f"  Force Join: {FORCE_JOIN_CHANNELS}")
print(f"  Notification Channel: {NOTIFICATION_CHANNEL}")
print("=" * 50)

while True:
    try:
        print("Bot is polling...")
        bot.infinity_polling(
            timeout=30,
            long_polling_timeout=20,
            allowed_updates=["message", "callback_query"],
            skip_pending=True
        )
    except requests.exceptions.RequestException as e:
        print(f"Polling network error: {e}")
        time.sleep(5)
    except Exception as e:
        print(f"Polling error: {e}")
        time.sleep(5)
