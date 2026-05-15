import argparse
import os
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

from src.google_sheets import get_worksheet
from src import glass as glass_utils
from src import accesorios_order_match as acc_match
import src.sheet_config as config


def load_providers():
    try:
        return config.load_providers_from_config()
    except Exception as e:
        print(f"Error loading providers: {e}")
        return {}


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


def load_wanted_accesorios(store, wanted_spreadsheet_id=None):
    if wanted_spreadsheet_id is None:
        wanted_spreadsheet_id = config.get_wanted_spreadsheet_id('ACCESORIOS')
    wanted_spreadsheet_id = (wanted_spreadsheet_id or '').strip()
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

    # New wanted layout for accessories:
    #   Columns A and E have product names, grouped vertically by category titles.
    #   Columns D and H contain the missing stock to order.
    _CATEGORY_TITLES_A = {'CARGADORES', 'ADAPTADORES', 'CABLES', 'HOLDER'}
    _CATEGORY_TITLES_E = {'PARLANTES', 'ACCESORIOS', 'MEMO-PEN', 'AURICULARES'}
    _ALL_CATEGORY_TITLES = _CATEGORY_TITLES_A | _CATEGORY_TITLES_E

    desired_stock = {}
    for row in values:
        # Left side: column A (0) = product, column D (3) = missing qty
        cell_a = str(row[0]).strip() if len(row) > 0 else ''
        if cell_a and cell_a.upper() not in _ALL_CATEGORY_TITLES:
            try:
                qty = int(float(str(row[3]).strip())) if len(row) > 3 and row[3] else 0
            except (ValueError, TypeError):
                qty = 0
            if qty > 0:
                key = (store, 'ACCESORIOS', cell_a)
                desired_stock[key] = qty

        # Right side: column E (4) = product, column H (7) = missing qty
        cell_e = str(row[4]).strip() if len(row) > 4 else ''
        if cell_e and cell_e.upper() not in _ALL_CATEGORY_TITLES:
            try:
                qty = int(float(str(row[7]).strip())) if len(row) > 7 and row[7] else 0
            except (ValueError, TypeError):
                qty = 0
            if qty > 0:
                key = (store, 'ACCESORIOS', cell_e)
                desired_stock[key] = qty

    return desired_stock


def load_wanted_glass(store, wanted_spreadsheet_id=None, glass_layout_out=None):
    if wanted_spreadsheet_id is None:
        wanted_spreadsheet_id = config.get_wanted_spreadsheet_id('GLASS')
    wanted_spreadsheet_id = (wanted_spreadsheet_id or '').strip()
    if not wanted_spreadsheet_id:
        return {}
    desired, uses_faltante = glass_utils.parse_glass_wanted(wanted_spreadsheet_id)
    if glass_layout_out is not None:
        glass_layout_out.clear()
        glass_layout_out.append(uses_faltante)
    return {(store, 'GLASS', key): qty for key, qty in desired.items()}


def load_wanted_file(store, stock_type, wanted_spreadsheet_id=None, glass_layout_out=None):
    if stock_type == 'ACCESORIOS':
        return load_wanted_accesorios(store, wanted_spreadsheet_id=wanted_spreadsheet_id)
    if stock_type == 'GLASS':
        return load_wanted_glass(
            store,
            wanted_spreadsheet_id=wanted_spreadsheet_id,
            glass_layout_out=glass_layout_out,
        )
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
    # New wanted layout: columns A/E have product names grouped by category
    # titles, columns D/H have the missing quantities directly. No need to
    # recalculate or write back to the wanted sheet (the visual layout with
    # category headers is maintained manually).
    missing = {}
    for key, qty in desired_stock.items():
        s, st, product_key = key
        if s != store or st != 'ACCESORIOS':
            continue
        if qty > 0:
            actual = products.get(product_key, 0)
            missing[product_key] = {
                'actual': actual,
                'desired': qty,
                'missing': qty,
            }

    print(f"Loaded {len(missing)} missing items for {store} ACCESORIOS from wanted sheet")
    return missing


