"""Минимальный HTTP-сервер здоровья (Health Check) для Render.com."""
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK: Yurist_AI Bot is running")

    def log_message(self, format, *args):
        # Отключаем спам в консоль при каждом пинге
        pass


def start_health_server(port: int = None) -> None:
    if port is None:
        port = int(os.getenv("PORT", "8080"))

    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("🌐 Health-сервер запущен на порту %d (готов к внешним пингам)", port)
