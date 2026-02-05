import json
import requests
import ssl
import socket
from datetime import datetime, timedelta
import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# 🔒 Load secrets
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL_FILE = "file.json"
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL", "10"))  # Default: every 10 mins

# ================================
# TELEGRAM & MONITORING LOGIC (same as before)
# ================================

def load_urls(file_path):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading URLs: {e}")
        return []

def check_url_status(url):
    try:
        response = requests.get(url, timeout=10)
        return response.status_code, "success"
    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, "connection_error"
    except Exception as e:
        return None, f"error: {str(e)}"

def check_ssl_expiry(url):
    if not url.startswith("https://"):
        return None
    try:
        domain = url.replace("https://", "").split("/")[0]
        context = ssl.create_default_context()
        sock = socket.create_connection((domain, 443), timeout=10)
        ssock = context.wrap_socket(sock, server_hostname=domain)
        cert = ssock.getpeercert()
        expire_date = datetime.strptime(cert['notAfter'], "%b %d %H:%M:%S %Y GMT")
        days_left = (expire_date - datetime.utcnow()).days
        ssock.close()
        sock.close()
        return days_left
    except:
        return None

def get_status_text(status_code, status_type):
    if status_code == 200:
        return "200 OK"
    elif status_code == 502:
        return "502 Bad Gateway"
    elif status_code == 503:
        return "503 Service Unavailable"
    elif status_code == 504:
        return "504 Gateway Timeout"
    elif status_code == 404:
        return "404 Not Found"
    elif status_code == 500:
        return "500 Internal Server Error"
    elif status_code is None:
        if status_type == "timeout":
            return "Timeout"
        elif status_type == "connection_error":
            return "Connection Failed"
        else:
            return "Error"
    else:
        return f"{status_code}"

def send_telegram_message(message):
    try:
        # ✅ FIXED: NO SPACE after /bot
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=data, timeout=10)
        print(f"📤 Telegram response: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

def create_alert_message(url, status_code, status_type, ssl_days=None):
    current_time = datetime.now().strftime("%Y-%m-%d : %H:%M")
    status_text = get_status_text(status_code, status_type)
    message = f"""🚨 **ALERT: Server Down!**

🌐 **Site:** {url}

🛠 **Status Code:** {status_text}

⏰ **Time:** {current_time}"""
    if ssl_days is not None and ssl_days <= 7:
        message += f"""

⚠️ **Warning: SSL Certificate**

📅 **Expires in:** {ssl_days} days!"""
    return message

def run_monitor():
    """Run one full monitoring cycle"""
    print("🔍 Starting URL monitoring cycle...")
    urls = load_urls(URL_FILE)
    if not urls:
        print("⚠️ No URLs found in file.json")
        return

    for url in urls:
        print(f" Checking: {url}")
        status_code, status_type = check_url_status(url)
        ssl_days = check_ssl_expiry(url) if url.startswith("https://") else None

        if status_code != 200:
            message = create_alert_message(url, status_code, status_type, ssl_days)
            print(" Sending alert to Telegram...")
            if send_telegram_message(message):
                print(" ✅ Alert sent")
            else:
                print(" ❌ Failed to send alert")
        else:
            print(f" ✅ {url} is OK")
    print("✅ Monitoring cycle complete.\n")

# ================================
# HEALTH CHECK SERVER (only for uptime)
# ================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🟢 Health server running on port {port}")
    server.serve_forever()

# ================================
# MAIN LOOP
# ================================

if __name__ == "__main__":
    # Start health server in background
    threading.Thread(target=start_health_server, daemon=True).start()

    # Run first check immediately
    run_monitor()

    # Then run every N minutes
    while True:
        print(f"😴 Sleeping for {CHECK_INTERVAL_MINUTES} minutes...")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)
        run_monitor()git