def update_wanted_file_glass_faltante(store, products, desired_stock):
    """Cantidades ya en columna faltante del wanted (no restar otra planilla)."""
    missing = {}
    for key, qty in desired_stock.items():
        s, st, product_key = key
        if s != store or st != 'GLASS':
            continue
        if qty > 0:
            actual = products.get(product_key, 0)
            missing[product_key] = {
                'actual': actual,
                'desired': qty,
                'missing': qty,
            }
    print(
        f"GLASS: {len(missing)} ítems con faltante>0 (columnas faltante del wanted, "
        "sin restar stock externo).",
    )
    return missing


def update_wanted_file(store, stock_type, products, desired_stock, glass_faltante_layout=False):
    if stock_type == 'ACCESORIOS':
        return update_wanted_file_accesorios(store, products, desired_stock)
    if stock_type == 'GLASS':
        if glass_faltante_layout:
            return update_wanted_file_glass_faltante(store, products, desired_stock)
        return get_missing(products, desired_stock, store, 'GLASS')
    return {}


def _resolve_section(item_brand, item_sub, item_quality, mapping_section):
    if mapping_section:
        return mapping_section
    return config.resolve_glass_section(item_brand, item_sub, item_quality)


def _default_provider_for_orders(providers: dict) -> str:
    for name in sorted(providers.keys()):
        if (providers[name].get('order_spreadsheet_id') or '').strip():
            return name
    return sorted(providers.keys())[0] if providers else 'ProviderA'


def _union_order_accesorios_product_names(providers: dict) -> list:
    """Column A product names from every provider order sheet (deduped, stable order)."""
    seen = set()
    out = []
    for pdata in providers.values():
        oid = (pdata.get('order_spreadsheet_id') or '').strip()
        if not oid:
            continue
        for n in acc_match.load_order_accesorios_product_names(
            oid, config.ORDER_ACCESORIOS_TAB,
        ):
            if n not in seen:
                seen.add(n)
                out.append(n)
    return out


def _provider_order_spreadsheet_ids(providers: dict) -> dict:
    return {
        k: v['order_spreadsheet_id'].strip()
        for k, v in providers.items()
        if (v.get('order_spreadsheet_id') or '').strip()
    }


def _normalize_store_label(name: str) -> str:
    """Comparar locales ignorando mayúsculas y espacios repetidos."""
    return " ".join((name or "").split()).upper()


def _find_store_row(stores: list, store_name: str):
    target = _normalize_store_label(store_name)
    for row in stores:
        if _normalize_store_label(row.get("store") or "") == target:
            return row
    return None


def _wanted_id_for_store(stock_type: str, store_row: dict | None) -> str | None:
    if not store_row:
        return None
    if stock_type == 'GLASS':
        return (store_row.get('wanted_glass_id') or '').strip() or None
    return (store_row.get('wanted_accesorios_id') or '').strip() or None


def generate_orders(missing, product_mapping, store, stock_type, providers):
    if stock_type == 'ACCESORIOS':
        return _generate_orders_accesorios(missing, product_mapping, store, providers)
    if stock_type == 'GLASS':
        return _generate_orders_glass(missing, product_mapping, store, providers)


