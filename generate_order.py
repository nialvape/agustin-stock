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


def load_providers():
    providers = {}
    spreadsheet_id = os.environ.get('CONFIG_TABLE')
    if not spreadsheet_id:
        print("CONFIG_TABLE not set in .env")
        return providers

    try:
        ws = get_worksheet(spreadsheet_id, 'providers')
        if ws is None:
            return providers

        values = ws.get_all_values()
        for row in values[1:]:
            if not row or len(row) < 2:
                continue
            provider = str(row[0]).strip()
            code = str(row[1]).strip()
            if provider:
                providers[provider] = code
    except Exception as e:
        print(f"Error loading providers: {e}")

    return providers


def load_product_mapping():
    """Load product_mapping with extended schema.

    Returns a list of dicts. Always contains the legacy fields plus the new
    GLASS-specific fields (brand, sub_line, quality, order_section,
    order_model_name). Missing columns degrade gracefully to empty strings.
    """
    product_mapping = []
    spreadsheet_id = os.environ.get('CONFIG_TABLE')
    if not spreadsheet_id:
        print("CONFIG_TABLE not set in .env")
        return product_mapping

    try:
        ws = get_worksheet(spreadsheet_id, 'product_mapping')
        if ws is None:
            return product_mapping

        values = ws.get_all_values()
        if not values or len(values) < 2:
            return product_mapping

        headers = [str(h).strip().lower() for h in values[0]]

        def col(name: str) -> int:
            try:
                return headers.index(name)
            except ValueError:
                return -1

        idx = {
            'product_name': col('product_name'),
            'store': col('store'),
            'stock_type': col('stock_type'),
            'provider': col('provider'),
            'provider_product_name': col('provider_product_name'),
            'brand': col('brand'),
            'sub_line': col('sub_line'),
            'quality': col('quality'),
            'order_section': col('order_section'),
            'order_model_name': col('order_model_name'),
        }

        def cell(row, key):
            i = idx[key]
            if i < 0 or i >= len(row):
                return ''
            return str(row[i]).strip()

        for row in values[1:]:
            if not row:
                continue
            product_name = cell(row, 'product_name')
            if not product_name:
                continue

            product_mapping.append({
                'product_name': product_name,
                'store': cell(row, 'store'),
                'stock_type': cell(row, 'stock_type'),
                'provider': cell(row, 'provider'),
                'provider_product_name': cell(row, 'provider_product_name'),
                'brand': cell(row, 'brand'),
                'sub_line': cell(row, 'sub_line'),
                'quality': cell(row, 'quality'),
                'order_section': cell(row, 'order_section'),
                'order_model_name': cell(row, 'order_model_name'),
            })
    except Exception as e:
        print(f"Error loading product_mapping: {e}")

    return product_mapping


def parse_accessories_stock(spreadsheet_id):
    products = {}
    stock_type = config.ACCESORIOS_TAB

    try:
        ws = get_worksheet(spreadsheet_id, stock_type)
        if ws is None:
            print(f"Worksheet '{stock_type}' not found")
            return products

        values = ws.get_all_values()

        for row in values[1:]:
            product_a = row[0] if len(row) > 0 else None
            qty_a = row[1] if len(row) > 1 else None
            product_c = row[2] if len(row) > 2 else None

            if product_a and isinstance(product_a, str) and product_a.strip():
                if (product_a.strip() != 'CARGADORES' and
                        product_a.strip() != 'PARLANTES'):
                    qty = 0
                    if qty_a:
                        try:
                            qty = int(float(qty_a))
                        except (ValueError, TypeError):
                            qty = 0
                    products[product_a.strip()] = qty

            if product_c and isinstance(product_c, str) and product_c.strip():
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


def parse_stock(spreadsheet_id, stock_type):
    try:
        if stock_type == 'ACCESORIOS':
            return parse_accessories_stock(spreadsheet_id)
        elif stock_type == 'GLASS':
            return glass_utils.parse_glass_stock(spreadsheet_id)
        else:
            raise ValueError(f"Unknown stock type: {stock_type}")
    except Exception as e:
        print(f"Error parsing {stock_type} stock: {e}")
        return {}


