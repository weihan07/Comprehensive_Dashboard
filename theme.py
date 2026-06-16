"""Professional theme + chart helpers used across every dashboard tab.

Centralises: colour palette, plotly layout defaults, large-number formatting,
delta-pct formatting, and a small ``apply_theme`` helper so every chart looks
consistent.
"""

from __future__ import annotations

# -- Palette ----------------------------------------------------------------

PRIMARY   = "#5B6CFF"   # main brand
SECONDARY = "#8B5CF6"   # accent purple
ACCENT    = "#EC4899"   # pink
SUCCESS   = "#10B981"   # green / positive
DANGER    = "#EF4444"   # red / negative
WARNING   = "#F59E0B"   # amber
INFO      = "#0EA5E9"   # sky blue
NEUTRAL   = "#64748B"   # slate

# Qualitative palette for category-coloured charts (B2B/B2C, by segment, etc.)
PALETTE = [
    "#5B6CFF", "#8B5CF6", "#EC4899", "#F59E0B",
    "#10B981", "#EF4444", "#0EA5E9", "#14B8A6",
    "#A855F7", "#F97316", "#3B82F6", "#22C55E",
]

# Sequential scale for choropleths / heatmaps
SCALE_SEQUENTIAL = [
    [0.00, "#EEF2FF"],
    [0.25, "#A5B4FC"],
    [0.50, "#6366F1"],
    [0.75, "#4338CA"],
    [1.00, "#312E81"],
]

# Diverging scale (for delta charts)
SCALE_DIVERGING = "RdYlGn"

# ISO-2 → ISO-3 country code mapping (for choropleth locationmode='ISO-3')
ISO2_TO_ISO3: dict[str, str] = {
    "AF":"AFG","AL":"ALB","DZ":"DZA","AD":"AND","AO":"AGO","AG":"ATG","AR":"ARG","AM":"ARM",
    "AU":"AUS","AT":"AUT","AZ":"AZE","BS":"BHS","BH":"BHR","BD":"BGD","BB":"BRB","BY":"BLR",
    "BE":"BEL","BZ":"BLZ","BJ":"BEN","BT":"BTN","BO":"BOL","BA":"BIH","BW":"BWA","BR":"BRA",
    "BN":"BRN","BG":"BGR","BF":"BFA","BI":"BDI","CV":"CPV","KH":"KHM","CM":"CMR","CA":"CAN",
    "CF":"CAF","TD":"TCD","CL":"CHL","CN":"CHN","CO":"COL","KM":"COM","CG":"COG","CD":"COD",
    "CR":"CRI","CI":"CIV","HR":"HRV","CU":"CUB","CY":"CYP","CZ":"CZE","DK":"DNK","DJ":"DJI",
    "DM":"DMA","DO":"DOM","EC":"ECU","EG":"EGY","SV":"SLV","GQ":"GNQ","ER":"ERI","EE":"EST",
    "SZ":"SWZ","ET":"ETH","FJ":"FJI","FI":"FIN","FR":"FRA","GA":"GAB","GM":"GMB","GE":"GEO",
    "DE":"DEU","GH":"GHA","GR":"GRC","GD":"GRD","GT":"GTM","GN":"GIN","GW":"GNB","GY":"GUY",
    "HT":"HTI","HN":"HND","HU":"HUN","IS":"ISL","IN":"IND","ID":"IDN","IR":"IRN","IQ":"IRQ",
    "IE":"IRL","IL":"ISR","IT":"ITA","JM":"JAM","JP":"JPN","JO":"JOR","KZ":"KAZ","KE":"KEN",
    "KI":"KIR","KP":"PRK","KR":"KOR","KW":"KWT","KG":"KGZ","LA":"LAO","LV":"LVA","LB":"LBN",
    "LS":"LSO","LR":"LBR","LY":"LBY","LI":"LIE","LT":"LTU","LU":"LUX","MG":"MDG","MW":"MWI",
    "MY":"MYS","MV":"MDV","ML":"MLI","MT":"MLT","MH":"MHL","MR":"MRT","MU":"MUS","MX":"MEX",
    "FM":"FSM","MD":"MDA","MC":"MCO","MN":"MNG","ME":"MNE","MA":"MAR","MZ":"MOZ","MM":"MMR",
    "NA":"NAM","NR":"NRU","NP":"NPL","NL":"NLD","NZ":"NZL","NI":"NIC","NE":"NER","NG":"NGA",
    "MK":"MKD","NO":"NOR","OM":"OMN","PK":"PAK","PW":"PLW","PA":"PAN","PG":"PNG","PY":"PRY",
    "PE":"PER","PH":"PHL","PL":"POL","PT":"PRT","QA":"QAT","RO":"ROU","RU":"RUS","RW":"RWA",
    "KN":"KNA","LC":"LCA","VC":"VCT","WS":"WSM","SM":"SMR","ST":"STP","SA":"SAU","SN":"SEN",
    "RS":"SRB","SC":"SYC","SL":"SLE","SG":"SGP","SK":"SVK","SI":"SVN","SB":"SLB","SO":"SOM",
    "ZA":"ZAF","SS":"SSD","ES":"ESP","LK":"LKA","SD":"SDN","SR":"SUR","SE":"SWE","CH":"CHE",
    "SY":"SYR","TW":"TWN","TJ":"TJK","TZ":"TZA","TH":"THA","TL":"TLS","TG":"TGO","TO":"TON",
    "TT":"TTO","TN":"TUN","TR":"TUR","TM":"TKM","TV":"TUV","UG":"UGA","UA":"UKR","AE":"ARE",
    "GB":"GBR","US":"USA","UY":"URY","UZ":"UZB","VU":"VUT","VE":"VEN","VN":"VNM","YE":"YEM",
    "ZM":"ZMB","ZW":"ZWE",
}