def _generate_orders_accesorios(missing, product_mapping, store, providers):
    if not providers:
        print("No hay proveedores en la pestaña providers de CONFIG.")
        return

    order_names = _union_order_accesorios_product_names(providers)
    provider_order_ids = _provider_order_spreadsheet_ids(providers)
    if not provider_order_ids:
        print(
            "No hay links de order en la pestaña providers (columna order). "
            "Completá la columna o definí ORDER_ACCESORIOS_TABLE en .env como respaldo.",
        )
        legacy = (config.get_order_spreadsheet_id('ACCESORIOS') or '').strip()
        if legacy:
            for name in providers:
                provider_order_ids[name] = legacy
        else:
            return

    default_provider = _default_provider_for_orders(providers)

    default_order_tab = config.ORDER_ACCESORIOS_TAB

    mapping_specific: dict = {}
    mapping_generic: dict = {}
    for m in product_mapping:
        st = (m.get('stock_type') or '').upper()
        if st == 'GLASS':
            continue
        pn = (m.get('product_name') or '').strip()
        if not pn:
            continue
        row_store = (m.get('store') or '').strip()
        if row_store:
            if row_store == store:
                mapping_specific[pn] = m
        else:
            mapping_generic[pn] = m

    def lookup_mapping(product_name: str):
        return mapping_specific.get(product_name) or mapping_generic.get(product_name)

    provider_products = {}
    mapped_names = set()
    for product_name, data in missing.items():
        m = lookup_mapping(product_name)
        provider = None
        provider_product_name = None
        order_tab = default_order_tab
        if m is not None:
            provider = (m.get('provider') or '').strip()
            provider_product_name = (m.get('provider_product_name') or '').strip()
            order_tab = (m.get('stock_type') or '').strip() or default_order_tab
            if not provider or not provider_product_name:
                print(f"WARNING: mapping for {product_name!r} lacks provider or provider_product_name")
        if (not provider or not provider_product_name) and order_names:
            auto_order, why = acc_match.match_wanted_to_order(product_name, order_names)
            if auto_order:
                provider_product_name = auto_order
                provider = default_provider
                order_tab = default_order_tab
                print(f"  match {product_name!r} -> {auto_order!r} ({why})")
        if provider and provider_product_name:
            provider_products.setdefault(provider, []).append({
                'provider_product_name': provider_product_name,
                'quantity': data['missing'],
                'order_tab': order_tab,
            })
            mapped_names.add(product_name)

    unmapped = set(missing.keys()) - mapped_names
    if unmapped:
        print(f"WARNING: {len(unmapped)} missing products sin mapeo ni match automático:")
        for name in sorted(unmapped)[:25]:
            print(f"  - {name}")
        if len(unmapped) > 25:
            print(f"  ... and {len(unmapped) - 25} more")

    if not provider_products:
        print(f"No products to order for {store} ACCESORIOS")
        return

    update_order_accesorios(provider_products, store, provider_order_ids)


def _generate_orders_glass(missing, product_mapping, store, providers):
    """Build order items from missing GLASS stock and write to the order sheet.

    product_mapping rows without a ``store`` apply to every store; rows with
    an explicit ``store`` override the generic entry for that store only.
    """
    if not providers:
        print("No hay proveedores en la pestaña providers de CONFIG.")
        return None

    # Index mapping by (brand, sub_line, model, quality)
    mapping_specific: dict = {}
    mapping_generic: dict = {}
    for m in product_mapping:
        if (m.get('stock_type') or '').upper() != 'GLASS':
            continue
        brand = (m.get('brand') or '').strip().upper()
        sub = (m.get('sub_line') or '').strip().upper()
        quality = (m.get('quality') or '').strip().upper()
        stock_model = (m.get('product_name') or '').strip()
        if not stock_model or not brand or not quality:
            continue
        key = (brand, sub, stock_model, quality)
        row_store = (m.get('store') or '').strip()
        if row_store:
            if row_store == store:
                mapping_specific[key] = m
        else:
            mapping_generic[key] = m

    def lookup_mapping(key):
        return mapping_specific.get(key) or mapping_generic.get(key)

    default_provider = _default_provider_for_orders(providers)
    provider_order_ids = _provider_order_spreadsheet_ids(providers)
    if not provider_order_ids:
        legacy = (config.get_order_spreadsheet_id('GLASS') or '').strip()
        if legacy:
            provider_order_ids = {name: legacy for name in providers}

    # Resolve each faltante item into an order line
    items_to_write = []
    counts = {'processed': 0, 'no_section': 0, 'no_mapping': 0}

    for key, data in missing.items():
        brand, sub_line, model, quality = key
        counts['processed'] += 1

        m = lookup_mapping(key)
        order_section = (m.get('order_section') or None) if m else None
        order_model_name = ((m.get('provider_product_name') or '').strip() or model) if m else model

        section = _resolve_section(brand, sub_line, quality, order_section)
        if section is None:
            counts['no_section'] += 1
            print(f"  skip: sin sección destino → {brand} {sub_line} {model} {quality}")
            continue

        if m is None:
            counts['no_mapping'] += 1
            print(f"  sin mapping → {brand} {sub_line} {model} {quality}  (sección={section})")

        prov = ((m.get('provider') or '').strip() if m else '') or default_provider

        items_to_write.append({
            'brand': brand,
            'sub_line': sub_line,
            'model': model,
            'quality': quality,
            'order_section': section,
            'order_model_name': order_model_name,
            'quantity': data['missing'],
            'provider': prov,
        })

    print(
        f"GLASS {store}: {counts['processed']} ítems procesados, "
        f"{len(items_to_write)} a escribir, "
        f"{counts['no_section']} sin sección, "
        f"{counts['no_mapping']} sin mapping.",
    )

    if not items_to_write:
        print(f"No hay productos a pedir para {store} GLASS.")
        return counts

    if not provider_order_ids:
        print(
            "No hay planillas de pedido GLASS: completá la columna order en providers "
            "o ORDER_GLASS_TABLE en .env.",
        )
        return counts

    by_provider: dict = defaultdict(list)
    for it in items_to_write:
        prov = it.pop('provider')
        by_provider[prov].append(it)

    for prov, subitems in sorted(by_provider.items()):
        oid = provider_order_ids.get(prov)
        if not oid:
            print(f"  proveedor {prov!r} sin link de pedido — se omiten {len(subitems)} ítems.")
            continue
        print(f"  ORDER_GLASS proveedor={prov!r} spreadsheet={oid[:12]}…")
        update_order_glass(subitems, store, spreadsheet_id=oid)

    return counts


