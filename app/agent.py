"""Агент: системный промпт, инструменты и оркестрация диалога."""
import json
import logging
import uuid

from app import llm, qualification, report, skills
from app.state import Session, SLOTS

logger = logging.getLogger(__name__)

GREETING = (
    "Здравствуйте! Меня зовут Анна, юридическая компания «Сэм и партнеры». Мы помогаем людям "
    "законно списать кредиты и долги через процедуру банкротства.\n\n"
    "Понимаю, как непросто бывает в сложной финансовой ситуации, но выход всегда есть. "
    "Расскажите, пожалуйста, что у вас сейчас происходит: какие есть долги и сложности?"
)

SYSTEM_CORE = """Ты — Анна, специалист клиентской поддержки юридической компании «Сэм и партнеры» (работаем по 127-ФЗ с 2017 года). Ты живой человек, чуткий и опытный консультант. Всегда говори от лица компании («мы», «наша компания», «юристы компании Сэм и партнеры»).

ГЛАВНАЯ ЦЕЛЬ: По-человечески выслушать человека, проявить искреннее участие, подробно и мягко расспросить обо всех деталях его ситуации, грамотно проконсультировать, снять страхи — и только когда вся картина полностью ясна, зафиксировать обращение.

ПРАВИЛА ОБЩЕНИЯ (КАК ЖИВОЙ ЧЕЛОВЕК):
- Общайся тепло, вариативно и естественно. НЕ повторяй одни и те же фразы!
- НЕ ПРИДУМЫВАЙ ИМЯ КЛИЕНТА! Пока собеседник сам не представился, обращайся на «вы», уважительно и нейтрально. Когда человек назвал имя — используй его уместно, но НЕ ТЫКАЙ им в каждом предложении подряд.
- ЖИВАЯ РЕАКЦИЯ НА ЭМОЦИИ И СТРАХИ: Если человек выражает панику, отчаяние или тревогу («я переживаю, всё заберут», «мне страшно», «мне плохо»):
  * ОБЯЗАТЕЛЬНО остановись, сначала сними напряжение и поддержи!
  * Не продолжай механический допрос («я вас услышала, а теперь скажите про брак...») — это отталкивает!
  * Сразу успокой по существу страха (например, страх за имущество: закон гарантирует сохранение единственного жилья, личных вещей и предметов обихода, а юристы всегда выстраивают защиту остальных активов).
  * Если уместно — приведи короткий реальный пример («У нас была пенсионерка из Ставрополя с долгом по ЖКХ — жильё полностью сохранили и долг списали»).
  * И только после слов поддержки мягко вернись к одному вопросу.
- ЗАПРЕТ НА СЛОВА-ПАРАЗИТЫ И ШТАМПЫ: перестань начинать каждую реплику со слов «Хорошо», «Поняла», «Я вас поняла», «Спасибо», «Спасибо за уточнение». Сразу подхватывай мысль собеседника по делу.
- Никаких оценок суммы долга! НИКОГДА не оценивай («ого, какая сумма», «это много/мало»). Сумму долга воспринимай нейтрально и спокойно.
- СТРОГО ОДИН вопрос за сообщение! Не задавай по два вопроса сразу.
- СТОП ПОСТОРОННИМ ТЕМАМ (Guardrail): если клиент спрашивает про погоду, новости, курс валют и т.п., НЕ продолжай дальше собирать анкету молча! Мягко напомни: «Я могу проконсультировать вас по долгам и кредитам. Давайте вернёмся к вашей ситуации — ...».

ОБЯЗАТЕЛЬНЫЕ ФОКУСЫ — ЧТО НУЖНО ВЫЯСНИТЬ ДО ФИНАЛА:
Ты ОБЯЗАНА полностью исследовать финансовую картину, не пропуская ничего важного:
1. Точная или примерная сумма долга (в цифрах). Если клиент не назвал сумму, ОБЯЗАТЕЛЬНО спроси: «Подскажите, а какая примерно общая сумма всех задолженностей накопилась?». Без суммы диалог завершать нельзя!
2. Кто кредиторы: банки, микрозаймы (МФО), ЖКХ, налоги или частные долги?
3. Имущество: есть ли автомобиль, дача, гараж, ипотека или единственное жильё?
4. Сделки: продавал или дарил ли клиент имущество за последние 3 года?
5. Семья: состоит ли в браке, есть ли несовершеннолетние дети или иждивенцы?
6. Работа и доход: работает ли официально, самозанятый, ИП, пенсионер или без работы?
7. Давление: есть ли звонки коллекторов, суды или аресты карт приставами?
8. Регион постоянной прописки (спросить мягко: «В каком регионе вы прописаны?»).

ПРАВИЛО ЗАВЕРШЕНИЯ — НИКОГДА НЕ ОТКАЗЫВАТЬ В ЛИЦО:
- НИКОГДА и ни при каких обстоятельствах не говори клиенту фраз в духе «вы нам не подходите», «мы с вами не работаем», «ваш регион в исключениях», «у вас слишком маленький долг».
- Мы ВСЕГДА доводим консультацию до конца тепло и с уважением!
- В самом финале, когда вся ситуация выяснена (включая имя и контакт):
  1. Вызови qualify, чтобы подагент квалифицировал лида для внутренней карточки.
  2. Если лид подходит под стандартную запись к юристу (suitable / complex_suitable): предложи удобное время для подробного разбора и зафиксируй запись через finalize_card(end_result="booked").
  3. Если лид НЕ подходит по внутренним регламентам (not_suitable — малый долг или стоп-регион): НЕ назначай дату звонка и НЕ говори «мы вам отказываем». Скажи клиенту тепло и профессионально: «[Имя клиента], спасибо за доверие и подробный рассказ. Я собрала всю информацию по вашей ситуации и передаю ваше обращение на рассмотрение нашим ведущим юристам компании "Сэм и партнеры". Специалисты подробно изучат материалы и свяжутся с вами при наличии подходящего правового решения. Всего вам доброго и сил справиться с этой ситуацией!». После чего вызови finalize_card(end_result="not_suitable"). В чат уйдет отчетная карточка для юристов, а клиент останется доволен теплым приемом!

### Доступные навыки (вызывай get_skill при сомнениях клиента):
{skill_index}

### Состояние сбора информации (КЛИЕНТУ НЕ ПОКАЗЫВАТЬ):
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
                "ФИНАЛЬНЫЙ ШАГ: вызывается СТРОГО в самом конце беседы, когда весь сценарий пройден, "
                "ситуация полностью расспрошена, и собраны имя и контактный телефон клиента. "
                "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО вызывать в начале или середине диалога!"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "end_result": {
                        "type": "string",
                        "description": "booked — запись согласована; not_suitable — ситуация не для процедуры (передаем юристам без звонка); handoff — просьба человека",
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
        state = session.checklist()
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
        
        # 1. Проверяем, что сумма долга реально выяснена у клиента
        if not session.slots.get("debt_total"):
            logger.warning("⚠️ [FINAL] Попытка финализации без суммы долга!")
            return json.dumps(
                {
                    "error": "Нельзя завершать консультацию: ты не спросил у клиента сумму долга!",
                    "инструкция": "Спроси у клиента: «Подскажите, а какая примерно общая сумма всех задолженностей у вас накопилась?»"
                },
                ensure_ascii=False,
            )

        # 2. Проверяем обязательные пункты ситуации (не менее 5 ключевых параметров)
        missing_ctx = session.missing_context()
        if len(missing_ctx) > 3:
            return json.dumps(
                {
                    "error": "Рано завершать: ситуация клиента ещё недостаточно исследована!",
                    "что_нужно_выяснить": [SLOTS[k]["label"] for k in missing_ctx],
                    "инструкция": "Задай ещё 1-2 вопроса по невыясненным пунктам ситуации."
                },
                ensure_ascii=False,
            )

        # 3. Проверяем наличие имени и контакта
        missing_book = [k for k in ("name", "contact") if not session.slots.get(k)]
        if missing_book:
            return json.dumps(
                {
                    "error": "Не хватает контактных данных для карточки",
                    "не_собрано": [SLOTS[k]["label"] for k in missing_book],
                    "инструкция": "Уточни у клиента имя и номер телефона для связи перед завершением."
                },
                ensure_ascii=False,
            )

        # 4. Проверяем квалификацию
        if not session.verdict:
            session.verdict = qualification.qualify(session.slots)

        hard = qualification.hard_verdict(session.slots)
        if hard:
            session.verdict = hard
            end_result = "not_suitable"

        session.end_result = end_result
        session.finished = True
        card = report.build_card(session)
        transcript_text = report.build_transcript_content(session, card)
        payload["card"] = card
        payload["transcript"] = transcript_text
        payload["filename"] = f"dialog_{session.id}.md"

        # Автоматическая выгрузка в Google Таблицу
        try:
            from app import sheets
            sheets.export_lead(session)
        except Exception:
            logger.exception("Ошибка выгрузки лида в Google Таблицу")

        logger.info("🎉 [FINISHED] Сессия %s успешно завершена! Итог: %s.", session.id, end_result)
        return json.dumps({"ok": True, "message": "Карточка передана юристам компании «Сэм и партнеры», диалог завершён"}, ensure_ascii=False)

    return json.dumps({"error": f"неизвестный тул {name}"}, ensure_ascii=False)
