"""Состояние диалога: слоты клиента, история реплик, вердикт квалификации."""
from datetime import datetime

# Ключевые слоты. required — обязательные для квалификации/записи.
SLOTS = {
    "debt_total": {"label": "Сумма долга, ₽", "required": True, "type": "number"},
    "region": {"label": "Регион прописки", "required": True, "type": "string"},
    "name": {"label": "Имя клиента", "required": True, "type": "string"},
    "contact": {"label": "Контакт (телефон/ник)", "required": True, "type": "string"},
    "preferred_time": {"label": "Удобное время консультации", "required": True, "type": "string"},
    "creditors": {"label": "Перед кем долги", "required": False, "type": "string"},
    "property": {"label": "Имущество", "required": False, "type": "string"},
    "mortgage": {"label": "Ипотека", "required": False, "type": "string"},
    "collateral": {"label": "Залоговое имущество", "required": False, "type": "string"},
    "deals": {"label": "Сделки за последние 3 года", "required": False, "type": "string"},
    "family": {"label": "Семья, дети, иждивенцы", "required": False, "type": "string"},
    "income": {"label": "Доход и обязательные расходы", "required": False, "type": "string"},
    "employment": {"label": "Занятость (работа/ИП/самозанятый/директор)", "required": False, "type": "string"},
    "pressure": {"label": "Суды, приставы, коллекторы, аресты", "required": False, "type": "string"},
    "notes": {"label": "Прочее / комментарии", "required": False, "type": "string"},
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

    def missing_required(self) -> list:
        return [k for k, m in SLOTS.items() if m["required"] and not self.slots.get(k)]

    def checklist(self) -> str:
        """Служебный блок «собрано / не собрано» для системного промпта."""
        filled, miss_req, miss_opt = [], [], []
        for key, meta in SLOTS.items():
            value = self.slots.get(key)
            if value not in (None, ""):
                filled.append(f"{meta['label']}: {value}")
            elif meta["required"]:
                miss_req.append(meta["label"])
            else:
                miss_opt.append(meta["label"])
        lines = [
            "СОБРАНО: " + ("; ".join(filled) if filled else "ничего"),
            "НЕ СОБРАНО (обязательно): " + (", ".join(miss_req) if miss_req else "— всё есть"),
            "НЕ СОБРАНО (дополнительно, по ситуации): " + (", ".join(miss_opt) if miss_opt else "—"),
        ]
        if self.verdict:
            lines.append(f"ВЕРДИКТ КВАЛИФИКАЦИИ: {self.verdict}")
        else:
            lines.append("ВЕРДИКТ КВАЛИФИКАЦИИ: ещё не запрошен")
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