# -- Telephone calling code -> country (for destination-market analysis) ----
# Covers the destination prefixes actually present in the data (区号 column).

CALLING_CODE_TO_COUNTRY: dict[int, str] = {
    1: "USA/Canada", 7: "Russia/Kazakhstan", 20: "Egypt", 27: "South Africa",
    30: "Greece", 31: "Netherlands", 33: "France", 34: "Spain", 39: "Italy",
    40: "Romania", 44: "United Kingdom", 49: "Germany", 51: "Peru", 52: "Mexico",
    54: "Argentina", 55: "Brazil", 56: "Chile", 57: "Colombia", 60: "Malaysia",
    61: "Australia", 62: "Indonesia", 63: "Philippines", 64: "New Zealand",
    65: "Singapore", 66: "Thailand", 81: "Japan", 82: "South Korea",
    84: "Vietnam", 86: "China", 90: "Turkey", 91: "India", 92: "Pakistan",
    93: "Afghanistan", 94: "Sri Lanka", 95: "Myanmar", 98: "Iran",
    211: "South Sudan", 212: "Morocco", 213: "Algeria", 216: "Tunisia",
    218: "Libya", 220: "Gambia", 221: "Senegal", 223: "Mali", 225: "Côte d'Ivoire",
    226: "Burkina Faso", 227: "Niger", 228: "Togo", 229: "Benin", 230: "Mauritius",
    231: "Liberia", 232: "Sierra Leone", 233: "Ghana", 234: "Nigeria",
    235: "Chad", 237: "Cameroon", 241: "Gabon", 243: "DR Congo", 244: "Angola",
    249: "Sudan", 250: "Rwanda", 251: "Ethiopia", 252: "Somalia", 254: "Kenya",
    255: "Tanzania", 256: "Uganda", 260: "Zambia", 263: "Zimbabwe",
    351: "Portugal", 352: "Luxembourg", 355: "Albania", 380: "Ukraine",
    420: "Czechia", 593: "Ecuador", 595: "Paraguay", 675: "Papua New Guinea",
    676: "Tonga", 679: "Fiji", 689: "French Polynesia",
    852: "Hong Kong", 853: "Macao", 855: "Cambodia", 856: "Laos",
    880: "Bangladesh", 886: "Taiwan", 960: "Maldives", 961: "Lebanon",
    962: "Jordan", 963: "Syria", 964: "Iraq", 965: "Kuwait", 966: "Saudi Arabia",
    967: "Yemen", 968: "Oman", 970: "Palestine", 971: "United Arab Emirates",
    972: "Israel", 973: "Bahrain", 974: "Qatar", 975: "Bhutan", 976: "Mongolia",
    977: "Nepal", 992: "Tajikistan", 993: "Turkmenistan", 994: "Azerbaijan",
    995: "Georgia", 996: "Kyrgyzstan", 998: "Uzbekistan",
}


