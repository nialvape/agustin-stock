import os
import gspread
from google.oauth2 import service_account
from gspread import Worksheet

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def get_client():
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_path:
        creds_path = os.environ.get('GOOGLE_CREDS_PATH')
    
    if not creds_path:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_CREDS_PATH not set")
    
    if creds_path.startswith('{'):
        import json
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(creds_path), scopes=SCOPES
        )
    else:
        credentials = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES
        )
    
    return gspread.Client(credentials)


def get_sheet(spreadsheet_id: str):
    try:
        client = get_client()
        return client.open_by_key(spreadsheet_id)
    except Exception as e:
        print(f"Error opening spreadsheet {spreadsheet_id}: {e}")
        return None


def get_worksheet(spreadsheet_id: str, sheet_name: str):
    try:
        sheet = get_sheet(spreadsheet_id)
        if sheet is None:
            return None
        try:
            return sheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            pass
        for ws in sheet.worksheets():
            if sheet_name.strip().lower() in ws.title.strip().lower():
                return ws
        return None
    except Exception as e:
        print(f"Error getting worksheet {sheet_name}: {e}")
        return None


def get_all_values(spreadsheet_id: str, sheet_name: str):
    ws = get_worksheet(spreadsheet_id, sheet_name)
    if ws is None:
        return []
    return ws.get_all_values()


def get_all_records(spreadsheet_id: str, sheet_name: str):
    ws = get_worksheet(spreadsheet_id, sheet_name)
    if ws is None:
        return []
    return ws.get_all_records()


def read_as_dict(spreadsheet_id: str, sheet_name: str):
    return get_all_records(spreadsheet_id, sheet_name)


def update_cell(worksheet: Worksheet, row: int, col: int, value):
    worksheet.update_cell(row, col, value)


def update_range(worksheet: Worksheet, start_row: int, start_col: int, values: list):
    end_col = start_col + len(values[0]) - 1 if values else start_col
    end_row = start_row + len(values) - 1 if values else start_row
    if end_row < start_row:
        end_row = start_row
    if end_col < start_col:
        end_col = start_col
    
    cell_range = f"{chr(64 + start_col)}{start_row}:{chr(64 + end_col)}{end_row}"
    worksheet.update(cell_range, values)


def find_row(worksheet: Worksheet, value, col: int = 1):
    all_values = worksheet.get_all_values()
    for i, row in enumerate(all_values, start=1):
        if col <= len(row) and str(row[col - 1]).strip() == str(value).strip():
            return i
    return None


def find_row_case_insensitive(worksheet: Worksheet, value, col: int = 1):
    all_values = worksheet.get_all_values()
    value_lower = str(value).strip().lower()
    for i, row in enumerate(all_values, start=1):
        if col <= len(row) and str(row[col - 1]).strip().lower() == value_lower:
            return i
    return None


def get_or_create_worksheet(spreadsheet_id: str, sheet_name: str):
    sheet = get_sheet(spreadsheet_id)
    try:
        return sheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return sheet.add_worksheet(title=sheet_name, rows=1000, cols=26)