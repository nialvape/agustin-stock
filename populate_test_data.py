import argparse
import os

from dotenv import load_dotenv

load_dotenv()

from src.google_sheets import (
    get_worksheet,
    get_or_create_worksheet,
)
from src import glass as glass_utils
import src.sheet_config as config


def populate_test_data(test_fill: bool = False):
    print("=== Populating Test Data ===\n")
    populate_product_mapping()
    populate_wanted_tables(test_fill=test_fill)
    print("\n=== Test Data Population Complete ===")


def populate_product_mapping(test_stores=None):
    """Populate the product_mapping tab.

    GLASS mappings are seeded only for the stores in ``test_stores`` (defaults
    to ``['LA PLATA']`` to keep test runs manageable). Existing GLASS rows in
    the tab are removed and replaced; existing ACCESORIOS rows are preserved.
    """
    print("--- Populating product_mapping ---")

    if test_stores is None:
        test_stores = ['COTO']

    spreadsheet_id = os.environ.get('CONFIG_TABLE')
    if not spreadsheet_id:
        print("CONFIG_TABLE not set")
        return

    try:
        ws = get_worksheet(spreadsheet_id, 'product_mapping')
        if ws is None:
            ws = get_or_create_worksheet(spreadsheet_id, 'product_mapping')

        existing_values = ws.get_all_values()
        existing_headers = [h.strip().lower() for h in (existing_values[0] if existing_values else [])]

        expected = [h.lower() for h in config.PRODUCT_MAPPING_HEADERS]
        if existing_headers != expected:
            ws.clear()
            _write_header_row(ws, config.PRODUCT_MAPPING_HEADERS)
            existing_values = [config.PRODUCT_MAPPING_HEADERS]

        try:
            stock_type_idx = existing_headers.index('stock_type') if existing_headers else 2
        except ValueError:
            stock_type_idx = 2

        preserved_rows = []
        for row in existing_values[1:]:
            if not row:
                continue
            stock_type = row[stock_type_idx].strip().upper() if len(row) > stock_type_idx else ''
            if stock_type == 'GLASS':
                continue
            preserved_rows.append(row)

        ws.clear()
        _write_header_row(ws, config.PRODUCT_MAPPING_HEADERS)
        if preserved_rows:
            ws.append_rows(preserved_rows)

        existing_keys = set()
        for row in preserved_rows:
            if row and row[0]:
                existing_keys.add(row[0].strip())

        new_rows = []

        order_acc_sp = config.get_order_spreadsheet_id('ACCESORIOS')
        if order_acc_sp:
            try:
                ws_order = get_worksheet(order_acc_sp, config.ORDER_ACCESORIOS_TAB)
                if ws_order:
                    values = ws_order.get_all_values()
                    for row in values[1:]:
                        if row and len(row) > 0 and row[0]:
                            product_name = row[0].strip()
                            if product_name and product_name not in existing_keys:
                                new_rows.append([
                                    product_name,
                                    'LA PLATA',
                                    'ACCESORIOS',
                                    'ProviderA',
                                    product_name,
                                    '', '', '', '', '',
                                ])
                                existing_keys.add(product_name)
            except Exception as e:
                print(f"Skipping ORDER_ACCESORIOS: {e}")

        glass_sp = config.get_stock_spreadsheet_id('GLASS')
        order_glass_sp = config.get_order_spreadsheet_id('GLASS')
        order_index_by_store: dict = {}
        if order_glass_sp:
            for store in test_stores:
                try:
                    ws_o = get_worksheet(order_glass_sp, store)
                    if ws_o is None:
                        continue
                    order_index_by_store[store] = glass_utils.index_order_sheet(ws_o.get_all_values())
                except Exception as e:
                    print(f"Skip order index for {store}: {e}")

        if glass_sp:
            try:
                products = glass_utils.parse_glass_stock(glass_sp)
                for key in products.keys():
                    brand, sub_line, model, quality = key
                    if quality in config.GLASS_IGNORED_QUALITIES:
                        continue
                    section = config.resolve_glass_section(brand, sub_line, quality) or ''

                    for store in test_stores:
                        label = f"{brand}{('/' + sub_line) if sub_line else ''} {model} {quality} @ {store}"
                        if label in existing_keys:
                            continue
                        order_model = _match_order_model(
                            order_index_by_store.get(store, {}),
                            section,
                            model,
                        )
                        new_rows.append([
                            label,
                            store,
                            'GLASS',
                            '',
                            model,
                            brand,
                            sub_line,
                            quality,
                            section,
                            order_model,
                        ])
                        existing_keys.add(label)
            except Exception as e:
                print(f"Skipping GLASS mapping seed: {e}")

        if new_rows:
            ws.append_rows(new_rows)
        print(f"Added {len(new_rows)} product mappings")

    except Exception as e:
        print(f"Error populating product_mapping: {e}")


