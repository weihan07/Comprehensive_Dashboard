"""Country -> local currency mapping + RMB->local FX rates.

Used by the 'Local Currency' option in the dashboard Currency filter.

Each entry maps an English country name (matching country_mapping.py output)
to a tuple ``(symbol, iso_code, rmb_to_local_rate)``:

  - symbol         : short display symbol, e.g. 'RM', '$', '₹'
  - iso_code       : 3-letter ISO 4217 code, e.g. 'MYR', 'USD', 'INR'
  - rmb_to_local   : multiplier to convert RMB into local currency
                     (i.e. local_value = rmb_value * rate)

Rates are approximate mid-2025 indicative values. Edit this file to keep
them current. A typo or stale rate only affects 'Local Currency' display
mode — the underlying RMB data is untouched.

Usage:
    from fx_rates import lookup
    info = lookup("Malaysia")   # ("RM", "MYR", 0.66)
"""

from __future__ import annotations

# Each value: (display_symbol, iso_code, rmb_to_local_rate)
COUNTRY_CURRENCY: dict[str, tuple[str, str, float]] = {
    # East Asia
    "China":            ("¥",     "CNY",  1.0),
    "Hong Kong":        ("HK$",   "HKD",  1.09),
    "Macao":            ("MOP",   "MOP",  1.12),
    "Taiwan":           ("NT$",   "TWD",  4.5),
    "Japan":            ("¥",     "JPY",  21.0),
    "South Korea":      ("₩",     "KRW",  192.0),
    "Mongolia":         ("₮",     "MNT",  480.0),

    # Southeast Asia
    "Malaysia":         ("RM",    "MYR",  0.66),
    "Indonesia":        ("Rp",    "IDR",  2250.0),
    "Singapore":        ("S$",    "SGD",  0.19),
    "Thailand":         ("฿",     "THB",  5.0),
    "Vietnam":          ("₫",     "VND",  3500.0),
    "Philippines":      ("₱",     "PHP",  8.0),
    "Cambodia":         ("៛",     "KHR",  565.0),
    "Laos":             ("₭",     "LAK",  3030.0),
    "Myanmar":          ("K",     "MMK",  292.0),
    "Brunei":           ("B$",    "BND",  0.19),

    # South Asia
    "India":            ("₹",     "INR",  11.7),
    "Pakistan":         ("Rs",    "PKR",  39.0),
    "Bangladesh":       ("৳",     "BDT",  17.0),
    "Sri Lanka":        ("Rs",    "LKR",  42.0),
    "Nepal":            ("Rs",    "NPR",  19.0),
    "Bhutan":           ("Nu",    "BTN",  11.7),
    "Maldives":         ("Rf",    "MVR",  2.16),
    "Afghanistan":      ("؋",     "AFN",  10.0),

    # Central Asia
    "Kazakhstan":       ("₸",     "KZT",  70.0),
    "Uzbekistan":       ("сўм",   "UZS",  1800.0),
    "Tajikistan":       ("SM",    "TJS",  1.5),
    "Kyrgyzstan":       ("сом",   "KGS",  12.2),
    "Turkmenistan":     ("m",     "TMT",  0.49),

    # Middle East
    "Saudi Arabia":     ("﷼",     "SAR",  0.52),
    "United Arab Emirates": ("د.إ", "AED", 0.51),
    "Qatar":            ("﷼",     "QAR",  0.51),
    "Kuwait":           ("د.ك",   "KWD",  0.043),
    "Bahrain":          ("د.ب",   "BHD",  0.052),
    "Oman":             ("﷼",     "OMR",  0.054),
    "Yemen":            ("﷼",     "YER",  35.0),
    "Iran":             ("﷼",     "IRR",  5850.0),
    "Iraq":             ("د.ع",   "IQD",  184.0),
    "Syria":            ("£",     "SYP",  1800.0),
    "Jordan":           ("د.أ",   "JOD",  0.099),
    "Lebanon":          ("ل.ل",   "LBP",  12500.0),
    "Israel":           ("₪",     "ILS",  0.51),
    "Palestine":        ("₪",     "ILS",  0.51),
    "Turkey":           ("₺",     "TRY",  5.4),
    "Cyprus":           ("€",     "EUR",  0.13),

    # Africa
    "Egypt":            ("ج.م",   "EGP",  7.1),
    "Libya":            ("ل.د",   "LYD",  0.68),
    "Sudan":            ("ج.س",   "SDG",  84.0),
    "South Sudan":      ("£",     "SSP",  280.0),
    "Morocco":          ("د.م",   "MAD",  1.4),
    "Algeria":          ("د.ج",   "DZD",  19.0),
    "Tunisia":          ("د.ت",   "TND",  0.44),
    "South Africa":     ("R",     "ZAR",  2.6),
    "Nigeria":          ("₦",     "NGN",  225.0),
    "Kenya":            ("KSh",   "KES",  18.0),
    "Ethiopia":         ("Br",    "ETB",  18.0),
    "Tanzania":         ("TSh",   "TZS",  380.0),
    "Uganda":           ("USh",   "UGX",  525.0),
    "Ghana":            ("GH₵",   "GHS",  2.2),
    "Senegal":          ("CFA",   "XOF",  86.0),
    "Côte d'Ivoire":    ("CFA",   "XOF",  86.0),
    "Cameroon":         ("FCFA",  "XAF",  86.0),
    "Zimbabwe":         ("$",     "USD",  0.14),
    "Zambia":           ("K",     "ZMW",  3.8),
    "Botswana":         ("P",     "BWP",  1.9),
    "Mozambique":       ("MT",    "MZN",  8.9),
    "Angola":           ("Kz",    "AOA",  128.0),
    "Rwanda":           ("RF",    "RWF",  185.0),
    "Burundi":          ("FBu",   "BIF",  400.0),
    "Madagascar":       ("Ar",    "MGA",  640.0),
    "Mauritius":        ("Rs",    "MUR",  6.4),
    "Mali":             ("CFA",   "XOF",  86.0),
    "Burkina Faso":     ("CFA",   "XOF",  86.0),
    "Niger":            ("CFA",   "XOF",  86.0),
    "Chad":             ("FCFA",  "XAF",  86.0),
    "Benin":            ("CFA",   "XOF",  86.0),
    "Togo":             ("CFA",   "XOF",  86.0),
    "Guinea":           ("FG",    "GNF",  1200.0),
    "Sierra Leone":     ("Le",    "SLL",  3100.0),
    "Liberia":          ("L$",    "LRD",  26.0),
    "Eswatini":         ("L",     "SZL",  2.6),
    "Namibia":          ("N$",    "NAD",  2.6),
    "Mauritania":       ("UM",    "MRU",  5.5),
    "Malawi":           ("MK",    "MWK",  240.0),
    "Réunion":          ("€",     "EUR",  0.13),

    # Europe
    "United Kingdom":   ("£",     "GBP",  0.11),
    "France":           ("€",     "EUR",  0.13),
    "Germany":          ("€",     "EUR",  0.13),
    "Italy":            ("€",     "EUR",  0.13),
    "Spain":            ("€",     "EUR",  0.13),
    "Portugal":         ("€",     "EUR",  0.13),
    "Netherlands":      ("€",     "EUR",  0.13),
    "Belgium":          ("€",     "EUR",  0.13),
    "Luxembourg":       ("€",     "EUR",  0.13),
    "Austria":          ("€",     "EUR",  0.13),
    "Ireland":          ("€",     "EUR",  0.13),
    "Greece":           ("€",     "EUR",  0.13),
    "Finland":          ("€",     "EUR",  0.13),
    "Estonia":          ("€",     "EUR",  0.13),
    "Latvia":           ("€",     "EUR",  0.13),
    "Lithuania":        ("€",     "EUR",  0.13),
    "Slovenia":         ("€",     "EUR",  0.13),
    "Slovakia":         ("€",     "EUR",  0.13),
    "Croatia":          ("€",     "EUR",  0.13),
    "Malta":            ("€",     "EUR",  0.13),
    "Monaco":           ("€",     "EUR",  0.13),
    "Andorra":          ("€",     "EUR",  0.13),
    "San Marino":       ("€",     "EUR",  0.13),
    "Vatican City":     ("€",     "EUR",  0.13),
    "Switzerland":      ("CHF",   "CHF",  0.12),
    "Denmark":          ("kr",    "DKK",  0.97),
    "Sweden":           ("kr",    "SEK",  1.5),
    "Norway":           ("kr",    "NOK",  1.5),
    "Iceland":          ("kr",    "ISK",  19.0),
    "Poland":           ("zł",    "PLN",  0.56),
    "Czechia":          ("Kč",    "CZK",  3.2),
    "Hungary":          ("Ft",    "HUF",  50.0),
    "Romania":          ("lei",   "RON",  0.64),
    "Bulgaria":         ("лв",    "BGN",  0.25),
    "Serbia":           ("дин",   "RSD",  15.0),
    "Bosnia and Herzegovina": ("KM", "BAM", 0.25),
    "Montenegro":       ("€",     "EUR",  0.13),
    "North Macedonia":  ("ден",   "MKD",  7.9),
    "Albania":          ("L",     "ALL",  13.0),
    "Russia":           ("₽",     "RUB",  12.5),
    "Ukraine":          ("₴",     "UAH",  5.8),
    "Belarus":          ("Br",    "BYN",  0.46),
    "Moldova":          ("L",     "MDL",  2.5),
    "Georgia":          ("₾",     "GEL",  0.39),
    "Armenia":          ("֏",     "AMD",  55.0),
    "Azerbaijan":       ("₼",     "AZN",  0.24),

    # Americas
    "United States":    ("$",     "USD",  0.14),
    "Canada":           ("C$",    "CAD",  0.19),
    "Mexico":           ("MX$",   "MXN",  2.55),
    "Guatemala":        ("Q",     "GTQ",  1.07),
    "Honduras":         ("L",     "HNL",  3.45),
    "El Salvador":      ("$",     "USD",  0.14),
    "Nicaragua":        ("C$",    "NIO",  5.0),
    "Costa Rica":       ("₡",     "CRC",  72.0),
    "Panama":           ("$",     "PAB",  0.14),
    "Cuba":             ("$MN",   "CUP",  3.4),
    "Jamaica":          ("J$",    "JMD",  21.0),
    "Haiti":            ("G",     "HTG",  18.0),
    "Dominican Republic": ("RD$", "DOP",  8.0),
    "Puerto Rico":      ("$",     "USD",  0.14),
    "Trinidad and Tobago": ("TT$","TTD",  0.93),
    "Barbados":         ("Bds$",  "BBD",  0.28),
    "Bahamas":          ("B$",    "BSD",  0.14),
    "Brazil":           ("R$",    "BRL",  0.81),
    "Argentina":        ("$",     "ARS",  130.0),
    "Chile":            ("CLP",   "CLP",  130.0),
    "Peru":             ("S/",    "PEN",  0.52),
    "Colombia":         ("COL$",  "COP",  580.0),
    "Venezuela":        ("Bs",    "VES",  5.1),
    "Ecuador":          ("$",     "USD",  0.14),
    "Bolivia":          ("Bs",    "BOB",  0.96),
    "Paraguay":         ("₲",     "PYG",  1050.0),
    "Uruguay":          ("$U",    "UYU",  5.6),
    "Belize":           ("BZ$",   "BZD",  0.28),
    "Suriname":         ("Sr$",   "SRD",  5.3),
    "Guyana":           ("G$",    "GYD",  29.0),
    "French Guiana":    ("€",     "EUR",  0.13),
    "Dominica":         ("EC$",   "XCD",  0.38),
    "Curaçao":          ("ƒ",     "ANG",  0.25),
    "Grenada":          ("EC$",   "XCD",  0.38),
    "Bermuda":          ("BD$",   "BMD",  0.14),
    "Antigua and Barbuda": ("EC$","XCD",  0.38),

    # Oceania
    "Australia":        ("A$",    "AUD",  0.21),
    "New Zealand":      ("NZ$",   "NZD",  0.23),
    "Papua New Guinea": ("K",     "PGK",  0.55),
    "Fiji":             ("FJ$",   "FJD",  0.31),
}


def lookup(country: str | None):
    """Return (symbol, iso_code, rmb_to_local_rate) for a country, or None."""
    if not country:
        return None
    return COUNTRY_CURRENCY.get(str(country).strip())
