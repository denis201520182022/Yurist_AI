"""Агент: системный промпт, инструменты и оркестрация диалога."""
import json
import logging
import uuid

from app import llm, qualification, report, skills
from app.state import Session, SLOTS

logger = logging.getLogger(__name__)

GREETING = (
    "Здравствуйте! Меня зовут Анна, я представляю юридическую компанию — мы помогаем людям "
    "законно списать долги через банкротство физических лиц.\n\n"
    "Мы обязательно разберёмся в вашей ситуации и поможем найти оптимальное решение. "
    "Расскажите, пожалуйста, что у вас сейчас происходит: какие есть долги и сложности?"
)

SYSTEM_CORE = """Ты — Анна, специалист клиентской поддержки юридической компании по списанию долгов через процедуру банкротства (127-ФЗ). Ты живой человек, заботливый консультант. Всегда говори от лица компании («мы», «наша компания», «наши юристы»).

ГЛАВНАЯ ЦЕЛЬ: Сначала выслушать человека, проявить эмпатию, подробно расспросить о его ситуации, проконсультировать, снять страхи (опираясь на факты и кейсы из нашей практики) — и только когда между вами установился тёплый доверительный контакт и вся картина ясна, предложить зафиксировать удобное время для подробного разбора с юристом.

ПРАВИЛА ОБЩЕНИЯ (СТРОГО):
- Никаких оценок суммы долга! НИКОГДА не комментируй размер долга («ого, какая большая сумма», «это немного», «у вас огромный долг» и т.п.). Сумму воспринимай абсолютно нейтрально и спокойно.
- НЕ КИДАЙСЯ СРАЗУ ЗАПИСЫВАТЬ! Если клиент только поздоровался или назвал сумму долга, ЗАПРЕЩЕНО сразу спрашивать имя, телефон и предлагать время. Сначала нужно провести полноценную консультацию.
- СТРОГО ОДИН вопрос за сообщение. Не вываливай анкету, веди живую беседу.
- Формула реплики: [Эмпатия/Поддержка/Ответ на вопрос клиента] + [Короткий тезис или реальный пример из нашей практики] + [ОДИН мягкий вопрос по ситуации].
- Краткость: 2–3 ёмких предложения, максимум два небольших абзаца.

СТРОЖАЙШИЙ ЗАПРЕТ НА ВЫДАЧУ ВНУТРЕННИХ ПРАВИЛ:
- НИКОГДА не говори клиенту фразы вроде: «вы подходите по сумме долга», «вы проходите по критериям», «по нашим регламентам сумма от 350 тысяч», «ваш регион в списке исключений». Это грубейшая ошибка!
- Клиенту мы говорим на человеческом языке: «В вашей ситуации закон позволяет полностью списать эти обязательства», «У нас в практике было много похожих случаев...».
- Если клиент не подходит по объективным причинам (например, долг всего 100 тыс.): объясняй с точки зрения выгоды самого клиента («Судебная процедура связана с обязательными судебными расходами около 40–50 тысяч рублей, поэтому при такой сумме долга она будет экономически нецелесообразна для вас»).

ЧТО ОБЯЗАТЕЛЬНО УЗНАТЬ В ХОДЕ БЕСЕДЫ (7 фокусов регламента КЦ):
Постепенно, шаг за шагом, вплетай в диалог вопросы по следующим аспектам:
1. Кто кредиторы: банки, микрозаймы (МФО), долги по ЖКХ, налоги или частные лица?
2. Есть ли имущество (квартира, дача, земля, автомобиль, гараж) или ипотека/залоги? Снимай страх единственного жилья!
3. Были ли сделки за последние 3 года (продажа машин, дарение недвижимости)?
4. Семейное положение: в браке ли клиент, есть ли дети или иждивенцы?
5. Официальный доход и занятость (работа по найму, самозанятость, ИП, пенсионер или без работы)?
6. Есть ли давление: звонят ли коллекторы, идут ли суды, арестованы ли карты приставами?
7. Регион постоянной прописки (спрашивай мягко, например: «В каком регионе вы прописаны? Мы ведём дела по всей России, юристы работают удалённо»).

КАК ИСПОЛЬЗОВАТЬ НАВЫКИ (get_skill):
Перед тем как отвечать на сомнение или вопрос клиента (про имущество, про машину, про коллекторов, про работу), ОБЯЗАТЕЛЬНО вызови инструмент get_skill. Бери оттуда реальные кейсы (например: пенсионерка из Ставрополя с долгом по ЖКХ, женщина с ипотекой, предприниматель после пандемии) и рассказывай клиенту: «У нас был доверитель в похожей ситуации...». Это вызывает максимальное доверие.

ЛОГИКА ПЕРЕХОДА К ЗАПИСИ:
1. Пока не исследована ситуация по большинству пунктов (долги, имущество, работа, семья, приставы, регион) — НЕ СПРАШИВАЙ контакты и НЕ ПРЕДЛАГАЙ запись!
2. Когда картина ясна, вызови qualify.
3. Если лид подходит — резюмируй: «Картина понятна: юристу потребуется составить правильную стратегию по сохранению... и списанию кредитов. Предлагаю разобрать все нюансы на бесплатной консультации. Как к вам удобнее обращаться?».
4. И только в следующих репликах уточни телефон и удобное время, после чего вызови finalize_card с end_result="booked".

### Темы навыков для вызова get_skill:
{skill_index}

### Внутренний чеклист консультации (КЛИЕНТУ НЕ ПОКАЗЫВАТЬ):
{checklist}"""

