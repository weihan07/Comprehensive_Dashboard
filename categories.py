"""Reorganized product-category taxonomy (重新整理过商品分类).

Maps the raw ``product_category`` values that appear in the data onto a clean
two-level hierarchy the dashboard's sidebar filter exposes:

    手机充值 (Mobile top-up)   ── 话费 / 后付费 / 流量 / 充值卡
    电子钱包 (E-wallet)        ── Touch'n Go / 电子钱包
    生活缴费 (Life bills)      ── 电费 / 水费 / 污水处理 / 固定电话 / 电视缴费 / 宽带缴费 / 其他
    道路交通 (Road transport)  ── Salik卡 / 车辆罚款

The raw value lists are the ACTUAL strings found in ``sales_cache.parquet``
(e.g. the data spells it ``Sailk卡``, not ``Salik``). ``充流量-测试`` (a test
category, 3 rows / ¥0.3) is intentionally left unmapped so it is excluded when
any category filter is active.

Helpers: ``TOP_CATEGORIES``, ``subcategories(top)``, ``raw_values(top, subs)``,
``EWALLET_RAW`` (the values the China-team default exclusion drops — used to let
an explicit selection override that exclusion), and ``label(name, lang)``.
"""
from __future__ import annotations

# top → subcategory → [raw product_category values as they appear in the data]
CATEGORY_TREE: dict[str, dict[str, list[str]]] = {
    "手机充值": {
        "话费":   ["充话费", "ENC", "PayGo", "Hotlink（Maxis）"],
        "后付费": ["后付费", "手机缴费"],
        "流量":   ["买流量"],
        "充值卡": ["PIN码话费", "充值卡"],
    },
    "电子钱包": {
        "Touch'n Go": ["Touch'n Go"],
        "电子钱包":    ["电子钱包"],
    },
    "生活缴费": {
        "电费":     ["交电费"],
        "水费":     ["交水费"],
        "污水处理": ["污水处理"],
        "固定电话": ["电话缴费", "固定电话", "交话费"],
        "电视缴费": ["电视缴费"],
        "宽带缴费": ["交网费", "宽带缴费"],
        "其他":     ["生活缴费"],
    },
    "道路交通": {
        "Salik卡":  ["Sailk卡"],
        "车辆罚款": ["车辆罚款"],
    },
}

# English display labels for the bilingual sidebar (missing keys fall back to the key).
LABELS_EN: dict[str, str] = {
    "手机充值": "Mobile Top-up", "电子钱包": "E-wallet",
    "生活缴费": "Life Bills", "道路交通": "Road Transport",
    "话费": "Airtime", "后付费": "Postpaid", "流量": "Data", "充值卡": "Recharge Card",
    "Touch'n Go": "Touch'n Go",
    "电费": "Electricity", "水费": "Water", "污水处理": "Sewage",
    "固定电话": "Landline", "电视缴费": "TV", "宽带缴费": "Broadband", "其他": "Other",
    "Salik卡": "Salik Card", "车辆罚款": "Vehicle Fines",
}

# The raw values the China-team default (_apply_global_exclusions) drops.
EWALLET_RAW: set[str] = {v for subs in CATEGORY_TREE["电子钱包"].values() for v in subs}

TOP_CATEGORIES: list[str] = list(CATEGORY_TREE.keys())


def subcategories(top: str) -> list[str]:
    """Subcategory names under a top category (empty if unknown/All)."""
    return list(CATEGORY_TREE.get(top, {}).keys())


def raw_values(top: str | None = None, subs=None) -> set[str]:
    """Raw ``product_category`` values selected by (top, subs).

    - top None/"All"    → every mapped value (all groups).
    - top set, subs empty → every value in that top group.
    - top set, subs given → only those subcategories' values.
    """
    if not top or top == "All":
        return {v for g in CATEGORY_TREE.values() for vs in g.values() for v in vs}
    group = CATEGORY_TREE.get(top, {})
    chosen = list(subs) if subs else list(group.keys())
    return {v for s in chosen for v in group.get(s, [])}


def label(name: str, lang: str = "en") -> str:
    """Bilingual display label for a top/sub name."""
    return LABELS_EN.get(name, name) if lang == "en" else name
