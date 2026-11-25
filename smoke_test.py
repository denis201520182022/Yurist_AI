"""Быстрая проверка: импорт, конфиг LLM, связность с GigaChat."""
from app import agent, config, llm

print("llm_config:", config.llm_config())
reply = llm.chat([{"role": "user", "content": "Скажи одно слово: ок"}])
print("ответ модели:", reply)