def _resolve_acce_store_column_1based(header_row, store: str):
    """Column index 1-based for ``store`` in ORDER ACCE header (row 1)."""
    target = (store or '').strip().upper()
    for i, cell in enumerate(header_row):
        if str(cell).strip().upper() == target:
            return i + 1
    return None


def update_order_accesorios(provider_products, store, provider_order_ids: dict):
    for provider, items in provider_products.items():
        spreadsheet_id = provider_order_ids.get(provider)
        if not spreadsheet_id:
            print(
                f"WARNING: proveedor {provider!r} sin link en columna order; "
                f"no se escribe pedido ({len(items)} líneas)",
            )
            continue

        # Group items by the order tab (stock_type from product_mapping)
        items_by_tab: dict = {}
        for item in items:
            tab = item.get('order_tab', config.ORDER_ACCESORIOS_TAB)
            items_by_tab.setdefault(tab, []).append(item)

        for tab, tab_items in items_by_tab.items():
            _write_order_tab(spreadsheet_id, tab, tab_items, provider, store)


def _write_order_tab(spreadsheet_id, tab, items, provider, store):
    """Write order quantities into a specific tab of the provider's order spreadsheet."""
    ws = get_worksheet(spreadsheet_id, tab)
    if ws is None:
        print(f"Worksheet '{tab}' not found en order de {provider!r}")
        return

    all_values = ws.get_all_values()
    if not all_values:
        print(f"Worksheet '{tab}' is empty ({provider!r})")
        return

    header = all_values[0]
    store_col = _resolve_acce_store_column_1based(header, store)
    if store_col is None:
        print(
            f"Store '{store}' not found in order tab '{tab}' header ({provider!r}). "
            f"Headers seen: {[str(h).strip() for h in header[:15] if str(h).strip()]}"
        )
        return

    product_rows = {}
    for i, row in enumerate(all_values[1:], start=2):
        if row and len(row) > 0 and row[0]:
            product_rows[row[0].strip()] = i

    qty_by_product: dict = {}
    sources_by_product: dict = {}
    for item in items:
        provider_product_name = item['provider_product_name']
        quantity = int(item['quantity'])
        qty_by_product[provider_product_name] = (
            qty_by_product.get(provider_product_name, 0) + quantity
        )
        sources_by_product.setdefault(provider_product_name, []).append(
            f'{provider}:{quantity}'
        )

    batch_updates = []
    log_lines = []
    not_found = []
    for provider_product_name, total in qty_by_product.items():
        row_num = product_rows.get(provider_product_name)
        if not row_num:
            not_found.append(provider_product_name)
            continue
        cell_a1 = f'{_col_letter(store_col)}{row_num}'
        batch_updates.append({'range': cell_a1, 'values': [[total]]})
        srcs = sources_by_product.get(provider_product_name, [])
        if len(srcs) > 1:
            log_lines.append(
                f"[{provider}] Updated {provider_product_name} -> {total} in {cell_a1} "
                f"(sum of {len(srcs)} lines: {', '.join(srcs)})"
            )
        else:
            log_lines.append(
                f"[{provider}] Updated {provider_product_name} -> {total} in {cell_a1}"
            )

    if not_found:
        for name in not_found:
            print(f"[{provider}] Product '{name}' not found in order tab '{tab}'")

    if batch_updates:
        chunk_size = 100
        for i in range(0, len(batch_updates), chunk_size):
            chunk = batch_updates[i:i + chunk_size]
            try:
                ws.batch_update(chunk, value_input_option='USER_ENTERED')
            except TypeError:
                ws.batch_update(chunk)

    for line in log_lines:
        print(line)

    print(
        f"Updated order tab='{tab}' provider={provider!r} store={store!r} "
        f"({len(batch_updates)} cells)"
    )


