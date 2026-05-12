import os
import re


SPREADSHEET_IDS = {
    'GLASS_TABLE': os.environ.get('GLASS_TABLE', ''),
    'ACCESORIOS_TABLE': os.environ.get('ACCESORIOS_TABLE', ''),
    'WANTED_GLASS_TABLE': os.environ.get('WANTED_GLASS_TABLE', ''),
    'WANTED_ACCESORIOS_TABLE': os.environ.get('WANTED_ACCESORIOS_TABLE', ''),
    'ORDER_GLASS_TABLE': os.environ.get('ORDER_GLASS_TABLE', ''),
    'ORDER_ACCESORIOS_TABLE': os.environ.get('ORDER_ACCESORIOS_TABLE', ''),
    'CONFIG_TABLE': os.environ.get('CONFIG_TABLE', ''),
}


GLASS_TAB = 'GLASS'
WANTED_GLASS_TAB = 'GLASS'

# Full URL of the stock spreadsheet, typed in this cell of the WANTED file (IMPORTRANGE first argument = $Q$1).
WANTED_GLASS_STOCK_URL_CELL = '$Q$1'

ACCESORIOS_TAB = 'ACCESORIOS'
WANTED_ACCESORIOS_TAB = 'STOCK'

GLASS_QUALITIES = ['COMUN', '5D', 'OSC']
GLASS_IGNORED_QUALITIES = {'COMUN'}

GLASS_BRANDS = {'SAMSUNG', 'MOTOROLA', 'IPHONE', 'XIAOMI'}


SECTION_IPHONE_1200 = 'FILM ANTIESPIA NUEVOS INGRESOS $1.200'
SECTION_SAMSUNG_1500 = 'FILM ANTIESTATIC CON HUELLA LINEA SAMSUNG $1500'
SECTION_SAMSUNG_2500 = 'FILM ANTIESPIA CON HUELLA LINEA SAMSUNG $2500'
SECTION_PUXIDA = 'FILM PREMIUM PUXIDA'

ORDER_GLASS_SECTIONS = [
    SECTION_IPHONE_1200,
    SECTION_SAMSUNG_1500,
    SECTION_SAMSUNG_2500,
    SECTION_PUXIDA,
]

ORDER_GLASS_LEGACY_SECTIONS = {'IPHONE 9D', 'REDMI 9D'}
ORDER_GLASS_LEGACY_TABS = {'CARRE', 'CARRE (4)'}

ORDER_GLASS_COLUMN_PAIRS = [
    (1, 2, 1),
    (3, 4, 3),
    (6, 7, 6),
    (8, 9, 6),
]


ORDER_GLASS_STORES = [
    'COTO', 'MONTE', 'BELLA', 'PILAR', 'VELEZ', 'MERLO',
    'SANFER', 'LA PLATA', 'GLEW', 'SAN MARTIN', 'ZARATE'
]

ORDER_ACCESORIOS_TAB = 'ACCE'

WANTED_TAB = 'STOCK'

CONFIG_TABS = {
    'providers': 'providers',
    'product_mapping': 'product_mapping',
    'stores': 'stores',
}

STORES_TAB = 'stores'


def get_config_table_id() -> str:
    return (os.environ.get('CONFIG_TABLE') or '').strip()


def extract_spreadsheet_id(value: str) -> str:
    """Google Sheet id from a raw id or a full /spreadsheets/d/... URL."""
    s = (value or '').strip()
    if not s:
        return ''
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', s)
    if m:
        return m.group(1)
    m = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', s)
    if m:
        return m.group(1)
    if re.fullmatch(r'[a-zA-Z0-9_-]{30,}', s):
        return s
    return s


def load_stores_rows():
    """Rows from config ``stores`` tab: store, GLASS wanted link, ACCESORIOS wanted link.

    Column A = nombre del local (p. ej. NAME en fila 1), B = GLASS, C = ACCESORIOS.
    Optional header row if la celda A parece título (NAME, store, local, etc.).
    """
    from .google_sheets import get_worksheet

    cid = get_config_table_id()
    if not cid:
        return []
    ws = get_worksheet(cid, STORES_TAB)
    if ws is None:
        return []
    try:
        values = ws.get_all_values()
    except Exception:
        return []
    if not values:
        return []
    start = 0
    first = str(values[0][0]).strip().lower() if values[0] else ''
    _STORE_HEADER_A = (
        'store', 'local', 'tienda', 'sucursal', 'name', 'nombre', 'localidad',
    )
    if first in _STORE_HEADER_A:
        start = 1
    out = []
    for row in values[start:]:
        if not row:
            continue
        name = str(row[0]).strip() if len(row) > 0 else ''
        if not name:
            continue
        glass_link = str(row[1]).strip() if len(row) > 1 else ''
        acc_link = str(row[2]).strip() if len(row) > 2 else ''
        out.append({
            'store': name,
            'wanted_glass_id': extract_spreadsheet_id(glass_link),
            'wanted_accesorios_id': extract_spreadsheet_id(acc_link),
        })
    return out