def load_wanted_accesorios(store):
    wanted_spreadsheet_id = config.get_wanted_spreadsheet_id('ACCESORIOS')
    if not wanted_spreadsheet_id:
        return {}
    tab = config.get_wanted_tab('ACCESORIOS')
    ws = get_worksheet(wanted_spreadsheet_id, tab)
    if ws is None:
        return {}

    try:
        values = ws.get_all_values()
    except Exception as e:
        print(f"Error reading wanted file: {e}")
        return {}

    if not values:
        return {}

    headers = values[0]
    product_idx = None
    desired_idx = None
    for i, h in enumerate(headers):
        h_lower = str(h).strip().lower()
        if h_lower == 'product_name':
            product_idx = i
        elif h_lower in ('desired_qty', 'desired'):
            desired_idx = i

    if product_idx is None:
        return {}
    if desired_idx is None:
        desired_idx = 2

    desired_stock = {}
    for row in values[1:]:
        if not row or len(row) <= product_idx:
            continue
        product_name = str(row[product_idx]).strip()
        if not product_name:
            continue
        desired_qty = 0
        if desired_idx < len(row):
            try:
                desired_qty = int(float(row[desired_idx]))
            except (ValueError, TypeError):
                desired_qty = 0
        key = (store, 'ACCESORIOS', product_name)
        desired_stock[key] = desired_qty

    return desired_stock


def load_wanted_glass(store):
    wanted_spreadsheet_id = config.get_wanted_spreadsheet_id('GLASS')
    if not wanted_spreadsheet_id:
        return {}
    desired = glass_utils.parse_glass_wanted(wanted_spreadsheet_id)
    return {(store, 'GLASS', key): qty for key, qty in desired.items()}


def load_wanted_file(store, stock_type):
    if stock_type == 'ACCESORIOS':
        return load_wanted_accesorios(store)
    if stock_type == 'GLASS':
        return load_wanted_glass(store)
    return {}


def get_missing(products, desired_stock, store, stock_type):
    missing = {}
    for key, desired_qty in desired_stock.items():
        s, st, product_key = key
        if s != store or st != stock_type:
            continue
        actual_qty = products.get(product_key, 0)
        diff = desired_qty - actual_qty
        if diff > 0:
            missing[product_key] = {
                'actual': actual_qty,
                'desired': desired_qty,
                'missing': diff,
            }
    return missing


def update_wanted_file_accesorios(store, products, desired_stock):
    missing = get_missing(products, desired_stock, store, 'ACCESORIOS')

    wanted_spreadsheet_id = config.get_wanted_spreadsheet_id('ACCESORIOS')
    if not wanted_spreadsheet_id:
        print("WANTED spreadsheet ID not set")
        return missing

    tab = config.get_wanted_tab('ACCESORIOS')
    ws = get_worksheet(wanted_spreadsheet_id, tab)
    if ws is None:
        ws = get_or_create_worksheet(wanted_spreadsheet_id, tab)
        ws.update('A1', [['product_name', 'actual_qty', 'desired_qty', 'missing_qty']])

    existing_rows = ws.get_all_values()
    existing_products = {}
    for i, row in enumerate(existing_rows[1:], start=2):
        if row and len(row) > 0 and row[0]:
            existing_products[row[0].strip()] = i

    for product_name, data in missing.items():
        row_num = existing_products.get(product_name)
        if row_num:
            ws.update_cell(row_num, 2, data['actual'])
            ws.update_cell(row_num, 3, data['desired'])
            ws.update_cell(row_num, 4, data['missing'])
        else:
            next_row = len(existing_rows) + 1
            ws.update_cell(next_row, 1, product_name)
            ws.update_cell(next_row, 2, data['actual'])
            ws.update_cell(next_row, 3, data['desired'])
            ws.update_cell(next_row, 4, data['missing'])
            existing_rows.append([product_name])

    print(f"Updated wanted file for {store} ACCESORIOS")
    return missing


def update_wanted_file(store, stock_type, products, desired_stock):
    if stock_type == 'ACCESORIOS':
        return update_wanted_file_accesorios(store, products, desired_stock)
    if stock_type == 'GLASS':
        return get_missing(products, desired_stock, store, 'GLASS')
    return {}


