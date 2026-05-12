"""Opcional: volcar mapeos WANTED→ORDER en ``product_mapping`` (filas A2:I219).

Usa la misma lógica que ``generate_order`` (alias + exacto + normalizado + fuzzy).

Uso::

    python sync_accessories_mapping.py
    python sync_accessories_mapping.py --apply
    python sync_accessories_mapping.py --apply --allow-partial   # escribe aunque falten algunos nombres

Requiere ``.env`` con ``CONFIG_TABLE``, ``GOOGLE_APPLICATION_CREDENTIALS``.
WANTED y ORDER se leen de CONFIG: pestaña ``stores`` (columna C = wanted accesorios)
y pestaña ``providers`` (columna ``order`` = link del pedido por proveedor).
Si falta alguno, se puede usar como respaldo ``WANTED_ACCESORIOS_TABLE`` /
``ORDER_ACCESORIOS_TABLE`` en ``.env``.
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from src.google_sheets import get_worksheet
import src.sheet_config as config
from src import accesorios_order_match as acc_match


def _default_provider() -> str:
    spreadsheet_id = os.environ.get('CONFIG_TABLE')
    if not spreadsheet_id:
        return 'ProviderA'
    try:
        ws = get_worksheet(spreadsheet_id, 'providers')
        if ws is None:
            return 'ProviderA'
        for row in ws.get_all_values()[1:]:
            if row and str(row[0]).strip():
                return str(row[0]).strip()
    except Exception:
        pass
    return 'ProviderA'


def main():
    parser = argparse.ArgumentParser(description='Sync WANTED→ORDER accesorios mappings')
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Write product_mapping A2:I219',
    )
    parser.add_argument(
        '--allow-partial',
        action='store_true',
        help='With --apply, write even if some wanted names have no match (listados en consola)',
    )
    args = parser.parse_args()

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
        print('WANTED accesorios: definí la pestaña stores (col. C) o WANTED_ACCESORIOS_TABLE en .env')
        sys.exit(1)

    providers = config.load_providers_from_config()
    order_names_sources = []
    for pdata in providers.values():
        oid = (pdata.get('order_spreadsheet_id') or '').strip()
        if oid:
            order_names_sources.append(oid)
    order_id = order_names_sources[0] if order_names_sources else (
        config.get_order_spreadsheet_id('ACCESORIOS') or ''
    ).strip()
    if not order_id:
        print('ORDER accesorios: columna order en providers o ORDER_ACCESORIOS_TABLE en .env')
        sys.exit(1)

    wanted_tab = config.get_wanted_tab('ACCESORIOS')
    ws_w = get_worksheet(wanted_id, wanted_tab)
    if ws_w is None:
        print(f'WANTED tab not found: {wanted_tab!r}')
        sys.exit(1)
    wanted_values = ws_w.get_all_values()
    wanted_names = acc_match.collect_wanted_product_names(wanted_values)
    print(f'WANTED products with faltante>0 (unique): {len(wanted_names)}')

    order_names_set = set()
    order_names = []
    for oid in order_names_sources or [order_id]:
        for n in acc_match.load_order_accesorios_product_names(oid, config.ORDER_ACCESORIOS_TAB):
            if n not in order_names_set:
                order_names_set.add(n)
                order_names.append(n)
    print(f'ORDER column A products (excl. section labels, union por proveedor): {len(order_names)}')

    mapping, failures = acc_match.build_wanted_to_order_map(wanted_names, order_names)
    print(f'Matches: {len(mapping)}')
    if failures:
        print(f'Sin match ({len(failures)}):')
        for n in sorted(failures)[:50]:
            print(f'  - {n}')
        if len(failures) > 50:
            print(f'  ... and {len(failures) - 50} more')

    if args.apply and failures and not args.allow_partial:
        print('Not writing: use --allow-partial to write matched rows anyway.')
        sys.exit(1)

    provider = _default_provider()
    print(f'Default provider for synced rows: {provider!r}')

    max_rows = 218
    if len(mapping) > max_rows:
        print(f'ERROR: {len(mapping)} mappings exceed block size {max_rows}.')
        sys.exit(1)

    rows = []
    for w in sorted(mapping.keys()):
        order_name = mapping[w]
        rows.append([
            w,
            '',
            'ACCESORIOS',
            provider,
            order_name,
            '', '', '', '',
        ])
    while len(rows) < max_rows:
        rows.append(['', '', '', '', '', '', '', '', ''])

    if not args.apply:
        print('Dry-run. Use --apply [--allow-partial] to write product_mapping A2:I219.')
        sys.exit(0)

    ws_pm = get_worksheet(config_id, 'product_mapping')
    if ws_pm is None:
        print('product_mapping worksheet not found')
        sys.exit(1)

    end = f'I{1 + max_rows}'
    ws_pm.update(
        range_name=f'A2:{end}',
        values=rows,
        value_input_option='USER_ENTERED',
    )
    print(f'Wrote {len(mapping)} mapping rows to product_mapping A2:{end}.')
    if failures:
        print('Quedaron nombres sin fila en el bloque (revisá la consola arriba).')


if __name__ == '__main__':
    main()
