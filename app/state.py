"""Состояние диалога: слоты клиента, история реплик, вердикт квалификации."""
from datetime import datetime

# Слоты клиента.
# required_context — ключевые аспекты ситуации, которые консультант ОБЯЗАН выяснить и обсудить ДО предложения записи.
# required_booking — контакты, собираемые ТОЛЬКО в самом конце, когда доверие выстроено и клиент согласен на встречу.
SLOTS = {
    # 7 фокусов методички КЦ (обязательно выяснить в ходе консультации):
    "debt_total": {"label": "Сумма долга, ₽", "stage": "context", "type": "number"},
    "creditors": {"label": "Перед кем долги (банки/МФО/ЖКХ/налоги)", "stage": "context", "type": "string"},
    "property": {"label": "Имущество (жильё/авто/залоги/ипотека)", "stage": "context", "type": "string"},
    "deals": {"label": "Сделки с имуществом за последние 3 года", "stage": "context", "type": "string"},
    "family": {"label": "Семья, дети, брак, иждивенцы", "stage": "context", "type": "string"},
    "income": {"label": "Доход и занятость (работа/ИП/самозанятый)", "stage": "context", "type": "string"},
    "pressure": {"label": "Аресты, приставы, суды, коллекторы", "stage": "context", "type": "string"},
    "region": {"label": "Регион прописки", "stage": "context", "type": "string"},

    # Запись к юристу (собираются строго в финале):
    "name": {"label": "Имя клиента", "stage": "booking", "type": "string"},
    "contact": {"label": "Контакт (телефон/ник)", "stage": "booking", "type": "string"},
    "preferred_time": {"label": "Удобное время консультации", "stage": "booking", "type": "string"},
    "notes": {"label": "Прочее / заметки", "stage": "optional", "type": "string"},
}


class Session:
    def __init__(self, sid: str, channel: str = "console"):
        self.id = sid
        self.channel = channel
        self.slots: dict = {}
        self.history: list = []  # [{"role": "user"|"assistant", "content": str, "ts": str}]
        self.verdict: dict | None = None
        self.end_result: str | None = None
        self.finished = False
        self.created_at = datetime.now()

    # ---------- слоты ----------
    def update(self, fields: dict) -> None:
        for key, meta in SLOTS.items():
            value = fields.get(key)
            if value in (None, "", "null"):
                continue
            if meta["type"] == "number":
                try:
                    value = float(str(value).replace(" ", "").replace("₽", ""))
                except (TypeError, ValueError):
                    value = str(value)
            self.slots[key] = value

    def missing_context(self) -> list:
        """Какие пункты ситуации клиента из методички ещё не исследованы."""
        return [k for k, m in SLOTS.items() if m["stage"] == "context" and not self.slots.get(k)]

    def missing_booking(self) -> list:
        """Контакты для записи."""
        return [k for k, m in SLOTS.items() if m["stage"] == "booking" and not self.slots.get(k)]

    def is_context_ready(self) -> bool:
        """Готова ли картина ситуации для перехода к предложению записи."""
        # Основные: сумма, кредиторы, имущество, регион + хотя бы большинство остальных пунктов
        missing = self.missing_context()
        return len(missing) <= 1 and bool(self.slots.get("debt_total")) and bool(self.slots.get("region"))

    def checklist(self) -> str:
        """Служебный блок для системного промпта."""
        filled, miss_ctx, miss_book = [], [], []
        for key, meta in SLOTS.items():
            value = self.slots.get(key)
            if value not in (None, ""):
                filled.append(f"{meta['label']}: {value}")
            elif meta["stage"] == "context":
                miss_ctx.append(meta["label"])
            elif meta["stage"] == "booking":
                miss_book.append(meta["label"])

        lines = [
            "ВЫЯСНЕНО О СИТУАЦИИ: " + ("; ".join(filled) if filled else "пока ничего"),
            "ЕЩЁ НЕ УТОЧНЕНО ПО СИТУАЦИИ (спрашивать по очереди, консультируя по ходу): " + (", ".join(miss_ctx) if miss_ctx else "— ситуация исследована полностью!"),
            "КОНТАКТЫ ДЛЯ ЗАПИСИ (спрашивать ТОЛЬКО после разбора ситуации): " + (", ".join(miss_book) if miss_book else "— собраны"),
        ]
        if self.verdict:
            lines.append(f"ВНУТРЕННЯЯ КВАЛИФИКАЦИЯ: {self.verdict.get('verdict')} ({self.verdict.get('reason', '')})")
        else:
            lines.append("ВНУТРЕННЯЯ КВАЛИФИКАЦИЯ: ещё не проводилась")
        return "\n".join(lines)

    # ---------- история ----------
    def add(self, role: str, content: str) -> None:
        self.history.append(
            {"role": role, "content": content, "ts": datetime.now().strftime("%H:%M")}
        )

    def messages_for_llm(self, system_prompt: str) -> list:
        msgs = [{"role": "system", "content": system_prompt}]
        msgs += [{"role": m["role"], "content": m["content"]} for m in self.history]
        return msgs
