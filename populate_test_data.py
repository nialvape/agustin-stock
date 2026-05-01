import os
import sys
from dotenv import load_dotenv

load_dotenv()

from src.google_sheets import (
    get_worksheet,
    get_sheet,
    get_or_create_worksheet,
)
import src.sheet_config as config


def populate_test_data():
    print("=== Populating Test Data ===\n")
    
    populate_product_mapping()
    
    populate_wanted_tables()
    
    print("\n=== Test Data Population Complete ===")


def populate_product_mapping():
    print("--- Populating product_mapping ---")
    
    spreadsheet_id = os.environ.get('CONFIG_TABLE')
    if not spreadsheet_id:
        print("CONFIG_TABLE not set")
        return
    
    try:
        ws = get_worksheet(spreadsheet_id, 'product_mapping')
        if ws is None:
            ws = get_or_create_worksheet(spreadsheet_id, 'product_mapping')
            ws.update('A1', [['product_name', 'store', 'stock_type', 'provider', 'provider_product_name']])
        
        existing = ws.get_all_values()
        existing_products = set()
        for row in existing[1:]:
            if row and len(row) > 0 and row[0]:
                existing_products.add(row[0].strip())
        
        new_mappings = []
        
        order_acc_sp = config.get_order_spreadsheet_id('ACCESORIOS')
        if order_acc_sp:
            try:
                ws_order = get_worksheet(order_acc_sp, config.ORDER_ACCESORIOS_TAB)
                if ws_order:
                    values = ws_order.get_all_values()
                    for row in values[1:]:
                        if row and len(row) > 0 and row[0]:
                            product_name = row[0].strip()
                            if product_name and product_name not in existing_products:
                                new_mappings.append({
                                    'product_name': product_name,
                                    'store': 'LA_PLATA',
                                    'stock_type': 'ACCESORIOS',
                                    'provider': 'ProviderA',
                                    'provider_product_name': product_name,
                                })
                                existing_products.add(product_name)
            except Exception as e:
                print(f"Skipping ORDER_ACCESORIOS: {e}")
        
        for mapping in new_mappings:
            ws.append_row([
                mapping['product_name'],
                mapping['store'],
                mapping['stock_type'],
                mapping['provider'],
                mapping['provider_product_name'],
            ])
        
        print(f"Added {len(new_mappings)} product mappings")
    
    except Exception as e:
        print(f"Error populating product_mapping: {e}")


def populate_wanted_tables():
    print("--- Populating WANTED tables ---")
    
    for stock_type in ['ACCESORIOS', 'GLASS']:
        wanted_sp = config.get_wanted_spreadsheet_id(stock_type)
        if not wanted_sp:
            print(f"WANTED_{stock_type}_TABLE not set")
            continue
        
        tab = config.get_wanted_tab(stock_type)
        
        try:
            ws = get_worksheet(wanted_sp, tab)
            
            if ws is None:
                print(f"Worksheet '{tab}' not found in WANTED_{stock_type}")
                continue
            
            headers = ws.get_all_values()
            if not headers or len(headers) < 2:
                ws.update('A1', [['product_name', 'actual_qty', 'desired_qty', 'missing_qty']])
                headers = [['product_name', 'actual_qty', 'desired_qty', 'missing_qty']]
            
            stock_sp = config.get_stock_spreadsheet_id(stock_type)
            if not stock_sp:
                print(f"{stock_type}_TABLE not set")
                continue
            
            products = {}
            
            try:
                if stock_type == 'ACCESORIOS':
                    products = parse_accessories_stock(stock_sp)
                elif stock_type == 'GLASS':
                    products = parse_glass_stock(stock_sp)
            except Exception as e:
                print(f"Skipping {stock_type} stock read: {e}")
            
            if not products:
                print(f"No products found or sheet inaccessible for {stock_type}")
                continue
            
            print(f"Found {len(products)} products in {stock_type} stock")
            
            store = 'LA_PLATA'
            
            existing = {}
            for i, row in enumerate(headers[1:], start=2):
                if row and len(row) > 0 and row[0]:
                    existing[row[0].strip()] = i
            
            for product_name, actual_qty in products.items():
                if product_name in existing:
                    continue
                
                desired_qty = actual_qty + 5
                missing_qty = max(0, desired_qty - actual_qty)
                
                ws.append_row([product_name, actual_qty, desired_qty, missing_qty])
                existing[product_name] = len(headers) + 1
                headers.append([product_name])
            
            print(f"Updated WANTED_{stock_type} with {len(products)} products")
        
        except Exception as e:
            print(f"Error populating WANTED_{stock_type}: {e}")


def parse_accessories_stock(spreadsheet_id):
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


if __name__ == "__main__":
    populate_test_data()