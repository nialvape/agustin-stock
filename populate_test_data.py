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
    """Append missing rows to product_mapping without overwriting user edits.

    - ``product_name`` holds the model name exactly as it appears in the stock
      sheet (e.g. ``A02/A02S``).
    - ``provider_product_name`` is left blank for the user to fill in with the
      name the provider uses for that product.
    - GLASS rows are seeded as generic (empty ``store``) by default so they
      apply to every store. A store-specific row in the sheet acts as an
      override.
    - Rows are deduped by the natural key
      ``(brand, sub_line, quality, product_name, store)``.
    """
    print("--- Populating product_mapping ---")

    if test_stores is None:
        test_stores = ['']

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
            migrated = _migrate_product_mapping_rows(existing_headers, existing_values[1:] if existing_values else [])
            ws.clear()
            _write_header_row(ws, config.PRODUCT_MAPPING_HEADERS)
            if migrated:
                ws.append_rows(migrated)
            existing_values = ws.get_all_values()
            existing_headers = [h.strip().lower() for h in existing_values[0]]
            print(f"Migrated {len(migrated)} existing rows to current schema")

        def _col(name):
            try:
                return existing_headers.index(name)
            except ValueError:
                return -1

        idx_product = _col('product_name')
        idx_store = _col('store')
        idx_stock_type = _col('stock_type')
        idx_brand = _col('brand')
        idx_sub = _col('sub_line')
        idx_quality = _col('quality')

        def _get(row, i):
            return row[i].strip() if 0 <= i < len(row) else ''

        existing_glass_keys = set()
        existing_acc_products = set()
        for row in existing_values[1:]:
            if not row:
                continue
            stock_type = _get(row, idx_stock_type).upper()
            if stock_type == 'GLASS':
                key = (
                    _get(row, idx_brand).upper(),
                    _get(row, idx_sub).upper(),
                    _get(row, idx_quality).upper(),
                    _get(row, idx_product),
                    _get(row, idx_store),
                )
                existing_glass_keys.add(key)
            elif stock_type == 'ACCESORIOS':
                existing_acc_products.add(_get(row, idx_product))

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
                            if product_name and product_name not in existing_acc_products:
                                new_rows.append([
                                    product_name,
                                    '',
                                    'ACCESORIOS',
                                    '',
                                    product_name,
                                    '', '', '', '',
                                ])
                                existing_acc_products.add(product_name)
            except Exception as e:
                print(f"Skipping ORDER_ACCESORIOS: {e}")

        glass_sp = config.get_stock_spreadsheet_id('GLASS')
        order_glass_sp = config.get_order_spreadsheet_id('GLASS')
        order_index_by_store: dict = {}
        if order_glass_sp:
            for store in test_stores:
                if not store:
                    continue
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
                        natural_key = (
                            brand.upper(), sub_line.upper(), quality.upper(),
                            model, store,
                        )
                        if natural_key in existing_glass_keys:
                            continue
                        order_model = (
                            _match_order_model(order_index_by_store.get(store, {}), section, model)
                            if store else model
                        )
                        new_rows.append([
                            model,
                            store,
                            'GLASS',
                            '',
                            order_model,
                            brand,
                            sub_line,
                            quality,
                            section,
                        ])
                        existing_glass_keys.add(natural_key)
            except Exception as e:
                print(f"Skipping GLASS mapping seed: {e}")

        if new_rows:
            ws.append_rows(new_rows)
        print(f"Added {len(new_rows)} product mappings (existing rows preserved)")

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

    # The wanted sheet now uses a visual layout maintained manually:
    #   columns A/E = product names grouped by category headers
    #   columns D/H = missing quantities
    # We do not overwrite or auto-populate rows so the manual layout stays intact.
    print(f"WANTED_ACCESORIOS sheet '{tab}' ready (manual layout preserved)")


