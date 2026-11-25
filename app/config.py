"""Настройки подключения к GigaChat через переменные окружения.

Режимы (GIGACHAT_MODE):
  - mtls  — внутренний корпоративный шлюз Сбера по mTLS-сертификатам (как в «Маркете»);
  - token — публичный API GigaChat по access_token / credentials.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)


def _abs(path: str) -> str:
    p = Path(path)
    return str(p if p.is_absolute() else BASE_DIR / p)


def llm_config() -> dict:
    """Собирает аргументы конструктора langchain_gigachat.GigaChat из env."""
    mode = os.getenv("GIGACHAT_MODE", "token").strip().lower()
    cfg = {
        "model": os.getenv("GIGACHAT_MODEL"),
        "temperature": float(os.getenv("GIGACHAT_TEMPERATURE", "0.3")),
        "timeout": int(os.getenv("GIGACHAT_TIMEOUT", "120")),
    }
    if mode == "token":
        for env_key, arg in (
            ("GIGACHAT_ACCESS_TOKEN", "access_token"),
            ("GIGACHAT_CREDENTIALS", "credentials"),
            ("GIGACHAT_SCOPE", "scope"),
            ("GIGACHAT_BASE_URL", "base_url"),
            ("GIGACHAT_AUTH_URL", "auth_url"),
        ):
            value = os.getenv(env_key)
            if value:
                cfg[arg] = value
        if os.getenv("GIGACHAT_VERIFY_SSL_CERTS") is not None:
            cfg["verify_ssl_certs"] = os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "").lower() in ("true", "1")
    else:
        host = os.getenv("GIGACHAT_HOST")
        port = os.getenv("GIGACHAT_PORT")
        if host and port:
            cfg["base_url"] = f"https://{host}:{port}/v1"
        elif host:
            cfg["base_url"] = f"https://{host}/v1"

        ca_bundle = os.getenv("GIGACHAT_CA_BUNDLE_FILEPATH")
        if ca_bundle:
            cfg["ca_bundle_file"] = _abs(ca_bundle)
        cert_file = os.getenv("GIGACHAT_TLS_CERT_FILEPATH")
        if cert_file:
            cfg["cert_file"] = _abs(cert_file)
        key_file = os.getenv("GIGACHAT_KEY_FILEPATH")
        if key_file:
            cfg["key_file"] = _abs(key_file)
        if os.getenv("GIGACHAT_VERIFY_SSL_CERTS") is not None:
            cfg["verify_ssl_certs"] = os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "").lower() in ("true", "1")
        else:
            cfg["verify_ssl_certs"] = False
    return {k: v for k, v in cfg.items() if v is not None}