def _resolve_section(item_brand, item_sub, item_quality, mapping_section):
    if mapping_section:
        return mapping_section
    return config.resolve_glass_section(item_brand, item_sub, item_quality)


def generate_orders(missing, product_mapping, store, stock_type):
    if stock_type == 'ACCESORIOS':
        return _generate_orders_accesorios(missing, product_mapping, store)
    if stock_type == 'GLASS':
        return _generate_orders_glass(missing, product_mapping, store)


def _generate_orders_accesorios(missing, product_mapping, store):
    provider_products = {}
    for mapping in product_mapping:
        if mapping['store'] != store or mapping['stock_type'] != 'ACCESORIOS':
            continue
        product_name = mapping['product_name']
        if product_name in missing:
            provider = mapping['provider']
            provider_product_name = mapping['provider_product_name']
            provider_products.setdefault(provider, []).append({
                'provider_product_name': provider_product_name,
                'quantity': missing[product_name]['missing'],
            })

    if not provider_products:
        print(f"No products to order for {store} ACCESORIOS")
        return

    update_order_accesorios(provider_products, store)


def _generate_orders_glass(missing, product_mapping, store):
    mapping_by_key = {}
    for m in product_mapping:
        if (m['stock_type'] or '').upper() != 'GLASS':
            continue
        if m.get('store') and m['store'] != store:
            continue
        brand = (m.get('brand') or '').strip().upper()
        sub = (m.get('sub_line') or '').strip().upper()
        quality = (m.get('quality') or '').strip().upper()
        stock_model = (m.get('provider_product_name') or m.get('product_name') or '').strip()
        if not stock_model or not brand or not quality:
            continue
        key = (brand, sub, stock_model, quality)
        mapping_by_key[key] = m

    items_to_write = []
    summary = {
        'processed': 0,
        'skipped_moto_xiaomi_osc': 0,
        'skipped_no_section': 0,
        'no_mapping': 0,
        'to_write': 0,
    }

    for key, data in missing.items():
        brand, sub_line, model, quality = key
        summary['processed'] += 1

        m = mapping_by_key.get(key)
        order_section = None
        order_model_name = model
        if m is not None:
            order_section = m.get('order_section') or None
            order_model_name = m.get('order_model_name') or model

        section = _resolve_section(brand, sub_line, quality, order_section)
        if section is None:
            if quality.upper() == 'OSC' and brand.upper() in ('MOTOROLA', 'XIAOMI'):
                summary['skipped_moto_xiaomi_osc'] += 1
                print(
                    f"WARNING: OSC + {brand} sin secci\u00f3n destino "
                    f"({model}) - skip"
                )
            else:
                summary['skipped_no_section'] += 1
                print(
                    f"WARNING: no section for {brand} {sub_line} {model} {quality}"
                )
            continue

        if m is None:
            summary['no_mapping'] += 1
            print(
                f"WARNING: producto sin mapping en product_mapping: "
                f"{brand} {sub_line} {model} {quality} -> usando default "
                f"section={section} order_model_name={order_model_name}"
            )

        items_to_write.append({
            'brand': brand,
            'sub_line': sub_line,
            'model': model,
            'quality': quality,
            'order_section': section,
            'order_model_name': order_model_name,
            'quantity': data['missing'],
        })
        summary['to_write'] += 1

    if not items_to_write:
        print(f"No products to order for {store} GLASS")
        return summary

    update_order_glass(items_to_write, store, summary)
    return summary


def update_order_accesorios(provider_products, store):
    spreadsheet_id = config.get_order_spreadsheet_id('ACCESORIOS')
    if not spreadsheet_id:
        print("ORDER_ACCESORIOS_TABLE not set")
        return

    tab = config.ORDER_ACCESORIOS_TAB
    ws = get_worksheet(spreadsheet_id, tab)
    if ws is None:
        print(f"Worksheet '{tab}' not found")
        return

    store_columns = config.get_store_columns_order_accesorios()
    try:
        store_col = store_columns.index(store) + 2
    except ValueError:
        print(f"Store '{store}' not found in ORDER_ACCESORIOS columns")
        return

    all_values = ws.get_all_values()
    product_rows = {}
    for i, row in enumerate(all_values[1:], start=2):
        if row and len(row) > 0 and row[0]:
            product_rows[row[0].strip()] = i

    for provider, items in provider_products.items():
        for item in items:
            provider_product_name = item['provider_product_name']
            quantity = item['quantity']
            row_num = product_rows.get(provider_product_name)
            if row_num:
                ws.update_cell(row_num, store_col, quantity)
                print(f"Updated {provider_product_name} -> {quantity} in column {store_col}")
            else:
                print(f"Product '{provider_product_name}' not found in ORDER_ACCESORIOS")

    print(f"Updated ORDER_ACCESORIOS for store: {store}")


