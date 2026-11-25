"""Клиент GigaChat с циклом обработки tool-вызовов.

Схема как в референсном проекте «Маркет»: bind_tools + повторные итерации,
пока модель не вернёт финальный текст без tool_calls.
"""
import json
import logging

logger = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "К сожалению, сейчас я временно не могу ответить. "
    "Попробуйте, пожалуйста, ещё раз через минуту."
)

_client = None


def get_client():
    global _client
    if _client is None:
        from app.config import llm_config
        from langchain_gigachat import GigaChat  # импорт по требованию

        _client = GigaChat(**llm_config())
    return _client


def chat(messages: list, tools: list | None = None, on_tool=None, max_iters: int = 8) -> str:
    """Прогон диалога через LLM.

    messages — список dict {role: system|user|assistant, content: str}.
    tools — схемы функций; on_tool(name, args_dict) -> str — исполнитель тулов.
    Возвращает финальный текстовый ответ модели.
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    model = get_client()
    if tools:
        model = model.bind_tools(tools)

    lc_messages: list = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))

    for iteration in range(1, max_iters + 1):
        resp = model.invoke(lc_messages)
        calls = getattr(resp, "tool_calls", None)
        if not calls:
            text = (resp.content or "").strip()
            return text or FALLBACK_REPLY
        lc_messages.append(resp)
        for tc in calls:
            name = tc.get("name")
            args = tc.get("args") or {}
            logger.info("Действие агента: %s(%s)", name, json.dumps(args, ensure_ascii=False)[:100])
            try:
                result = on_tool(name, args) if on_tool else '{"error": "нет обработчика тулов"}'
            except Exception as e:  # noqa: BLE001
                logger.exception("Ошибка в инструменте %s", name)
                result = json.dumps({"error": f"ошибка тула: {e}"}, ensure_ascii=False)
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)
            lc_messages.append(
                ToolMessage(content=result, tool_call_id=tc.get("id") or f"call_{iteration}")
            )

    logger.warning("Превышен лимит итераций диалогового цикла")
    return FALLBACK_REPLY
