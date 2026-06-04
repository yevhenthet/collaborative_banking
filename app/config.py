from sqlalchemy.orm import Session
from . import models

# Organisation branding settings (text type, stored in same Setting table)
ORG_SETTINGS_SCHEMA = {
    "org_name": {
        "label": "Назва банку / системи",
        "label_en": "System / app name",
        "hint": "Відображається в шапці та при вході. Наприклад: «Банк питань»",
        "hint_en": "Shown in the sidebar header and login page. E.g. «Question Bank»",
        "default": "",
        "placeholder": "Question Bank",
        "placeholder_uk": "Банк питань",
    },
    "org_dept": {
        "label": "Університет · Кафедра",
        "label_en": "University · Department",
        "hint": "Підзаголовок. Наприклад: «ОНМедУ · Мікробіологія»",
        "hint_en": "Subtitle line. E.g. «ONMedU · Microbiology»",
        "default": "",
        "placeholder": "University · Department",
        "placeholder_uk": "Університет · Кафедра",
    },
    "pass_threshold_method": {
        "label": "Метод встановлення порогу складання",
        "label_en": "Standard-setting method",
        "hint": "Задокументуйте яким методом встановлено поріг (напр. «Метод Ангоффа, консенсус кафедри 2024», «Borderline regression, іспит 2023»). Відображається в експорті тестів.",
        "hint_en": "Document how the pass threshold was set (e.g. 'Angoff method, faculty consensus 2024', 'Borderline regression, exam 2023'). Shown in test exports.",
        "default": "",
        "placeholder": "Angoff method, faculty consensus 2024",
        "placeholder_uk": "Метод Ангоффа, консенсус кафедри 2024",
    },
}

# Each setting: default, label, hint, type ("pct" or "int"), min, max, unit
SETTINGS_SCHEMA = {
    "quorum": {
        "default": 2, "min": 1, "max": 50, "type": "int", "unit": "голосів",
        "label": "Кворум",
        "hint": "Мінімальна кількість голосів (від різних викладачів) для активації питання.",
        "label_en": "Quorum",
        "hint_en": "Minimum number of votes (from different teachers) to activate a question.",
        "unit_en": "votes",
    },
    "approve_pct": {
        "default": 51, "min": 1, "max": 100, "type": "pct", "unit": "%",
        "label": "Поріг схвалення",
        "hint": "Мінімальний % голосів «Схвалити» серед усіх проголосованих для активації питання.",
        "label_en": "Approval threshold",
        "hint_en": "Minimum % of 'Approve' votes among all voters to activate a question.",
        "unit_en": "%",
    },
    "diff_v_pct": {
        "default": 50, "min": 1, "max": 100, "type": "pct", "unit": "%",
        "label": "Поріг рівня В",
        "hint": "Мінімальний % голосів за рівень В серед тих, хто схвалив, щоб питання отримало рівень В.",
        "label_en": "Higher-order threshold",
        "hint_en": "Minimum % of H votes among approvers for a question to receive H tier.",
        "unit_en": "%",
    },
    "diff_s_pct": {
        "default": 50, "min": 1, "max": 100, "type": "pct", "unit": "%",
        "label": "Поріг рівня С або вище",
        "hint": "Мінімальний % голосів за рівень С або В серед схвалених, щоб питання отримало рівень С (якщо не В).",
        "label_en": "Moderate-or-above threshold",
        "hint_en": "Minimum % of M/H votes among approvers for a question to receive M tier (if not H).",
        "unit_en": "%",
    },
    "pass_threshold_pct": {
        "default": 75, "min": 50, "max": 90, "step": 5, "type": "pct", "unit": "%",
        "label": "Поріг зарахування Б+С",
        "hint": "Мінімальний % правильних відповідей на питання базового та середнього рівнів для отримання позитивної оцінки. Є параметром навчального закладу — задайте до початку тестування.",
        "label_en": "B+M pass threshold",
        "hint_en": "Minimum % of basic and intermediate questions answered correctly to pass. This is an institutional policy parameter — set it before testing begins.",
        "unit_en": "%",
    },
    "exposure_horizon_n": {
        "default": 3, "min": 1, "max": 10, "type": "int", "unit": "тестів",
        "label": "Горизонт контролю повторень",
        "hint": "Кількість останніх тестів модуля, в яких питання вважається «нещодавно використаним» та виключається з нової генерації. Рекомендується ≥ 3 для sound exposure control.",
        "label_en": "Exposure control horizon",
        "hint_en": "Number of recent module tests within which a question is considered 'recently used' and excluded from new test generation. ≥ 3 recommended for sound exposure control.",
        "unit_en": "tests",
    },
}

DEFAULTS = {k: v["default"] for k, v in SETTINGS_SCHEMA.items()}
LABELS   = {k: v["label"]   for k, v in SETTINGS_SCHEMA.items()}
HINTS    = {k: v["hint"]    for k, v in SETTINGS_SCHEMA.items()}


def get_settings(db: Session) -> dict:
    result = dict(DEFAULTS)
    for row in db.query(models.Setting).all():
        if row.key in result:
            result[row.key] = int(row.value)
    return result


def save_settings(db: Session, data: dict):
    for key, value in data.items():
        if key not in DEFAULTS:
            continue
        schema = SETTINGS_SCHEMA[key]
        clamped = max(schema["min"], min(schema["max"], int(value)))
        row = db.get(models.Setting, key)
        if row:
            row.value = str(clamped)
        else:
            db.add(models.Setting(key=key, value=str(clamped)))
    db.commit()


def get_org_settings(db: Session) -> dict:
    result = {k: v["default"] for k, v in ORG_SETTINGS_SCHEMA.items()}
    for row in db.query(models.Setting).filter(
        models.Setting.key.in_(list(ORG_SETTINGS_SCHEMA.keys()))
    ).all():
        result[row.key] = row.value
    return result


def save_org_settings(db: Session, data: dict):
    for key in ORG_SETTINGS_SCHEMA:
        value = (data.get(key) or "").strip()
        row = db.get(models.Setting, key)
        if row:
            row.value = value
        else:
            db.add(models.Setting(key=key, value=value))
    db.commit()