def calling_code_to_country(code) -> str:
    """Map a numeric calling code (区号) to a country label."""
    try:
        return CALLING_CODE_TO_COUNTRY.get(int(float(code)), f"+{int(float(code))}")
    except (TypeError, ValueError):
        return "Unknown"


# -- Layout defaults --------------------------------------------------------

FONT_FAMILY = ("'Inter', 'Segoe UI Variable Text', 'Segoe UI', system-ui, "
               "-apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif")

LAYOUT_DEFAULTS = dict(
    template="plotly_white",
    title_x=0.0,                                     # left-align titles
    title_xanchor="left",
    title_font=dict(size=14, color="#0F172A", family=FONT_FAMILY),
    margin=dict(l=10, r=10, t=50, b=10),
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family=FONT_FAMILY, size=12, color="#334155"),
    hoverlabel=dict(bgcolor="white", bordercolor="#E2E8F0",
                    font=dict(family=FONT_FAMILY, size=12, color="#0F172A")),
    xaxis=dict(showgrid=False, linecolor="#E2E8F0", ticks="outside", tickcolor="#E2E8F0",
               tickfont=dict(size=11, color="#64748B"),
               title_font=dict(size=12, color="#64748B")),
    yaxis=dict(gridcolor="#F1F5F9", linecolor="#E2E8F0", zerolinecolor="#E2E8F0",
               tickfont=dict(size=11, color="#64748B"),
               title_font=dict(size=12, color="#64748B")),
    legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0,
                bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    colorway=PALETTE,
)


def apply_theme(fig, title: str | None = None, **layout_overrides):
    """Apply consistent layout to a Plotly figure. Returns the figure."""
    layout = {**LAYOUT_DEFAULTS}
    if title is not None:
        layout["title_text"] = title
    layout.update(layout_overrides)
    fig.update_layout(**layout)
    return fig


# Loading mode for Plotly.js:
#   - "cdn"  : pulls plotly.min.js from cdn.plot.ly (2-3s on first browser load)
#   - False  : the page promises plotly.min.js is already loaded
#              (we serve it from /static via Shiny — see sales_dashboard.py)
PLOTLY_JS_MODE: object = False


def fig_to_html(fig) -> str:
    """Render a Plotly figure to a fragment of HTML, using the project's
    chosen Plotly.js loading mode. Use this everywhere instead of calling
    ``fig.to_html(...)`` directly — that way we can flip how plotly.min.js
    is delivered in a single place."""
    return fig.to_html(include_plotlyjs=PLOTLY_JS_MODE, full_html=False)


# -- Number formatting ------------------------------------------------------

def format_full(n, currency_symbol: str = "", decimals: int = 2) -> str:
    """Render a number in full comma-separated format (e.g. 5,334,565.77)."""
    if n is None:
        return "—"
    try:
        n = float(n)
    except Exception:
        return "—"
    if n != n:
        return "—"
    return f"{currency_symbol}{n:,.{decimals}f}"