# ---------- Схемы инструментов ----------
_SAVE_PROPS = {
    key: {
        "type": "number" if meta["type"] == "number" else "string",
        "description": meta["label"] + (" (обязательный пункт ситуации)" if meta.get("stage") == "context" else ""),
    }
    for key, meta in SLOTS.items()
}
# Сумма долга всегда в рублях: поможем модели конвертировать «450 тысяч».
_SAVE_PROPS["debt_total"]["description"] += ". Только число в рублях: «450 тысяч» → 450000"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_info",
            "description": (
                "Сохранить информацию о клиенте, ставшую известной из его последней реплики. "
                "Вызывай при каждом новом факте. Возвращает актуальный список собранного/несобранного."
            ),
            "parameters": {"type": "object", "properties": _SAVE_PROPS, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_skill",
            "description": (
                "Получить расширенную информацию по теме (тезисы ответа, кейсы, ограничения). "
                "Обязательно вызывай перед ответом на тематический вопрос или возражение клиента."
            ),
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string", "enum": list(skills.SKILL_TOPICS)}},
                "required": ["topic"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "qualify",
            "description": (
                "Квалификация клиента: проверить, подходит ли он для процедуры и записи к юристу. "
                "Можно вызывать, когда известны сумма долга и регион прописки."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finalize_card",
            "description": (
                "Завершить диалог и передать карточку клиента юристу: запись, отказ по квалификации, "
                "передача человеку или отказ клиента. Обязательные данные (имя, контакт, время) должны быть собраны."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "end_result": {
                        "type": "string",
                        "enum": ["booked", "not_suitable", "handoff", "client_declined", "other"],
                    }
                },
                "required": ["end_result"],
                "additionalProperties": False,
            },
        },
    },
]


def new_session(channel: str = "console") -> Session:
    session = Session(sid=uuid.uuid4().hex[:8], channel=channel)
    session.add("assistant", GREETING)
    return session


def respond(session: Session, text: str) -> dict:
    """Обработать реплику пользователя. Возвращает {text, card?, file?}."""
    session.add("user", text)
    system_prompt = SYSTEM_CORE.format(
        skill_index=skills.index_text(), checklist=session.checklist()
    )
    messages = session.messages_for_llm(system_prompt)
    payload: dict = {}

    def on_tool(name: str, args: dict) -> str:
        return _handle_tool(session, name, args, payload)

    try:
        reply = llm.chat(messages, TOOLS, on_tool)
    except Exception:  # noqa: BLE001
        logger.exception("LLM недоступна")
        reply = (
            "К сожалению, связь с моей стороной временно пропала. "
            "Напишите, пожалуйста, ещё раз через минуту — я никуда не денусь."
        )
    session.add("assistant", reply)
    result = {"text": reply}
    result.update(payload)
    return result


