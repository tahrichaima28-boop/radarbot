import json
import requests
import ssl
import socket
from datetime import datetime
import os

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL_FILE = "file.json"

def load_urls(file_path):
    """Load URLs from JSON file"""
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f" Error: File {file_path} not found!")
        return []
    except json.JSONDecodeError:
        print(f" Error: File {file_path} is not valid JSON!")
        return []

def check_url_status(url):
    """Check URL status code"""
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
    """Check SSL certificate expiry date"""
    try:
        if not url.startswith("https://"):
            return None
        domain = url.replace("https://", "").split("/")[0]
        context = ssl.create_default_context()
        sock = socket.create_connection((domain, 443), timeout=10)
        ssock = context.wrap_socket(sock, server_hostname=domain)
        cert = ssock.getpeercert()
        expire_date_str = cert['notAfter']
        expire_date = datetime.strptime(expire_date_str, "%b %d %H:%M:%S %Y GMT")
        days_left = (expire_date - datetime.utcnow()).days
        ssock.close()
        sock.close()
        return days_left
    except:
        return None

def get_status_text(status_code, status_type):
    """Convert status code to human-readable text"""
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
    """Send message to Telegram"""
    try:
        # 🚨 Fixed: removed space in URL!
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except:
        return False

def create_alert_message(url, status_code, status_type, ssl_days=None):
    """Create alert message with SSL info if available"""
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

def main():
    print(" Starting URL monitoring system...")
    print("=" * 50)
    urls = load_urls(URL_FILE)
    if not urls:
        print(" No URLs to check. Please add URLs to file.json")
        return
    print(f" Found {len(urls)} URL(s) to check")
    print("=" * 50)
    for url in urls:
        print(f" Checking: {url}")
        status_code, status_type = check_url_status(url)
        ssl_days = None
        if url.startswith("https://"):
            ssl_days = check_ssl_expiry(url)
            if ssl_days is not None:
                print(f"    SSL expires in: {ssl_days} days")
            else:
                print("    Could not check SSL (connection failed)")
        if status_code != 200:
            print(f" SERVER PROBLEM: {status_type}")
            message = create_alert_message(url, status_code, status_type, ssl_days)
            print(" Alert Message:")
            print(message.replace("**", ""))
            print(" Sending to Telegram...", end="")
            if send_telegram_message(message):
                print("  Sent")
            else:
                print("  Failed")
        else:
            print(f" Site is working normally")
        print("-" * 50)
    print("\n Monitoring complete!")

# ================================
# 🌐 WEB SERVER FOR RENDER + CRON
# ================================
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/run':
            try:
                main()
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write("✅ Monitor executed successfully")
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"❌ Error: {str(e)}".encode())
        elif self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), RequestHandler)
    print(f"🚀 Web server running on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    # If running on Render (web mode)
    if os.getenv("RENDER_EXTERNAL_URL"):
        run_web_server()
    else:
        # Run once (local testing)
        main()