def format_number(n, currency_symbol: str = "", decimals: int = 2) -> str:
    """Render a number with K/M/B suffixes and an optional currency symbol."""
    if n is None:
        return "—"
    try:
        n = float(n)
    except Exception:
        return "—"
    if n != n:  # NaN
        return "—"
    sign = "-" if n < 0 else ""
    a = abs(n)
    if a >= 1e12:
        s = f"{a/1e12:.{decimals}f}T"
    elif a >= 1e9:
        s = f"{a/1e9:.{decimals}f}B"
    elif a >= 1e6:
        s = f"{a/1e6:.{decimals}f}M"
    elif a >= 1e3:
        s = f"{a/1e3:.{decimals}f}K"
    else:
        s = f"{a:,.{decimals}f}"
    return f"{currency_symbol}{sign}{s}"


def format_int(n) -> str:
    """Render an integer count with K/M suffixes."""
    if n is None:
        return "—"
    try:
        n = float(n)
    except Exception:
        return "—"
    if n != n:
        return "—"
    sign = "-" if n < 0 else ""
    a = abs(n)
    if a >= 1e9:
        return f"{sign}{a/1e9:.2f}B"
    if a >= 1e6:
        return f"{sign}{a/1e6:.2f}M"
    if a >= 1e3:
        return f"{sign}{a/1e3:.1f}K"
    return f"{sign}{int(a):,}"


def format_pct(p, decimals: int = 1) -> str:
    if p is None:
        return "—"
    try:
        p = float(p)
    except Exception:
        return "—"
    if p != p:
        return "—"
    sign = "+" if p > 0 else ("" if p == 0 else "")
    return f"{sign}{p:.{decimals}f}%"


def delta_color(delta: float) -> str:
    if delta is None or delta != delta:
        return NEUTRAL
    if delta > 0:
        return SUCCESS
    if delta < 0:
        return DANGER
    return NEUTRAL


# -- Country -> ISO-3 code (for choropleth maps) ----------------------------
# Just the markets actually present in the data; covers ~99% of rows.