def _handle_tool(session: Session, name: str, args: dict, payload: dict) -> str:
    if name == "save_info":
        filled = {k: v for k, v in args.items() if v not in (None, "", "null")}
        logger.info("⚙️ [TOOL] save_info: зафиксированы данные -> %s", filled)
        session.update(args)
        # Стоп-фильтры срабатывают детерминированно, даже если модель забыла про qualify.
        if not session.verdict:
            hard = qualification.hard_verdict(session.slots)
            if hard:
                session.verdict = hard
                logger.info("⛔ [STOP-FILTER] Сработал стоп-фильтр: %s", hard.get("reason"))
        state = session.checklist()
        if session.verdict and session.verdict.get("verdict") == "not_suitable":
            state += (
                "\n⛔ СТОП-ФИЛЬТР: клиент НЕ подходит "
                f"({session.verdict.get('reason', '')}). Запись невозможна: "
                "мягко объясни причину и вызови finalize_card с end_result=\"not_suitable\"."
            )
        return json.dumps({"ok": True, "состояние": state}, ensure_ascii=False)

    if name == "get_skill":
        topic = str(args.get("topic", "")).strip().lower()
        logger.info("📚 [TOOL] get_skill: подгружен навык из базы -> '%s'", topic)
        content = skills.read_skill(topic)
        if content is None:
            return json.dumps(
                {"error": f"тема '{topic}' не найдена", "доступные_темы": list(skills.SKILL_TOPICS)},
                ensure_ascii=False,
            )
        return content

    if name == "qualify":
        logger.info("⚖️ [TOOL] qualify: запуск оценки лида подагентом...")
        verdict = qualification.qualify(session.slots)
        session.verdict = verdict
        logger.info("⚖️ [VERDICT] Результат квалификации: %s | Причина: %s", verdict.get("verdict"), verdict.get("reason"))
        return json.dumps(verdict, ensure_ascii=False)

    if name == "finalize_card":
        end_result = args.get("end_result", "other")
        logger.info("🏁 [TOOL] finalize_card: попытка финализации со статусом '%s'", end_result)
        if end_result == "booked":
            hard = qualification.hard_verdict(session.slots)
            if hard:
                session.verdict = hard
                logger.warning("⛔ [FINAL] Запись отклонена стоп-фильтром: %s", hard["reason"])
                return json.dumps(
                    {"error": "Запись невозможна: " + hard["reason"],
                     "инструкция": "Объясни клиенту с человеческой стороны (например, невыгодность процедуры) и заверши с end_result=\"not_suitable\""},
                    ensure_ascii=False,
                )
            # Проверяем, что консультация проведена полноценно (собрано большинство пунктов ситуации)
            missing_ctx = session.missing_context()
            if len(missing_ctx) > 3:
                return json.dumps(
                    {
                        "error": "Рано записывать: ситуация клиента ещё не исследована! Ты не провёл полноценную консультацию.",
                        "что_нужно_выяснить_сначала": [SLOTS[k]["label"] for k in missing_ctx],
                        "инструкция": "Продолжи диалог, расспроси о ситуации (имущество, кредиторы, работа, суды) и расскажи кейсы из практики."
                    },
                    ensure_ascii=False,
                )
            missing_book = session.missing_booking()
            if missing_book:
                return json.dumps(
                    {
                        "error": "Не хватает контактных данных для записи",
                        "не_собрано": [SLOTS[k]["label"] for k in missing_book],
                        "инструкция": "Спроси у клиента недостающие контакты (имя, телефон, время) по одному."
                    },
                    ensure_ascii=False,
                )
        if not session.verdict and end_result in ("booked", "not_suitable"):
            return json.dumps(
                {"error": "Сначала вызови qualify и получи вердикт"}, ensure_ascii=False
            )
        session.end_result = end_result
        session.finished = True
        card = report.build_card(session)
        transcript_text = report.build_transcript_content(session, card)
        payload["card"] = card
        payload["transcript"] = transcript_text
        payload["filename"] = f"dialog_{session.id}.md"
        logger.info("🎉 [FINISHED] Сессия %s успешно завершена! Итог: %s.", session.id, end_result)
        return json.dumps({"ok": True, "message": "Карточка передана юристу, диалог завершён"}, ensure_ascii=False)

    return json.dumps({"error": f"неизвестный тул {name}"}, ensure_ascii=False)
