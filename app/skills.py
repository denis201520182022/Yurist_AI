"""Реестр скилов: темы регламента, подгружаемые моделью по требованию."""
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

# topic -> краткое описание для индекса в системном промпте
SKILL_TOPICS = {
    "company_facts": "факты о компании, доверие, «вы не обманщики»",
    "price": "вопросы о стоимости",
    "no_office": "нет офиса в городе клиента, дистанционная работа",
    "restructuring": "реструктуризация vs банкротство",
    "guarantees": "вопросы о гарантиях",
    "procedure": "этапы процедуры, что будет происходить",
    "court": "страх суда, заседания",
    "children": "дети, опека, «заберут ли детей»",
    "property": "страх потери имущества в целом",
    "home": "единственное жильё",
    "mortgage": "ипотека",
    "collateral": "залоговое имущество",
    "car": "автомобиль",
    "income": "доход, прожиточный минимум, высокий доход",
    "deals": "оспаривание сделок",
    "arrests": "аресты счетов, запрет выезда, приставы",
    "collectors": "коллекторы",
    "fraud": "кредиты под влиянием мошенников",
    "mfc": "внесудебное банкротство через МФЦ",
    "married": "брак, совместное имущество и долги",
    "unemployed": "безработный",
    "disability": "инвалидность",
    "ip": "ИП и бывшие ИП",
    "self_employed": "самозанятые",
    "ooo": "директор, учредитель, доля в ООО",
    "debts": "какие долги списываются",
    "zhkh": "долги по ЖКХ",
    "taxes": "налоговые долги",
    "inheritance": "наследственные долги",
}


def index_text() -> str:
    return "\n".join(f"- {topic}: {desc}" for topic, desc in SKILL_TOPICS.items())


def read_skill(topic: str) -> str | None:
    if topic not in SKILL_TOPICS:
        return None
    path = SKILLS_DIR / f"{topic}.md"
    return path.read_text(encoding="utf-8") if path.exists() else None


def read_qualification_rules() -> str:
    return (SKILLS_DIR / "qualification.md").read_text(encoding="utf-8")
