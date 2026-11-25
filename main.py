"""Точка входа: python main.py [--tg]"""
import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

# Загружаем переменные окружения до импортов модулей приложения
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)


def main() -> None:
    # Настраиваем лаконичный формат консольного лога
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # Глушим сетевой спам HTTP-запросов к API Telegram и Sberbank
    for noisy in ("httpx", "httpcore", "gigachat", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="ИИ-агент КЦ: банкротство физлиц")
    parser.add_argument("--tg", action="store_true", help="запустить Telegram-бота (иначе консоль)")
    args = parser.parse_args()

    if args.tg or os.getenv("RUN_TG", "").lower() in ("true", "1"):
        # Запускаем лёгкий HTTP health-сервер для Render и пингеров (Keep-Alive)
        from app.server import start_health_server
        start_health_server()

        from app.channels.telegram_bot import run_bot

        run_bot()
    else:
        from app.channels.console import run_console

        run_console()


if __name__ == "__main__":
    main()
