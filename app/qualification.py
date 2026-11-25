"""Квалификация лида: жёсткие фильтры кодом + вердикт подагента-LLM."""
import json
import logging

from app import llm, skills

logger = logging.getLogger(__name__)

MIN_DEBT = 350_000
STOP_REGION_MARKERS = ("чечен", "днр", "лнр", "владимирск")


def hard_verdict(slots: dict) -> dict | None:
    """Детерминированные стоп-фильтры. None — продолжаем оценку подагентом."""
    debt = slots.get("debt_total")
    region = str(slots.get("region", "")).lower()
    if isinstance(debt, (int, float)) and debt < MIN_DEBT:
        return {
            "verdict": "not_suitable",
            "reason": f"Сумма долга {debt:,.0f} ₽ ниже порога 350 000 ₽ — процедура экономически нецелесообразна.".replace(",", " "),
            "complexity_flags": [],
            "lawyer_note": "",
        }
    if any(marker in region for marker in STOP_REGION_MARKERS):
        return {
            "verdict": "not_suitable",
            "reason": "Регион прописки вне зоны работы компании.",
            "complexity_flags": [],
            "lawyer_note": "",
        }
    return None


def qualify(slots: dict) -> dict:
    """Вызывается тулом qualify. Сначала жёсткие фильтры, затем LLM-подагент."""
    if slots.get("debt_total") in (None, "") or not isinstance(slots.get("debt_total"), (int, float)):
        return {
            "verdict": "need_more_info",
            "reason": "Не известна точная сумма долга",
            "missing": ["debt_total"],
        }
    if not slots.get("region"):
        return {
            "verdict": "need_more_info",
            "reason": "Неизвестен регион прописки",
            "missing": ["region"],
        }

    hard = hard_verdict(slots)
    if hard:
        return hard

    rules = skills.read_qualification_rules()
    data = json.dumps(slots, ensure_ascii=False, indent=2)
    prompt = (
        "Оцени лида по правилам и данным карточки.\n\n"
        f"ПРАВИЛА:\n{rules}\n\n"
        f"КАРТОЧКА КЛИЕНТА:\n{data}\n\n"
        "Верни только JSON."
    )
    try:
        text = llm.chat([{"role": "user", "content": prompt}])
        verdict = _parse_verdict(text)
    except Exception:  # noqa: BLE001
        logger.exception("Подагент квалификации упал — считаю подходящим (жёсткие фильтры пройдены)")
        verdict = {
            "verdict": "suitable",
            "reason": "Жёсткие фильтры пройдены, подагент недоступен.",
            "complexity_flags": [],
            "lawyer_note": "",
        }
    return verdict


def _parse_verdict(text: str) -> dict:
    """Извлекает JSON-вердикт из ответа подагента (допускает обрамление ```)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(cleaned[start : end + 1])
            if isinstance(data, dict) and data.get("verdict"):
                return {
                    "verdict": data["verdict"],
                    "reason": str(data.get("reason", "")),
                    "complexity_flags": list(data.get("complexity_flags") or []),
                    "lawyer_note": str(data.get("lawyer_note", "")),
                }
        except json.JSONDecodeError:
            pass
    logger.warning("Не распарсился вердикт: %.200s", text)
    return {
        "verdict": "suitable",
        "reason": f"Формат вердикта не распознан, принят безопасный дефолт. Сырой ответ: {text[:200]}",
        "complexity_flags": [],
        "lawyer_note": "",
    }