def populate_wanted_tables(test_fill: bool = False):
    print("--- Populating WANTED tables ---")

    for stock_type in ['ACCESORIOS', 'GLASS']:
        wanted_sp = config.get_wanted_spreadsheet_id(stock_type)
        if not wanted_sp:
            print(f"WANTED_{stock_type}_TABLE not set")
            continue

        try:
            if stock_type == 'GLASS':
                populate_wanted_glass(wanted_sp, test_fill=test_fill)
            else:
                populate_wanted_accesorios(wanted_sp)
        except Exception as e:
            print(f"Error populating WANTED_{stock_type}: {e}")


def populate_wanted_accesorios(wanted_sp: str):
    tab = config.get_wanted_tab('ACCESORIOS')
    ws = get_worksheet(wanted_sp, tab)
    if ws is None:
        ws = get_or_create_worksheet(wanted_sp, tab)

    headers = ws.get_all_values()
    if not headers or len(headers) < 1 or not headers[0] or headers[0][0].strip().lower() != 'product_name':
        ws.update(values=[['product_name', 'actual_qty', 'desired_qty', 'missing_qty']], range_name='A1')

    stock_sp = config.get_stock_spreadsheet_id('ACCESORIOS')
    if not stock_sp:
        return

    products = _parse_accessories_stock(stock_sp)
    if not products:
        return

    existing_rows = ws.get_all_values()
    existing = {}
    for i, row in enumerate(existing_rows[1:], start=2):
        if row and len(row) > 0 and row[0]:
            existing[row[0].strip()] = i

    new_rows = []
    for product_name, actual_qty in products.items():
        if product_name in existing:
            continue
        desired_qty = actual_qty + 5
        missing_qty = max(0, desired_qty - actual_qty)
        new_rows.append([product_name, actual_qty, desired_qty, missing_qty])

    if new_rows:
        ws.append_rows(new_rows)
    print(f"Updated WANTED_ACCESORIOS with {len(new_rows)} new rows")


def populate_wanted_glass(wanted_sp: str, test_fill: bool = False):
    """Clone the layout of the GLASS stock sheet into the WANTED GLASS sheet.

    If the wanted sheet is empty, the stock grid (brand headers + model names)
    is mirrored exactly. When ``test_fill`` is True the script additionally
    writes a ``desired`` value for every non-COMUN cell that is guaranteed to be
    smaller than the stock value (forces missing > 0 for every product).
    """
    stock_sp = config.get_stock_spreadsheet_id('GLASS')
    if not stock_sp:
        print("GLASS_TABLE not set")
        return

    stock_ws = get_worksheet(stock_sp, config.GLASS_TAB)
    if stock_ws is None:
        print("Stock GLASS tab not found")
        return

    stock_values = stock_ws.get_all_values()
    blocks = glass_utils.detect_blocks(stock_values)
    if not blocks:
        print("No GLASS blocks detected in stock")
        return

    wanted_ws = get_worksheet(wanted_sp, config.WANTED_GLASS_TAB)
    if wanted_ws is None:
        wanted_ws = get_or_create_worksheet(wanted_sp, config.WANTED_GLASS_TAB)

    wanted_values = wanted_ws.get_all_values()
    has_layout = bool(glass_utils.detect_blocks(wanted_values))

    if not has_layout:
        _write_glass_layout(wanted_ws, stock_values, blocks)
        wanted_values = wanted_ws.get_all_values()
        print("Cloned GLASS layout into WANTED tab")

    if test_fill:
        _fill_test_desired(wanted_ws, wanted_values, stock_values, blocks)
        print("Filled WANTED GLASS with test desired values (always > stock)")


def _write_header_row(ws, headers):
    """Write a single header row reliably, unmerging any cells in the way."""
    end_col = _col_letter(len(headers))
    try:
        ws.unmerge_cells(f"A1:{end_col}1")
    except Exception:
        pass
    ws.update(range_name=f"A1:{end_col}1", values=[list(headers)])