def update_order_glass(items, store, summary=None):
    spreadsheet_id = config.get_order_spreadsheet_id('GLASS')
    if not spreadsheet_id:
        print("ORDER_GLASS_TABLE not set")
        return

    if store in config.ORDER_GLASS_LEGACY_TABS:
        print(f"Skip legacy tab '{store}'")
        return

    ws = get_worksheet(spreadsheet_id, store)
    if ws is None:
        print(f"Store '{store}' not found in ORDER_GLASS")
        return

    try:
        values = ws.get_all_values()
    except Exception as e:
        print(f"Error reading order tab '{store}': {e}")
        return

    index = glass_utils.index_order_sheet(values)

    batch_updates = []
    written = 0
    not_found = 0
    for item in items:
        section = item['order_section']
        order_model_name = item['order_model_name']
        quantity = item['quantity']
        normalized = glass_utils.normalize_model_name(order_model_name)
        cell_info = index.get((section, normalized))

        if cell_info is None:
            normalized_stock = glass_utils.normalize_model_name(item['model'])
            cell_info = index.get((section, normalized_stock))

        if cell_info is None:
            not_found += 1
            print(
                f"NOT FOUND in order sheet: section='{section}' "
                f"model='{order_model_name}' (stock {item['brand']} "
                f"{item['sub_line']} {item['model']} {item['quality']})"
            )
            continue

        row, col = cell_info
        cell_a1 = f"{_col_letter(col)}{row}"
        batch_updates.append({'range': cell_a1, 'values': [[quantity]]})
        written += 1
        print(
            f"  -> [{section}] {order_model_name} = {quantity} "
            f"(cell={cell_a1})"
        )

    if batch_updates:
        try:
            ws.batch_update(batch_updates, value_input_option='USER_ENTERED')
        except TypeError:
            ws.batch_update(batch_updates)

    if summary is not None:
        summary['written'] = written
        summary['not_found_in_order'] = not_found
    print(
        f"Updated ORDER_GLASS for store '{store}': written={written}, "
        f"not_found={not_found}"
    )


def _col_letter(col_1based: int) -> str:
    s = ''
    n = col_1based
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    parser = argparse.ArgumentParser(description="Generate stock orders from Google Sheets")
    parser.add_argument('--store', required=True, help="Store identifier (e.g., LA PLATA)")
    parser.add_argument('--stock_type', required=True, choices=['ACCESORIOS', 'GLASS'],
                        help="Stock type")
    args = parser.parse_args()

    load_providers()
    product_mapping = load_product_mapping()

    desired_stock = load_wanted_file(args.store, args.stock_type)

    stock_spreadsheet_id = config.get_stock_spreadsheet_id(args.stock_type)
    if not stock_spreadsheet_id:
        print(f"Stock spreadsheet ID not set for {args.stock_type}")
        return

    print(f"Reading stock from: {stock_spreadsheet_id}")

    try:
        products = parse_stock(stock_spreadsheet_id, args.stock_type)
    except Exception as e:
        print(f"Error reading stock: {e}")
        products = {}

    print(f"Found {len(products)} products in stock file")

    if not products:
        print("No products found in stock")
        return

    if desired_stock:
        missing = update_wanted_file(args.store, args.stock_type, products, desired_stock)
        print(f"Found {len(missing)} products with missing stock")
        if missing:
            result = generate_orders(missing, product_mapping, args.store, args.stock_type)
            if isinstance(result, dict):
                print("Summary:", result)
    else:
        print(f"No desired stock configured for {args.store} {args.stock_type}")


if __name__ == "__main__":
    main()
