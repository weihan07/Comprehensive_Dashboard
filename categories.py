"""Product-category taxonomy — 6 system-wide classes (matches the supplier
dashboard's category breakdown).

Maps every raw ``product_category`` value in ``sales_cache.parquet`` onto one of
six business classes the sidebar filter and the Product-tab charts use:

    话费充值   Airtime      充话费 · ENC · PayGo · Hotlink（Maxis）· PIN码话费 · 充值卡
    电子钱包/PIN E-wallet/PIN Touch'n Go            (SRS TNG PIN)
    电子钱包    E-wallet     电子钱包               (IAK OVO/DANA/GoPay)
    流量套餐   Data         买流量
    账单缴费   Bill Payment 交电费/交水费/污水处理/固定电话/电话缴费/交话费/电视缴费/
                            交网费/宽带缴费/生活缴费/Sailk卡/车辆罚款
    后付费     Postpaid     后付费 · 手机缴费

The raw lists are the ACTUAL strings in the data (e.g. it spells ``Sailk卡``).
``充流量-测试`` (a test category) is intentionally unmapped → excluded when any
category filter is active, and classified as "Other" in the Product-tab charts.

Helpers: ``TOP_CATEGORIES``, ``subcategories(top)``, ``raw_values(top, subs)``,
``classify(raw)`` / ``top_of(raw)``, ``EWALLET_RAW``, ``label(name, lang)``.
"""
from __future__ import annotations

# class name → [raw product_category values as they appear in the data]
CATEGORY_CLASSES: dict[str, list[str]] = {
    "话费充值":    ["充话费", "ENC", "PayGo", "Hotlink（Maxis）", "PIN码话费", "充值卡"],
    "电子钱包/PIN": ["Touch'n Go"],
    "电子钱包":     ["电子钱包"],
    "流量套餐":     ["买流量"],
    "账单缴费":     ["交电费", "交水费", "污水处理", "固定电话", "电话缴费", "交话费",
                    "电视缴费", "交网费", "宽带缴费", "生活缴费", "Sailk卡", "车辆罚款"],
    "后付费":       ["后付费", "手机缴费"],
}

# Backward-compat alias (older code/tests referenced CATEGORY_TREE).
CATEGORY_TREE = CATEGORY_CLASSES

# English display labels for the bilingual sidebar (missing keys fall back to key).
LABELS_EN: dict[str, str] = {
    "话费充值": "Airtime", "电子钱包/PIN": "E-wallet/PIN", "电子钱包": "E-wallet",
    "流量套餐": "Data", "账单缴费": "Bill Payment", "后付费": "Postpaid",
    # a few common raw-value → EN (subcategory labels; others fall back to raw)
    "充话费": "Airtime top-up", "买流量": "Data bundle", "Touch'n Go": "Touch'n Go",
    "PIN码话费": "Airtime PIN", "充值卡": "Recharge card", "手机缴费": "Mobile bill",
    "交电费": "Electricity", "交水费": "Water", "污水处理": "Sewage",
    "固定电话": "Landline", "电视缴费": "TV", "宽带缴费": "Broadband", "交网费": "Internet",
    "Sailk卡": "Salik card", "车辆罚款": "Vehicle fines",
}

TOP_CATEGORIES: list[str] = list(CATEGORY_CLASSES.keys())

# raw value → class name (reverse map)
_RAW_TO_CLASS: dict[str, str] = {
    v: cls for cls, vs in CATEGORY_CLASSES.items() for v in vs
}

# The raw values the China-team default (_apply_global_exclusions) drops —
# both e-wallet classes, so an explicit selection can override the exclusion.
EWALLET_RAW: set[str] = set(CATEGORY_CLASSES["电子钱包/PIN"]) | set(CATEGORY_CLASSES["电子钱包"])


def subcategories(top: str) -> list[str]:
    """Raw values under a class (used as the cascading sub-filter choices)."""
    return list(CATEGORY_CLASSES.get(top, []))


def raw_values(top: str | None = None, subs=None) -> set[str]:
    """Raw ``product_category`` values selected by (class, subs).

    - top None/"All"      → every mapped value (all classes).
    - top set, subs empty → every value in that class.
    - top set, subs given → only those raw values (intersected with the class).
    """
    if not top or top == "All":
        return set(_RAW_TO_CLASS.keys())
    group = set(CATEGORY_CLASSES.get(top, []))
    return (set(subs) & group) if subs else group


def classify(raw, default: str = "其他") -> str:
    """Class name for a raw product_category value ('其他'/Other if unmapped)."""
    return _RAW_TO_CLASS.get(str(raw).strip(), default)


def top_of(raw) -> str | None:
    """Class name for a raw value, or None if unmapped."""
    return _RAW_TO_CLASS.get(str(raw).strip())


def label(name: str, lang: str = "en") -> str:
    """Bilingual display label for a class or raw value."""
    return LABELS_EN.get(name, name) if lang == "en" else name
