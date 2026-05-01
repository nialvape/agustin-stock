import argparse
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from src.google_sheets import (
    get_worksheet,
    get_all_values,
    find_row,
    find_row_case_insensitive,
    get_or_create_worksheet,
)
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
        
        try:
            values = ws.get_all_values()
        except Exception as e:
            print(f"Error reading providers: {e}")
            return providers
        
        headers = values[0] if values else []
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
    product_mapping = []
    spreadsheet_id = os.environ.get('CONFIG_TABLE')
    if not spreadsheet_id:
        print("CONFIG_TABLE not set in .env")
        return product_mapping
    
    try:
        ws = get_worksheet(spreadsheet_id, 'product_mapping')
        if ws is None:
            return product_mapping
        
        try:
            values = ws.get_all_values()
        except Exception as e:
            print(f"Error reading product_mapping: {e}")
            return product_mapping
        
        if not values or len(values) < 2:
            return product_mapping
        
        headers = values[0]
        for row in values[1:]:
            if not row or len(row) < 5:
                continue
            product_name = str(row[0]).strip()
            if not product_name:
                continue
            
            product_mapping.append({
                'product_name': product_name,
                'store': str(row[1]).strip(),
                'stock_type': str(row[2]).strip(),
                'provider': str(row[3]).strip(),
                'provider_product_name': str(row[4]).strip(),
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
                    if qty_a and isinstance(qty_a, (int, float)):
                        qty = int(float(qty_a))
                    elif qty_a:
                        try:
                            qty = int(float(qty_a))
                        except (ValueError, TypeError):
                            qty = 0
                    products[product_a.strip()] = qty
            
            if product_c and isinstance(product_c, str) and product_c.strip():
                qty = 0
                if qty_a and isinstance(qty_a, (int, float)):
                    qty = int(float(qty_a))
                elif qty_a:
                    try:
                        qty = int(float(qty_a))
                    except (ValueError, TypeError):
                        qty = 0
                products[product_c.strip()] = qty

    except Exception as e:
        print(f"Error parsing accessories stock: {e}")
    
    return products


def parse_glass_stock(spreadsheet_id):
    products = {}
    
    for tab in config.GLASS_TABS:
        try:
            ws = get_worksheet(spreadsheet_id, tab)
            if ws is None:
                continue
            
            values = ws.get_all_values()
            if not values or len(values) < 2:
                continue
            
            headers = values[0]
            brand_cols = {}
            for i, header in enumerate(headers[1:], start=2):
                if header and isinstance(header, str) and header.strip():
                    brand_cols[header.strip()] = i
            
            for row in values[1:]:
                model = row[0]
                if not model or not isinstance(model, str) or not model.strip():
                    continue
                
                model = model.strip()
                
                for brand, col_idx in brand_cols.items():
                    if col_idx < len(row):
                        qty_val = row[col_idx]
                        qty = 0
                        if qty_val and isinstance(qty_val, (int, float)):
                            qty = int(float(qty_val))
                        elif qty_val:
                            try:
                                qty = int(float(qty_val))
                            except (ValueError, TypeError):
                                qty = 0
                        
                        product_name = f"{brand} {model}"
                        products[product_name] = qty

        except Exception as e:
            print(f"Error parsing glass stock: {e}")
    
    return products


def parse_stock(spreadsheet_id, stock_type):
    try:
        if stock_type == 'ACCESORIOS':
            return parse_accessories_stock(spreadsheet_id)
        elif stock_type == 'GLASS':
            return parse_glass_stock(spreadsheet_id)
        else:
            raise ValueError(f"Unknown stock type: {stock_type}")
    except Exception as e:
        print(f"Error parsing {stock_type} stock: {e}")
        return {}


def load_wanted_file(store, stock_type):
    wanted_spreadsheet_id = config.get_wanted_spreadsheet_id(stock_type)
    if not wanted_spreadsheet_id:
        return {}
    
    tab = config.get_wanted_tab(stock_type)
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
        
        key = (store, stock_type, product_name)
        desired_stock[key] = desired_qty
    
    return desired_stock


def get_missing(products, desired_stock, store, stock_type):
    missing = {}
    
    for key, desired_qty in desired_stock.items():
        s, st, product_name = key
        if s != store or st != stock_type:
            continue
        
        actual_qty = products.get(product_name, 0)
        diff = desired_qty - actual_qty
        
        if diff > 0:
            missing[product_name] = {
                'actual': actual_qty,
                'desired': desired_qty,
                'missing': diff
            }
    
    return missing


def update_wanted_file(store, stock_type, products, desired_stock):
    from dotenv import load_dotenv
    load_dotenv()
    
    missing = get_missing(products, desired_stock, store, stock_type)
    
    wanted_spreadsheet_id = config.get_wanted_spreadsheet_id(stock_type)
    if not wanted_spreadsheet_id:
        print("WANTED spreadsheet ID not set")
        return missing
    
    tab = config.get_wanted_tab(stock_type)
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
    
    print(f"Updated wanted file for {store} {stock_type}")
    return missing


def generate_orders(missing, product_mapping, store, stock_type):
    provider_products = {}
    
    for mapping in product_mapping:
        if mapping['store'] != store or mapping['stock_type'] != stock_type:
            continue
        
        product_name = mapping['product_name']
        
        if product_name in missing:
            provider = mapping['provider']
            provider_product_name = mapping['provider_product_name']
            
            if provider not in provider_products:
                provider_products[provider] = []
            
            provider_products[provider].append({
                'provider_product_name': provider_product_name,
                'quantity': missing[product_name]['missing']
            })
    
    if not provider_products:
        print(f"No products to order for {store} {stock_type}")
        return
    
    if stock_type == 'ACCESORIOS':
        update_order_accesorios(provider_products, store)
    elif stock_type == 'GLASS':
        update_order_glass(provider_products, store)


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


def update_order_glass(provider_products, store):
    spreadsheet_id = config.get_order_spreadsheet_id('GLASS')
    if not spreadsheet_id:
        print("ORDER_GLASS_TABLE not set")
        return
    
    sheet = None
    try:
        from src.google_sheets import get_sheet
        sheet = get_sheet(spreadsheet_id)
        ws = sheet.worksheet(store)
    except Exception as e:
        print(f"Store '{store}' not found in ORDER_GLASS: {e}")
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
                ws.update_cell(row_num, 2, quantity)
                print(f"Updated {provider_product_name} -> {quantity}")
            else:
                print(f"Product '{provider_product_name}' not found in ORDER_GLASS/{store}")
    
    print(f"Updated ORDER_GLASS for store: {store}")


def main():
    parser = argparse.ArgumentParser(description="Generate stock orders from Google Sheets")
    parser.add_argument('--store', required=True, help="Store identifier (e.g., LA_PLATA)")
    parser.add_argument('--stock_type', required=True, choices=['ACCESORIOS', 'GLASS'],
                        help="Stock type")
    args = parser.parse_args()
    
    providers = load_providers()
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
            generate_orders(missing, product_mapping, args.store, args.stock_type)
    else:
        print(f"No desired stock configured for {args.store} {args.stock_type}")


if __name__ == "__main__":
    main()