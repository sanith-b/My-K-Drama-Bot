from flask import Flask
import threading
import time
import requests
import os

SELF_URL = "https://auto-filter-bot-v.koyeb.app"

app = Flask(__name__)

# --- Your normal app routes ---
@app.route("/")
def home():
    return "Hello from Koyeb!"

@app.route("/ping")
def ping():
    return "pong", 200


# --- Self-pinging function ---
def keep_alive():
    while True:
        try:
            url = os.environ.get("SELF_URL")  # Set this in Koyeb environment vars
            if url:
                requests.get(f"{url}/ping")
                print(f"[KeepAlive] Pinged {url}/ping")
        except Exception as e:
            print(f"[KeepAlive Error] {e}")
        time.sleep(300)  # wait 5 minutes


# --- Start self-pinging in a separate thread ---
if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