ISO3 = {
    "Malaysia": "MYS", "Indonesia": "IDN", "Singapore": "SGP", "Thailand": "THA",
    "Vietnam": "VNM", "Philippines": "PHL", "Cambodia": "KHM", "Laos": "LAO",
    "Myanmar": "MMR", "Brunei": "BRN", "Timor-Leste": "TLS",
    "China": "CHN", "Hong Kong": "HKG", "Macao": "MAC", "Taiwan": "TWN",
    "Japan": "JPN", "South Korea": "KOR", "North Korea": "PRK", "Mongolia": "MNG",
    "India": "IND", "Pakistan": "PAK", "Bangladesh": "BGD", "Sri Lanka": "LKA",
    "Nepal": "NPL", "Bhutan": "BTN", "Maldives": "MDV", "Afghanistan": "AFG",
    "Kazakhstan": "KAZ", "Uzbekistan": "UZB", "Tajikistan": "TJK",
    "Kyrgyzstan": "KGZ", "Turkmenistan": "TKM",
    "Saudi Arabia": "SAU", "United Arab Emirates": "ARE", "Qatar": "QAT",
    "Kuwait": "KWT", "Bahrain": "BHR", "Oman": "OMN", "Yemen": "YEM",
    "Iran": "IRN", "Iraq": "IRQ", "Syria": "SYR", "Jordan": "JOR",
    "Lebanon": "LBN", "Israel": "ISR", "Palestine": "PSE", "Turkey": "TUR",
    "Egypt": "EGY", "Libya": "LBY", "Sudan": "SDN", "South Sudan": "SSD",
    "Morocco": "MAR", "Algeria": "DZA", "Tunisia": "TUN", "South Africa": "ZAF",
    "Nigeria": "NGA", "Kenya": "KEN", "Ethiopia": "ETH", "Tanzania": "TZA",
    "Uganda": "UGA", "Ghana": "GHA", "Senegal": "SEN", "Côte d'Ivoire": "CIV",
    "Cameroon": "CMR", "Zimbabwe": "ZWE", "Zambia": "ZMB", "Botswana": "BWA",
    "Mozambique": "MOZ", "Angola": "AGO", "Rwanda": "RWA", "Burundi": "BDI",
    "Somalia": "SOM", "Djibouti": "DJI", "Eritrea": "ERI", "Madagascar": "MDG",
    "Mauritius": "MUS", "Seychelles": "SYC", "Comoros": "COM", "Gambia": "GMB",
    "Guinea": "GIN", "Guinea-Bissau": "GNB", "Sierra Leone": "SLE", "Liberia": "LBR",
    "Mali": "MLI", "Burkina Faso": "BFA", "Niger": "NER", "Chad": "TCD",
    "Central African Republic": "CAF", "Republic of the Congo": "COG",
    "Democratic Republic of the Congo": "COD", "Gabon": "GAB",
    "Equatorial Guinea": "GNQ", "São Tomé and Príncipe": "STP", "Lesotho": "LSO",
    "Eswatini": "SWZ", "Namibia": "NAM", "Mauritania": "MRT", "Benin": "BEN",
    "Togo": "TGO", "Cape Verde": "CPV", "Malawi": "MWI", "Réunion": "REU",
    "United Kingdom": "GBR", "France": "FRA", "Germany": "DEU", "Italy": "ITA",
    "Spain": "ESP", "Portugal": "PRT", "Netherlands": "NLD", "Belgium": "BEL",
    "Luxembourg": "LUX", "Switzerland": "CHE", "Austria": "AUT", "Denmark": "DNK",
    "Sweden": "SWE", "Norway": "NOR", "Finland": "FIN", "Iceland": "ISL",
    "Ireland": "IRL", "Poland": "POL", "Czechia": "CZE", "Slovakia": "SVK",
    "Hungary": "HUN", "Romania": "ROU", "Bulgaria": "BGR", "Greece": "GRC",
    "Serbia": "SRB", "Croatia": "HRV", "Slovenia": "SVN",
    "Bosnia and Herzegovina": "BIH", "Montenegro": "MNE", "North Macedonia": "MKD",
    "Albania": "ALB", "Russia": "RUS", "Ukraine": "UKR", "Belarus": "BLR",
    "Moldova": "MDA", "Lithuania": "LTU", "Latvia": "LVA", "Estonia": "EST",
    "Georgia": "GEO", "Armenia": "ARM", "Azerbaijan": "AZE", "Cyprus": "CYP",
    "Malta": "MLT", "Monaco": "MCO", "Andorra": "AND", "Liechtenstein": "LIE",
    "San Marino": "SMR", "Vatican City": "VAT",
    "United States": "USA", "Canada": "CAN", "Mexico": "MEX", "Guatemala": "GTM",
    "Belize": "BLZ", "Honduras": "HND", "El Salvador": "SLV", "Nicaragua": "NIC",
    "Costa Rica": "CRI", "Panama": "PAN", "Cuba": "CUB", "Jamaica": "JAM",
    "Haiti": "HTI", "Dominican Republic": "DOM", "Puerto Rico": "PRI",
    "Trinidad and Tobago": "TTO", "Barbados": "BRB", "Bahamas": "BHS",
    "Brazil": "BRA", "Argentina": "ARG", "Chile": "CHL", "Peru": "PER",
    "Colombia": "COL", "Venezuela": "VEN", "Ecuador": "ECU", "Bolivia": "BOL",
    "Paraguay": "PRY", "Uruguay": "URY", "Suriname": "SUR", "Guyana": "GUY",
    "French Guiana": "GUF", "Dominica": "DMA", "Curaçao": "CUW", "Grenada": "GRD",
    "Bermuda": "BMU", "Antigua and Barbuda": "ATG",
    "Australia": "AUS", "New Zealand": "NZL", "Papua New Guinea": "PNG",
    "Fiji": "FJI", "Tonga": "TON", "Samoa": "WSM", "Vanuatu": "VUT",
    "Solomon Islands": "SLB", "Kiribati": "KIR", "Tuvalu": "TUV", "Nauru": "NRU",
    "Palau": "PLW", "Micronesia": "FSM", "Marshall Islands": "MHL",
}


