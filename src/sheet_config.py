import os


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
}

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
    'order_model_name',
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


def get_store_columns_order_accesorios():
    return ORDER_GLASS_STORES.copy()
