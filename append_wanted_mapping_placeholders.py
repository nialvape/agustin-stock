"""Completa ``product_mapping`` con nombres WANTED aún no mapeados (solo filas 138–219).

- No borra ni modifica filas por encima de la 137.
- Solo usa filas 138 a 219 (inclusive) donde ``product_name`` está vacío.
- Cada fila nueva: ``product_name`` = texto WANTED, ``stock_type`` = ACCESORIOS,
  ``provider`` y ``provider_product_name`` vacíos (completás el pedido a mano).
- No agrega un nombre si ya existe en **cualquier** fila ACCESORIOS con el mismo
  ``product_name`` (evita duplicados aunque ``provider_product_name`` esté vacío).

Uso::

    python append_wanted_mapping_placeholders.py

Requiere ``.env`` con ``CONFIG_TABLE``, ``GOOGLE_APPLICATION_CREDENTIALS``.
WANTED accesorios: primera fila de la pestaña ``stores`` (columna C) o
``WANTED_ACCESORIOS_TABLE`` en ``.env``.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from src.google_sheets import get_worksheet
import src.sheet_config as config
from src import accesorios_order_match as acc_match

FIRST_PLACEHOLDER_ROW = 138
LAST_PLACEHOLDER_ROW = 219


def _col_letter(n: int) -> str:
    s = ''
    x = n
    while x > 0:
        x, r = divmod(x - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    config_id = os.environ.get('CONFIG_TABLE')
    if not config_id:
        print('CONFIG_TABLE must be set')
        sys.exit(1)

    stores = config.load_stores_rows()
    wanted_id = ''
    if stores:
        wanted_id = (stores[0].get('wanted_accesorios_id') or '').strip()
    if not wanted_id:
        wanted_id = (config.get_wanted_spreadsheet_id('ACCESORIOS') or '').strip()
    if not wanted_id:
        print('WANTED: pestaña stores (col. C) o WANTED_ACCESORIOS_TABLE en .env')
        sys.exit(1)

    wanted_tab = config.get_wanted_tab('ACCESORIOS')
    ws_w = get_worksheet(wanted_id, wanted_tab)
    if ws_w is None:
        print(f'WANTED tab not found: {wanted_tab!r}')
        sys.exit(1)

    wanted_values = ws_w.get_all_values()
    all_names = acc_match.collect_all_wanted_product_names(wanted_values)
    print(f'Nombres en WANTED (A/E, todos): {len(all_names)}')

    ws_pm = get_worksheet(config_id, 'product_mapping')
    if ws_pm is None:
        print('product_mapping not found')
        sys.exit(1)

    pm_rows = ws_pm.get_all_values()
    if not pm_rows:
        print('product_mapping is empty')
        sys.exit(1)

    headers = [str(h).strip().lower() for h in pm_rows[0]]

    def col(name: str) -> int:
        try:
            return headers.index(name)
        except ValueError:
            return -1

    i_pn = col('product_name')
    i_st = col('stock_type')
    if i_pn < 0 or i_st < 0:
        print('product_mapping must have product_name and stock_type columns')
        sys.exit(1)

    def row_key(product: str) -> str:
        return product.strip().casefold()

    def cell(row, idx: int) -> str:
        if idx < 0 or idx >= len(row):
            return ''
        return str(row[idx]).strip()

    # Ya existe fila ACCESORIOS con este product_name (cualquier fila del sheet)
    existing_product_keys: set = set()
    for row in pm_rows[1:]:
        if not row:
            continue
        if cell(row, i_st).upper() != 'ACCESORIOS':
            continue
        pn = cell(row, i_pn)
        if pn:
            existing_product_keys.add(row_key(pn))

    candidates = [n for n in all_names if row_key(n) not in existing_product_keys]
    print(f'Sin fila ACCESORIOS para ese product_name: {len(candidates)}')

    free_rows: list = []
    for r in range(FIRST_PLACEHOLDER_ROW, LAST_PLACEHOLDER_ROW + 1):
        idx = r - 1
        if idx >= len(pm_rows):
            free_rows.append(r)
            continue
        row = pm_rows[idx]
        pn = cell(row, i_pn)
        if not pn:
            free_rows.append(r)

    print(f'Filas vacías en {FIRST_PLACEHOLDER_ROW}-{LAST_PLACEHOLDER_ROW}: {len(free_rows)}')

    if not candidates:
        print('Nada que agregar.')
        return

    if len(candidates) > len(free_rows):
        print(
            f'ERROR: hacen falta {len(candidates)} filas y solo hay {len(free_rows)} '
            f'vacías en el bloque. Liberá celdas o ampliá el rango en el script.'
        )
        sys.exit(1)

    batch_updates = []
    for i, name in enumerate(candidates):
        r = free_rows[i]
        vals = [''] * len(headers)
        vals[i_pn] = name
        vals[i_st] = 'ACCESORIOS'
        end_col = _col_letter(len(headers))
        rng = f'A{r}:{end_col}{r}'
        batch_updates.append({'range': rng, 'values': [vals]})

    if batch_updates:
        chunk = 100
        for i in range(0, len(batch_updates), chunk):
            part = batch_updates[i : i + chunk]
            try:
                ws_pm.batch_update(part, value_input_option='USER_ENTERED')
            except TypeError:
                ws_pm.batch_update(part)

    print(f'Escritas {len(batch_updates)} fila(s) en {FIRST_PLACEHOLDER_ROW}-{LAST_PLACEHOLDER_ROW} (sin tocar filas < {FIRST_PLACEHOLDER_ROW}).')


if __name__ == '__main__':
    main()