def update_order_glass(items, store, spreadsheet_id=None):
    spreadsheet_id = (spreadsheet_id or '').strip() or config.get_order_spreadsheet_id('GLASS')
    if not spreadsheet_id:
        print("ORDER_GLASS: sin spreadsheet (columna order en providers ni ORDER_GLASS_TABLE)")
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

    cell_aggregations: dict = {}
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
        agg = cell_aggregations.setdefault(
            (row, col),
            {'section': section, 'order_model_name': order_model_name,
             'quantity': 0, 'sources': []},
        )
        agg['quantity'] += quantity
        agg['sources'].append(
            f"{item['brand']} {item['sub_line']} {item['model']} {item['quality']}={quantity}"
        )

    batch_updates = []
    written = 0
    aggregated_cells = 0
    for (row, col), agg in cell_aggregations.items():
        cell_a1 = f"{_col_letter(col)}{row}"
        batch_updates.append({'range': cell_a1, 'values': [[agg['quantity']]]})
        written += 1
        if len(agg['sources']) > 1:
            aggregated_cells += 1
            print(
                f"  -> [{agg['section']}] {agg['order_model_name']} = "
                f"{agg['quantity']} (cell={cell_a1}, agregado de "
                f"{len(agg['sources'])} items: {', '.join(agg['sources'])})"
            )
        else:
            print(
                f"  -> [{agg['section']}] {agg['order_model_name']} = "
                f"{agg['quantity']} (cell={cell_a1})"
            )

    if batch_updates:
        try:
            ws.batch_update(batch_updates, value_input_option='USER_ENTERED')
        except TypeError:
            ws.batch_update(batch_updates)

    print(
        f"  ORDER_GLASS '{store}': {written} celdas escritas, "
        f"{aggregated_cells} agregadas, {not_found} no encontradas.",
    )


