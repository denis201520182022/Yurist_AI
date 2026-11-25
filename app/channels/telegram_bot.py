"""Telegram-канал: long-polling через Bot API (httpx), кнопка сброса сессии.

По завершении сценария в чат уходят карточка клиента и файл-передача (.md).
"""
import logging
import os
import time

import httpx

from app import agent

logger = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"

_sessions: dict[int, object] = {}


def _allowed_chats() -> set:
    raw = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    return {int(x) for x in raw.split(",") if x.strip()}


class Telegram:
    def __init__(self, token: str):
        self.token = token
        self.client = httpx.Client(timeout=60)

    def call(self, method: str, **kwargs):
        resp = self.client.post(API.format(token=self.token, method=method), json=kwargs)
        data = resp.json()
        if not data.get("ok"):
            logger.error("TG %s: %s", method, data)
        return data.get("result")

    def set_commands(self):
        """Устанавливает слэш-команды в системное меню Telegram."""
        commands = [
            {"command": "start", "description": "Начать консультацию"},
            {"command": "reset", "description": "Новая консультация (сброс)"},
        ]
        self.call("setMyCommands", commands=commands)

    def send_chat_action(self, chat_id: int, action: str = "typing"):
        """Показывает статус 'печатает...' в верхней части чата."""
        self.call("sendChatAction", chat_id=chat_id, action=action)

    def send_text(self, chat_id: int, text: str):
        for i in range(0, len(text), 3900):  # лимит Telegram 4096 символов
            self.call("sendMessage", chat_id=chat_id, text=text[i : i + 3900])

    def send_file(self, chat_id: int, path: str):
        with open(path, "rb") as fh:
            self.client.post(
                API.format(token=self.token, method="sendDocument"),
                data={"chat_id": chat_id},
                files={"document": (path.split("/")[-1], fh, "text/markdown")},
                timeout=60,
            )


def run_bot() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Не задан TELEGRAM_BOT_TOKEN в .env")
    tg = Telegram(token)
    tg.set_commands()
    allowed = _allowed_chats()
    offset = 0
    me = tg.call("getMe")
    print(f"Бот @{(me or {}).get('username')} успешно запущен в Telegram.")

    while True:
        try:
            updates = tg.call("getUpdates", offset=offset + 1 if offset else None, timeout=30) or []
        except Exception as e:  # noqa: BLE001
            time.sleep(3)
            continue

        for upd in updates:
            offset = max(offset, upd["update_id"])
            chat_id, text = None, None
            if "message" in upd and upd["message"].get("text"):
                msg = upd["message"]
                chat_id, text = msg["chat"]["id"], msg["text"]

            if chat_id is None:
                continue
            if allowed and chat_id not in allowed:
                tg.send_text(chat_id, "Доступ ограничен.")
                continue

            try:
                _handle(tg, chat_id, text)
            except Exception:  # noqa: BLE001
                logger.exception("Ошибка обработки сообщения")
                tg.send_text(chat_id, "Произошла временная заминка. Попробуйте написать ещё раз.")


def _handle(tg: Telegram, chat_id: int, text: str | None) -> None:
    clean_text = (text or "").strip()
    if clean_text.lower() in ("/start", "/reset"):
        session = agent.new_session("telegram")
        _sessions[chat_id] = session
        tg.send_text(chat_id, session.history[-1]["content"])
        return

    session = _sessions.get(chat_id)
    if session is None or session.finished:
        session = agent.new_session("telegram")
        _sessions[chat_id] = session
        tg.send_text(chat_id, session.history[-1]["content"])
        if not clean_text:
            return

    # Отображаем индикатор «печатает...» во время генерации ответа LLM
    tg.send_chat_action(chat_id, "typing")
    payload = agent.respond(session, clean_text)
    tg.send_text(chat_id, payload["text"])
    if payload.get("card"):
        tg.send_text(chat_id, payload["card"])
    if payload.get("file"):
        tg.send_file(chat_id, payload["file"])