def _providers_table_columns(values):
    """Detecta fila de encabezados y columnas provider / code / order (0-based).

    Soporta:
    - Layout clásico: col A = provider, B = code, D = order (fila 1 sin encabezado).
    - Layout con encabezado en B:C:D (fila 1 vacía o no): ``provider``, ``code``, ``order``.
    """
    if not values:
        return 0, 0, 1, 3

    for r in range(min(15, len(values))):
        row = values[r]
        if not row:
            continue
        cells = [str(c).strip().lower() for c in row]
        ip = next(
            (i for i, c in enumerate(cells) if c in ('provider', 'proveedor')),
            None,
        )
        if ip is None:
            continue
        ic = next((i for i, c in enumerate(cells) if c in ('code', 'codigo')), None)
        io = next(
            (
                i
                for i, c in enumerate(cells)
                if c in ('order', 'order_sheet', 'pedido', 'sheet')
            ),
            None,
        )
        if ic is not None and io is not None:
            return r + 1, ip, ic, io

    return 0, 0, 1, 3


def load_providers_from_config():
    """Provider rows: proveedor, código y link de planilla de pedido (columna ``order``).

    Returns dict ``name -> {'code': str, 'order_spreadsheet_id': str}``.
    """
    from .google_sheets import get_worksheet

    cid = get_config_table_id()
    if not cid:
        return {}
    ws = get_worksheet(cid, 'providers')
    if ws is None:
        return {}
    try:
        values = ws.get_all_values()
    except Exception:
        return {}
    if not values:
        return {}
    start, col_p, col_c, col_o = _providers_table_columns(values)
    out = {}
    for row in values[start:]:
        if not row:
            continue
        max_i = max(col_p, col_c, col_o)
        if len(row) <= max_i:
            continue
        provider = str(row[col_p]).strip()
        code = str(row[col_c]).strip() if col_c < len(row) else ''
        if not provider:
            continue
        if provider.lower() in ('provider', 'proveedor'):
            continue
        order_cell = str(row[col_o]).strip() if col_o < len(row) else ''
        out[provider] = {
            'code': code,
            'order_spreadsheet_id': extract_spreadsheet_id(order_cell),
        }
    return out

PRODUCT_MAPPING_HEADERS = [
    'product_name',
    'store',
    'stock_type',
    'provider',
    'provider_product_name',
    'brand',
    'sub_line',
    'quality',
    'order_section',
]


def resolve_glass_section(brand: str, sub_line: str, quality: str):
    brand_u = (brand or '').strip().upper()
    sub_u = (sub_line or '').strip().upper()
    q = (quality or '').strip().upper()

    if q in GLASS_IGNORED_QUALITIES:
        return None
    if q == 'OSC':
        if brand_u == 'IPHONE':
            return SECTION_IPHONE_1200
        if brand_u == 'SAMSUNG' and sub_u == 'A':
            return SECTION_IPHONE_1200
        if brand_u == 'SAMSUNG' and sub_u == 'S':
            return SECTION_SAMSUNG_2500
        return None
    if q == '5D':
        if brand_u == 'SAMSUNG' and sub_u == 'S':
            return SECTION_SAMSUNG_1500
        return SECTION_PUXIDA
    return None


def get_stock_tabs(stock_type: str):
    if stock_type == 'GLASS':
        return [GLASS_TAB]
    elif stock_type == 'ACCESORIOS':
        return [ACCESORIOS_TAB]
    return []


def get_wanted_tab(stock_type: str):
    if stock_type == 'GLASS':
        return WANTED_GLASS_TAB
    return WANTED_TAB


def get_wanted_spreadsheet_id(stock_type: str):
    if stock_type == 'GLASS':
        return SPREADSHEET_IDS.get('WANTED_GLASS_TABLE')
    elif stock_type == 'ACCESORIOS':
        return SPREADSHEET_IDS.get('WANTED_ACCESORIOS_TABLE')
    return None


def get_stock_spreadsheet_id(stock_type: str):
    if stock_type == 'GLASS':
        return SPREADSHEET_IDS.get('GLASS_TABLE')
    elif stock_type == 'ACCESORIOS':
        return SPREADSHEET_IDS.get('ACCESORIOS_TABLE')
    return None


def get_order_spreadsheet_id(stock_type: str):
    if stock_type == 'GLASS':
        return SPREADSHEET_IDS.get('ORDER_GLASS_TABLE')
    elif stock_type == 'ACCESORIOS':
        return SPREADSHEET_IDS.get('ORDER_ACCESORIOS_TABLE')
    return None