def _col_letter(col_1based: int) -> str:
    s = ''
    n = col_1based
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _build_store_jobs(stock_type: str, store_arg: str | None):
    """List of (store_name, wanted_spreadsheet_id).

    Si existe la pestaña ``stores`` con filas, los links B/C tienen prioridad
    absoluta: no se sustituye por WANTED_* del .env salvo que la pestaña esté
    vacía (modo legacy sin config de locales).
    """
    stores = config.load_stores_rows()
    env_wanted = (config.get_wanted_spreadsheet_id(stock_type) or "").strip() or None
    stores_configured = bool(stores)

    if store_arg:
        name = store_arg.strip()
        row = _find_store_row(stores, name)
        if row:
            wid = _wanted_id_for_store(stock_type, row)
            if not wid:
                col = "B (GLASS)" if stock_type == "GLASS" else "C (ACCESORIOS)"
                print(
                    f"La fila de {name!r} en la pestaña stores no tiene link en {col}. "
                    "Completá la celda en la planilla CONFIG; no se usa WANTED_* del .env "
                    "cuando el local está en stores.",
                )
                return []
            canonical = (row.get("store") or name).strip()
            return [(canonical, wid)]
        if stores_configured:
            known = ", ".join(repr((r.get("store") or "").strip()) for r in stores[:20])
            more = "…" if len(stores) > 20 else ""
            print(
                f"No hay fila en la pestaña stores para el local {name!r}. "
                f"Revisá el nombre (debe coincidir con la columna NAME). "
                f"Locales en config: {known}{more}",
            )
            return []
        if env_wanted:
            print(
                "Advertencia: no hay pestaña stores (o está vacía); "
                f"se usa WANTED_{stock_type} del .env para {name!r}.",
            )
            return [(name, env_wanted)]
        print(
            f"No se encontró {name!r} en stores y no hay WANTED_* en .env.",
        )
        return []

    if not stores:
        print(
            "Sin --store: hace falta la pestaña stores en CONFIG con columnas "
            "A=local, B=GLASS, C=ACCESORIOS (links a wanted).",
        )
        return []

    jobs = []
    for row in stores:
        s = (row.get("store") or "").strip()
        if not s:
            continue
        wid = _wanted_id_for_store(stock_type, row)
        if not wid:
            print(
                f"Omitido {s!r}: falta link de wanted para {stock_type} "
                f"({'columna B' if stock_type == 'GLASS' else 'columna C'}).",
            )
            continue
        jobs.append((s, wid))
    return jobs


def run_pipeline(store: str, stock_type: str, wanted_spreadsheet_id: str | None,
                 product_mapping, providers):
    glass_layout: list = []
    desired_stock = load_wanted_file(
        store, stock_type, wanted_spreadsheet_id=wanted_spreadsheet_id,
        glass_layout_out=glass_layout,
    )
    glass_faltante_layout = bool(glass_layout and glass_layout[0])

    if not desired_stock:
        print(f"No hay cantidades a pedir en WANTED para {store!r} ({stock_type}).")
        return

    if stock_type == 'GLASS' and glass_faltante_layout:
        products = {}
        print(
            "WANTED GLASS: layout con columnas «faltante»; "
            "no se usa GLASS_TABLE del .env (el pedido sale solo de esas celdas).",
        )
    else:
        stock_spreadsheet_id = (config.get_stock_spreadsheet_id(stock_type) or '').strip() or None
        products = {}
        if stock_spreadsheet_id:
            print(f"Leyendo stock de referencia (env): {stock_spreadsheet_id}")
            try:
                products = parse_stock(stock_spreadsheet_id, stock_type)
            except Exception as e:
                print(f"Error reading stock: {e}")
                products = {}
        else:
            print(
                "GLASS_TABLE / ACCESORIOS_TABLE no definidos: solo se usa el WANTED "
                "(GLASS clásico: faltante = deseado − stock leído; sin stock, deseado).",
            )

    print(f"Productos en stock (referencia): {len(products)}")

    if not products and not desired_stock:
        print("Sin datos de stock ni de wanted; no hay nada que procesar.")
        return

    missing = update_wanted_file(
        store, stock_type, products, desired_stock,
        glass_faltante_layout=glass_faltante_layout,
    )
    print(f"Productos con faltante: {len(missing)}")
    if missing:
        result = generate_orders(missing, product_mapping, store, stock_type, providers)
        if isinstance(result, dict):
            print("Summary:", result)


def main():
    parser = argparse.ArgumentParser(description="Generate stock orders from Google Sheets")
    parser.add_argument(
        '--store',
        required=False,
        default=None,
        help="Local (ej. LA PLATA). Si se omite, se procesan todos los de la pestaña stores.",
    )
    parser.add_argument('--stock_type', required=True, choices=['ACCESORIOS', 'GLASS'],
                        help="Stock type")
    args = parser.parse_args()

    providers = load_providers()
    product_mapping = load_product_mapping()

    jobs = _build_store_jobs(args.stock_type, args.store)
    if not jobs:
        return

    for store, wid in jobs:
        print(f"\n=== {store} ({args.stock_type}) wanted={wid[:12]}… ===")
        run_pipeline(store, args.stock_type, wid, product_mapping, providers)


if __name__ == "__main__":
    main()