def populate_wanted_glass(wanted_sp: str, test_fill: bool = False):
    """Rebuild the WANTED GLASS layout, preserving user-entered desired values.

    Next to COMUN/5D/OSC there is a ``stock`` column with ``IMPORTRANGE`` pointing
    at the same cell on the stock sheet. The spreadsheet URL is read from
    ``config.WANTED_GLASS_STOCK_URL_CELL`` (default ``$Q$1``) so duplicating
    the wanted file only requires updating that cell. Formulas use ``;`` as the
    argument separator (locale used in Spanish Google Sheets).

    When ``test_fill`` is True the desired columns for 5D/OSC get ``actual + 2``
    (or 1 if stock=0) using the stock snapshot from the API (not the formula).
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
    stock_blocks = glass_utils.detect_blocks(stock_values)
    if not stock_blocks:
        print("No GLASS blocks detected in stock")
        return

    wanted_ws = get_worksheet(wanted_sp, config.WANTED_GLASS_TAB)
    if wanted_ws is None:
        wanted_ws = get_or_create_worksheet(wanted_sp, config.WANTED_GLASS_TAB)

    wanted_values = wanted_ws.get_all_values()
    existing_desired = _extract_existing_desired(wanted_values)

    _write_glass_layout_with_stock(
        wanted_ws,
        stock_values,
        stock_blocks,
        existing_desired=existing_desired,
        test_fill=test_fill,
    )
    if test_fill:
        print(
            "Wrote WANTED GLASS (IMPORTRANGE desde "
            f"{config.WANTED_GLASS_STOCK_URL_CELL}; verificar URL en Q1) + test desired"
        )
    else:
        print(
            "Wrote WANTED GLASS (IMPORTRANGE desde "
            f"{config.WANTED_GLASS_STOCK_URL_CELL}; poner URL del stock en Q1 si falta)"
        )


def _extract_existing_desired(wanted_values):
    """Pull existing (brand, sub, model, quality) -> desired_qty from a wanted sheet.

    Robust against both the legacy 4-col layout and the new 7-col layout because
    detect_blocks now accepts both.
    """
    desired = {}
    if not wanted_values:
        return desired
    blocks = glass_utils.detect_blocks(wanted_values)
    for block in blocks:
        for model, row_idx in zip(block['models'], block['model_rows']):
            row = wanted_values[row_idx] if row_idx < len(wanted_values) else []
            for quality, col in block['qualities'].items():
                if col < len(row):
                    cell = row[col]
                    if cell and str(cell).strip():
                        try:
                            desired[(block['brand'], block['sub_line'], model, quality)] = int(float(cell))
                        except (ValueError, TypeError):
                            pass
    return desired


def _migrate_product_mapping_rows(old_headers, old_rows):
    """Convert legacy product_mapping rows to the current 9-column schema.

    Legacy schema had a 10th column ``order_model_name`` and the ``product_name``
    column held a synthetic label (``"BRAND/SUB MODEL QUALITY @ STORE"``) while
    the stock model lived in ``provider_product_name``.

    The current schema is:
        product_name           -> stock model (e.g. "A02/A02S")
        provider_product_name  -> order-sheet model (what the provider uses)
        order_section          -> section in the order sheet
        (no order_model_name column)

    For each legacy GLASS row we copy ``provider_product_name`` into
    ``product_name`` and ``order_model_name`` into ``provider_product_name``.
    ACCESORIOS rows keep their values; the extra column is dropped.
    """
    def col(name):
        try:
            return old_headers.index(name)
        except ValueError:
            return -1

    idx_pn = col('product_name')
    idx_store = col('store')
    idx_stype = col('stock_type')
    idx_prov = col('provider')
    idx_ppn = col('provider_product_name')
    idx_brand = col('brand')
    idx_sub = col('sub_line')
    idx_quality = col('quality')
    idx_section = col('order_section')
    idx_omn = col('order_model_name')

    def cell(row, i):
        return row[i].strip() if 0 <= i < len(row) else ''

    migrated = []
    for row in old_rows:
        if not row or not any(c.strip() for c in row if c is not None):
            continue
        stype = cell(row, idx_stype).upper()
        product_name = cell(row, idx_pn)
        provider_product_name = cell(row, idx_ppn)
        order_model_name = cell(row, idx_omn) if idx_omn >= 0 else ''

        if stype == 'GLASS':
            stock_model = provider_product_name or product_name
            order_model = order_model_name or provider_product_name
            new_row = [
                stock_model,
                cell(row, idx_store),
                'GLASS',
                cell(row, idx_prov),
                order_model,
                cell(row, idx_brand),
                cell(row, idx_sub),
                cell(row, idx_quality),
                cell(row, idx_section),
            ]
        else:
            new_row = [
                product_name,
                cell(row, idx_store),
                stype or 'ACCESORIOS',
                cell(row, idx_prov),
                provider_product_name or product_name,
                cell(row, idx_brand),
                cell(row, idx_sub),
                cell(row, idx_quality),
                cell(row, idx_section),
            ]
        migrated.append(new_row)
    return migrated


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


def _write_glass_layout_with_stock(
    wanted_ws,
    stock_values,
    stock_blocks,
    existing_desired=None,
    test_fill=False,
):
    """Render the wanted sheet with interleaved desired/stock columns.

    For each stock block we emit seven columns::

        BRAND | COMUN | stock | 5D | stock | OSC | stock

    Each ``stock`` cell is ``=IMPORTRANGE($Q$1;"GLASS!<col><row>")`` using ``;``
    as the list separator. Put the stock workbook URL in Q1 (see
    ``WANTED_GLASS_STOCK_URL_CELL``).
    """
    existing_desired = existing_desired or {}

    n_rows = len(stock_values)
    if n_rows == 0:
        return

    block_width = 7
    stock_model_cols = sorted({b['model_col'] for b in stock_blocks})
    wanted_offset = {sc: i * block_width for i, sc in enumerate(stock_model_cols)}
    total_cols = max(wanted_offset.values()) + block_width if wanted_offset else block_width

    grid = [['' for _ in range(total_cols)] for _ in range(n_rows)]

    source_tab = config.GLASS_TAB
    url_ref = config.WANTED_GLASS_STOCK_URL_CELL

    def _stock_formula(stock_row_1based: int, stock_col_1based: int) -> str:
        col_a1 = _col_letter(stock_col_1based)
        return (
            f'=IMPORTRANGE({url_ref};"{source_tab}!{col_a1}{stock_row_1based}")'
        )

    qualities_order = ['COMUN', '5D', 'OSC']

    for block in stock_blocks:
        offset = wanted_offset[block['model_col']]
        hr = block['header_row']
        brand = block['brand']

        grid[hr][offset] = brand
        for i, q in enumerate(qualities_order):
            grid[hr][offset + 1 + i * 2] = q
            grid[hr][offset + 2 + i * 2] = 'stock'

        for model, row_idx in zip(block['models'], block['model_rows']):
            grid[row_idx][offset] = model

            stock_row_1based = row_idx + 1
            stock_row_api = stock_values[row_idx] if row_idx < len(stock_values) else []

            for i, q in enumerate(qualities_order):
                desired_col = offset + 1 + i * 2
                stock_col_idx = offset + 2 + i * 2

                stock_quality_col_0based = block['qualities'][q]
                stock_quality_col_1based = stock_quality_col_0based + 1

                grid[row_idx][stock_col_idx] = _stock_formula(
                    stock_row_1based, stock_quality_col_1based
                )

                qty_live = glass_utils._to_int(
                    stock_row_api[stock_quality_col_0based]
                    if stock_quality_col_0based < len(stock_row_api)
                    else ''
                )

                preserved = existing_desired.get(
                    (brand, block['sub_line'], model, q)
                )

                if q in config.GLASS_IGNORED_QUALITIES:
                    if preserved is not None:
                        grid[row_idx][desired_col] = preserved
                    continue

                if preserved is not None:
                    grid[row_idx][desired_col] = preserved
                elif test_fill:
                    actual = qty_live
                    grid[row_idx][desired_col] = actual + 2 if actual > 0 else 1

    end_cell = f"{_col_letter(total_cols)}{n_rows}"
    wanted_ws.update(
        values=grid,
        range_name=f"A1:{end_cell}",
        value_input_option='USER_ENTERED',
    )


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
