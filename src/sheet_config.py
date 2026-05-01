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


GLASS_TABS = ['PANTALLA', 'CAMARAS', 'RELOJES-AIRPODS']

ACCESORIOS_TAB = 'ACCESORIOS'


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


def get_stock_tabs(stock_type: str):
    if stock_type == 'GLASS':
        return GLASS_TABS
    elif stock_type == 'ACCESORIOS':
        return [ACCESORIOS_TAB]
    return []


def get_order_glass_tabs():
    return ORDER_GLASS_STORES


def get_wanted_tab(stock_type: str):
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