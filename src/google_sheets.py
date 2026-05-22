import os
import time
import gspread
from google.oauth2 import service_account
from gspread import Worksheet

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

_RETRY_DELAYS = [5, 10, 20]  # segundos de espera entre reintentos (429 / 503)

_cached_client = None
_cached_sheets: dict = {}  # spreadsheet_id -> Spreadsheet


def get_client():
    global _cached_client
    if _cached_client is not None:
        return _cached_client

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
    
    _cached_client = gspread.Client(credentials)
    return _cached_client


def _is_rate_limit_error(exc: Exception) -> bool:
    code = getattr(exc, 'response', None)
    if code is not None:
        status = getattr(code, 'status_code', None)
        if status in (429, 503):
            return True
    if hasattr(exc, 'args') and exc.args:
        msg = str(exc.args[0]) if exc.args else ''
        if '429' in msg or '503' in msg:
            return True
    return False


def _retry(fn, label: str = ''):
    """Ejecuta *fn()* con reintentos ante 429 / 503."""
    last_exc = None
    for attempt in range(1 + len(_RETRY_DELAYS)):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if _is_rate_limit_error(e) and attempt < len(_RETRY_DELAYS):
                delay = _RETRY_DELAYS[attempt]
                tag = f" ({label})" if label else ''
                print(f"  [rate-limit] esperando {delay}s antes de reintentar{tag}")
                time.sleep(delay)
                continue
            raise
    raise last_exc  # nunca debería llegar acá


# Alias público para que otros módulos puedan usar retry en sus llamadas gspread.
retry_api = _retry


def get_sheet(spreadsheet_id: str):
    if spreadsheet_id in _cached_sheets:
        return _cached_sheets[spreadsheet_id]

    try:
        client = get_client()
        sheet = _retry(lambda: client.open_by_key(spreadsheet_id), spreadsheet_id[:12])
        _cached_sheets[spreadsheet_id] = sheet
        return sheet
    except Exception as e:
        print(f"Error opening spreadsheet {spreadsheet_id}: {e}")
        return None


def get_worksheet(spreadsheet_id: str, sheet_name: str):
    try:
        sheet = get_sheet(spreadsheet_id)
        if sheet is None:
            return None
        try:
            return _retry(lambda: sheet.worksheet(sheet_name), sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            pass
        all_ws = _retry(lambda: sheet.worksheets(), sheet_name)
        for ws in all_ws:
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