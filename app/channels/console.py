"""Консольный канал для тестирования агента без Telegram."""
from app import agent


def _render(payload: dict) -> None:
    print(f"\n🤖 {payload['text']}\n")
    if payload.get("card"):
        print(payload["card"])
    if payload.get("file"):
        print(f"📄 Файл-передача юристу сохранён: {payload['file']}")


def run_console() -> None:
    session = agent.new_session("console")
    print(f"\n🤖 {session.history[-1]['content']}\n")
    print("Команды: /reset — новая сессия, /exit — выход\n")
    while True:
        try:
            text = input("👤> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nПока!")
            break
        if not text:
            continue
        if text.lower() in ("/exit", "/quit"):
            print("Пока!")
            break
        if text.lower() == "/reset":
            session = agent.new_session("console")
            print(f"\n🤖 {session.history[-1]['content']}\n")
            continue
        if session.finished:
            print("Диалог завершён. /reset — начать заново, /exit — выход.")
            continue
        _render(agent.respond(session, text))
        if session.finished:
            print("\n— Диалог завершён. /reset — начать заново, /exit — выход —\n")