def _col_letter(col_1based: int) -> str:
    s = ''
    n = col_1based
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _write_glass_layout(wanted_ws, stock_values, blocks):
    n_rows = len(stock_values)
    n_cols = max((len(r) for r in stock_values), default=0)

    grid = [['' for _ in range(n_cols)] for _ in range(n_rows)]

    for block in blocks:
        hr = block['header_row']
        if hr >= n_rows:
            continue
        for offset, col in enumerate((
            block['model_col'],
            block['comun_col'],
            block['qty5d_col'],
            block['qtyosc_col'],
        )):
            if col < n_cols and hr < len(stock_values) and col < len(stock_values[hr]):
                grid[hr][col] = stock_values[hr][col]

        for model, row_idx in zip(block['models'], block['model_rows']):
            if row_idx < n_rows and block['model_col'] < n_cols:
                grid[row_idx][block['model_col']] = model

    if n_rows == 0 or n_cols == 0:
        return

    end_cell = f"{_col_letter(n_cols)}{n_rows}"
    wanted_ws.update(values=grid, range_name=f"A1:{end_cell}")


def _fill_test_desired(wanted_ws, wanted_values, stock_values, blocks):
    n_rows = max(len(wanted_values), len(stock_values))
    n_cols = max(
        max((len(r) for r in wanted_values), default=0),
        max((len(r) for r in stock_values), default=0),
    )

    grid = [['' for _ in range(n_cols)] for _ in range(n_rows)]
    for r_idx, row in enumerate(wanted_values):
        for c_idx, val in enumerate(row):
            grid[r_idx][c_idx] = val

    for block in blocks:
        for model, row_idx in zip(block['models'], block['model_rows']):
            stock_row = stock_values[row_idx] if row_idx < len(stock_values) else []
            for quality, col in (
                ('5D', block['qty5d_col']),
                ('OSC', block['qtyosc_col']),
            ):
                actual = 0
                if col < len(stock_row):
                    try:
                        v = stock_row[col]
                        actual = int(float(v)) if str(v).strip() else 0
                    except (ValueError, TypeError):
                        actual = 0
                desired = actual + 2 if actual > 0 else 1
                if col < n_cols and row_idx < n_rows:
                    grid[row_idx][col] = desired

    if n_rows == 0 or n_cols == 0:
        return

    end_cell = f"{_col_letter(n_cols)}{n_rows}"
    wanted_ws.update(values=grid, range_name=f"A1:{end_cell}")


def _match_order_model(order_index, section, stock_model):
    """Try to map a stock model to an existing order-sheet model within a section.

    Stock and order sheets use slightly different name conventions
    (``A06/A07 `` vs ``A06``, ``IP X/XS/11PRO`` vs ``X/XS/11PRO``,
    ``REDMI A5`` vs ``A05/RD 13C``...).  This helper tries several strategies
    and returns the order-sheet name when a match is found, otherwise the
    original stock model (as a placeholder for manual editing).
    """
    if not section or not order_index:
        return stock_model

    section_keys = {model: (row, col) for (s, model), (row, col) in order_index.items() if s == section}
    if not section_keys:
        return stock_model

    stock_norm = glass_utils.normalize_model_name(stock_model)
    if stock_norm in section_keys:
        return stock_norm

    stock_tokens = [t for t in stock_model.replace('/', ' ').split() if t]
    for token in stock_tokens:
        nt = glass_utils.normalize_model_name(token)
        if nt and nt in section_keys:
            return nt

    for order_norm in section_keys.keys():
        order_tokens = order_norm.replace('/', ' ').split()
        for ot in order_tokens:
            ot_norm = glass_utils.normalize_model_name(ot)
            for st in stock_tokens:
                st_norm = glass_utils.normalize_model_name(st)
                if ot_norm and ot_norm == st_norm:
                    return order_norm

    return stock_model


def _parse_accessories_stock(spreadsheet_id):
    products = {}
    try:
        ws = get_worksheet(spreadsheet_id, config.ACCESORIOS_TAB)
        if ws is None:
            return products
        values = ws.get_all_values()
        for row in values[1:]:
            product_a = row[0] if len(row) > 0 else None
            qty_a = row[1] if len(row) > 1 else None
            product_c = row[2] if len(row) > 2 else None

            if product_a and product_a.strip() and product_a.strip() not in ('CARGADORES', 'PARLANTES'):
                qty = 0
                if qty_a:
                    try:
                        qty = int(float(qty_a))
                    except (ValueError, TypeError):
                        qty = 0
                products[product_a.strip()] = qty
            if product_c and product_c.strip():
                qty = 0
                if qty_a:
                    try:
                        qty = int(float(qty_a))
                    except (ValueError, TypeError):
                        qty = 0
                products[product_c.strip()] = qty
    except Exception as e:
        print(f"Error parsing accessories stock: {e}")
    return products


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate test/wanted data")
    parser.add_argument('--test-fill', action='store_true',
                        help="Fill WANTED GLASS with desired = max(actual-2,1) "
                             "to force missing>0 for every product")
    args = parser.parse_args()
    populate_test_data(test_fill=args.test_fill)