def to_iso3(name):
    """Map English country name to ISO-3 code (or None if unknown)."""
    if name is None:
        return None
    return ISO3.get(str(name).strip())


# -- Country -> Region mapping (for the Region/Continent filter) -----------
# Six business regions, matching how mobile-recharge markets are typically
# organised (MENA is a meaningful market group, so Middle East is its own
# region). Anything not in the dict falls back to "Other".

REGION = {
    # East Asia
    "China": "Asia", "Hong Kong": "Asia", "Macao": "Asia", "Taiwan": "Asia",
    "Japan": "Asia", "South Korea": "Asia", "North Korea": "Asia", "Mongolia": "Asia",
    # Southeast Asia
    "Malaysia": "Asia", "Indonesia": "Asia", "Singapore": "Asia", "Thailand": "Asia",
    "Vietnam": "Asia", "Philippines": "Asia", "Cambodia": "Asia", "Laos": "Asia",
    "Myanmar": "Asia", "Brunei": "Asia", "Timor-Leste": "Asia",
    # South Asia
    "India": "Asia", "Pakistan": "Asia", "Bangladesh": "Asia", "Sri Lanka": "Asia",
    "Nepal": "Asia", "Bhutan": "Asia", "Maldives": "Asia", "Afghanistan": "Asia",
    # Central Asia
    "Kazakhstan": "Asia", "Uzbekistan": "Asia", "Tajikistan": "Asia",
    "Kyrgyzstan": "Asia", "Turkmenistan": "Asia",

    # Middle East (incl. Turkey)
    "Saudi Arabia": "Middle East", "United Arab Emirates": "Middle East",
    "Qatar": "Middle East", "Kuwait": "Middle East", "Bahrain": "Middle East",
    "Oman": "Middle East", "Yemen": "Middle East", "Iran": "Middle East",
    "Iraq": "Middle East", "Syria": "Middle East", "Jordan": "Middle East",
    "Lebanon": "Middle East", "Israel": "Middle East", "Palestine": "Middle East",
    "Turkey": "Middle East", "Cyprus": "Middle East",

    # Africa
    "Egypt": "Africa", "Libya": "Africa", "Sudan": "Africa", "South Sudan": "Africa",
    "Morocco": "Africa", "Algeria": "Africa", "Tunisia": "Africa",
    "South Africa": "Africa", "Nigeria": "Africa", "Kenya": "Africa",
    "Ethiopia": "Africa", "Tanzania": "Africa", "Uganda": "Africa",
    "Ghana": "Africa", "Senegal": "Africa", "Côte d'Ivoire": "Africa",
    "Cameroon": "Africa", "Zimbabwe": "Africa", "Zambia": "Africa",
    "Botswana": "Africa", "Mozambique": "Africa", "Angola": "Africa",
    "Rwanda": "Africa", "Burundi": "Africa", "Somalia": "Africa",
    "Djibouti": "Africa", "Eritrea": "Africa", "Madagascar": "Africa",
    "Mauritius": "Africa", "Seychelles": "Africa", "Comoros": "Africa",
    "Gambia": "Africa", "Guinea": "Africa", "Guinea-Bissau": "Africa",
    "Sierra Leone": "Africa", "Liberia": "Africa", "Mali": "Africa",
    "Burkina Faso": "Africa", "Niger": "Africa", "Chad": "Africa",
    "Central African Republic": "Africa",
    "Republic of the Congo": "Africa", "Democratic Republic of the Congo": "Africa",
    "Gabon": "Africa", "Equatorial Guinea": "Africa",
    "São Tomé and Príncipe": "Africa", "Lesotho": "Africa", "Eswatini": "Africa",
    "Namibia": "Africa", "Mauritania": "Africa", "Benin": "Africa",
    "Togo": "Africa", "Cape Verde": "Africa", "Malawi": "Africa",
    "Réunion": "Africa",

    # Europe
    "United Kingdom": "Europe", "France": "Europe", "Germany": "Europe",
    "Italy": "Europe", "Spain": "Europe", "Portugal": "Europe",
    "Netherlands": "Europe", "Belgium": "Europe", "Luxembourg": "Europe",
    "Switzerland": "Europe", "Austria": "Europe", "Denmark": "Europe",
    "Sweden": "Europe", "Norway": "Europe", "Finland": "Europe",
    "Iceland": "Europe", "Ireland": "Europe", "Poland": "Europe",
    "Czechia": "Europe", "Slovakia": "Europe", "Hungary": "Europe",
    "Romania": "Europe", "Bulgaria": "Europe", "Greece": "Europe",
    "Serbia": "Europe", "Croatia": "Europe", "Slovenia": "Europe",
    "Bosnia and Herzegovina": "Europe", "Montenegro": "Europe",
    "North Macedonia": "Europe", "Albania": "Europe", "Russia": "Europe",
    "Ukraine": "Europe", "Belarus": "Europe", "Moldova": "Europe",
    "Lithuania": "Europe", "Latvia": "Europe", "Estonia": "Europe",
    "Georgia": "Europe", "Armenia": "Europe", "Azerbaijan": "Europe",
    "Malta": "Europe", "Monaco": "Europe", "Andorra": "Europe",
    "Liechtenstein": "Europe", "San Marino": "Europe", "Vatican City": "Europe",

    # Americas
    "United States": "Americas", "Canada": "Americas", "Mexico": "Americas",
    "Guatemala": "Americas", "Belize": "Americas", "Honduras": "Americas",
    "El Salvador": "Americas", "Nicaragua": "Americas", "Costa Rica": "Americas",
    "Panama": "Americas", "Cuba": "Americas", "Jamaica": "Americas",
    "Haiti": "Americas", "Dominican Republic": "Americas", "Puerto Rico": "Americas",
    "Trinidad and Tobago": "Americas", "Barbados": "Americas", "Bahamas": "Americas",
    "Brazil": "Americas", "Argentina": "Americas", "Chile": "Americas",
    "Peru": "Americas", "Colombia": "Americas", "Venezuela": "Americas",
    "Ecuador": "Americas", "Bolivia": "Americas", "Paraguay": "Americas",
    "Uruguay": "Americas", "Suriname": "Americas", "Guyana": "Americas",
    "French Guiana": "Americas", "Dominica": "Americas", "Curaçao": "Americas",
    "Grenada": "Americas", "Bermuda": "Americas", "Antigua and Barbuda": "Americas",

    # Oceania
    "Australia": "Oceania", "New Zealand": "Oceania", "Papua New Guinea": "Oceania",
    "Fiji": "Oceania", "Tonga": "Oceania", "Samoa": "Oceania", "Vanuatu": "Oceania",
    "Solomon Islands": "Oceania", "Kiribati": "Oceania", "Tuvalu": "Oceania",
    "Nauru": "Oceania", "Palau": "Oceania", "Micronesia": "Oceania",
    "Marshall Islands": "Oceania",
}

REGION_ORDER = ["Asia", "Middle East", "Africa", "Europe", "Americas", "Oceania", "Other"]


def to_region(name):
    """Map English country name to a business region (or 'Other')."""
    if name is None:
        return "Other"
    return REGION.get(str(name).strip(), "Other")
