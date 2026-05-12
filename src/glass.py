"""Shared GLASS parsing / routing utilities.

The GLASS stock sheet is a single tab where multiple side-by-side blocks coexist.
Each block has shape:

    BRAND_NAME | COMUN | 5D | OSC
    model_1    | qty   | qty | qty
    model_2    | qty   | qty | qty
    ...
    (empty row or next BRAND row terminates the block)

SAMSUNG appears twice: once for the A-line and once for the S-line. We
distinguish them with a `sub_line` derived from the first model in the block.
"""

from typing import Dict, List, Optional, Tuple

from . import sheet_config as config


GlassKey = Tuple[str, str, str, str]


def _to_int(value) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if not s:
        return 0
    try:
        return int(float(s.replace(',', '.')))
    except (ValueError, TypeError):
        return 0


def _normalize_cell(value) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _samsung_sub_line(first_model: str) -> str:
    m = (first_model or '').strip().upper()
    if not m:
        return ''
    if m.startswith('S'):
        return 'S'
    if m.startswith('A'):
        return 'A'
    return m[:1]


def detect_blocks(values: List[List[str]]) -> List[dict]:
    """Detect blocks in a GLASS sheet.

    Returns a list of dicts with keys:
      brand, sub_line, header_row (1-based), model_col, comun_col, qty5d_col,
      qtyosc_col, model_rows (list of 1-based row indices), models (list of model
      names aligned with model_rows).
    """
    blocks: List[dict] = []
    if not values:
        return blocks

    n_rows = len(values)
    samsung_seen = 0

    header_positions: List[Tuple[int, int, str]] = []
    for r_idx, row in enumerate(values):
        for c_idx, cell in enumerate(row):
            text = _normalize_cell(cell).upper()
            if text not in config.GLASS_BRANDS:
                continue
            if c_idx + 3 >= len(row):
                continue
            q1 = _normalize_cell(row[c_idx + 1]).upper()
            q2 = _normalize_cell(row[c_idx + 2]).upper()
            q3 = _normalize_cell(row[c_idx + 3]).upper()
            if q1 == 'COMUN' and q2 == '5D' and q3 == 'OSC':
                header_positions.append((r_idx, c_idx, text))

    headers_by_col: Dict[int, List[Tuple[int, str]]] = {}
    for r, c, brand in header_positions:
        headers_by_col.setdefault(c, []).append((r, brand))

    for c_idx, lst in headers_by_col.items():
        lst.sort()

    for r_idx, c_idx, brand in header_positions:
        col_headers = headers_by_col[c_idx]
        next_header_row = n_rows
        for hr, _ in col_headers:
            if hr > r_idx:
                next_header_row = hr
                break

        model_col = c_idx
        comun_col = c_idx + 1
        qty5d_col = c_idx + 2
        qtyosc_col = c_idx + 3

        model_rows: List[int] = []
        models: List[str] = []
        for rr in range(r_idx + 1, next_header_row):
            row = values[rr] if rr < n_rows else []
            model = _normalize_cell(row[model_col]) if model_col < len(row) else ''
            if not model:
                continue
            model_rows.append(rr)
            models.append(model)

        sub_line = ''
        if brand == 'SAMSUNG':
            samsung_seen += 1
            sub_line = _samsung_sub_line(models[0] if models else '')
            if not sub_line:
                sub_line = 'A' if samsung_seen == 1 else 'S'

        blocks.append({
            'brand': brand,
            'sub_line': sub_line,
            'header_row': r_idx,
            'model_col': model_col,
            'comun_col': comun_col,
            'qty5d_col': qty5d_col,
            'qtyosc_col': qtyosc_col,
            'model_rows': model_rows,
            'models': models,
        })

    blocks.sort(key=lambda b: (b['model_col'], b['header_row']))
    return blocks


def parse_glass_values(values: List[List[str]]) -> Dict[GlassKey, int]:
    """Parse GLASS sheet values into a dict keyed by (brand, sub_line, model, quality)."""
    products: Dict[GlassKey, int] = {}
    blocks = detect_blocks(values)

    for block in blocks:
        brand = block['brand']
        sub_line = block['sub_line']
        for model, row_idx in zip(block['models'], block['model_rows']):
            row = values[row_idx] if row_idx < len(values) else []
            for quality, col in (
                ('COMUN', block['comun_col']),
                ('5D', block['qty5d_col']),
                ('OSC', block['qtyosc_col']),
            ):
                if quality in config.GLASS_IGNORED_QUALITIES:
                    continue
                qty = _to_int(row[col]) if col < len(row) else 0
                products[(brand, sub_line, model, quality)] = qty

    return products


def parse_glass_stock(spreadsheet_id: str) -> Dict[GlassKey, int]:
    from .google_sheets import get_worksheet

    try:
        ws = get_worksheet(spreadsheet_id, config.GLASS_TAB)
        if ws is None:
            return {}
        values = ws.get_all_values()
    except Exception as e:
        print(f"Error parsing glass stock: {e}")
        return {}

    return parse_glass_values(values)


def parse_glass_wanted(spreadsheet_id: str) -> Dict[GlassKey, int]:
    from .google_sheets import get_worksheet

    try:
        ws = get_worksheet(spreadsheet_id, config.WANTED_GLASS_TAB)
        if ws is None:
            return {}
        values = ws.get_all_values()
    except Exception as e:
        print(f"Error parsing glass wanted: {e}")
        return {}

    return parse_glass_values(values)


def normalize_model_name(name: str) -> str:
    if not name:
        return ''
    s = str(name).strip().upper()
    s = s.replace('  ', ' ')
    while '  ' in s:
        s = s.replace('  ', ' ')
    if s.startswith('IP '):
        s = s[3:]
    s = s.replace(' ', '')
    s = s.replace('-', '')
    s = s.replace('_', '')
    return s


def index_order_sheet(values: List[List[str]]) -> Dict[Tuple[str, str], Tuple[int, int]]:
    """Build an index of an order sheet tab.

    Returns dict mapping (section, normalized_model) -> (row_1based, qty_col_1based).
    Legacy sections (IPHONE 9D, REDMI 9D, ...) are skipped.
    """
    index: Dict[Tuple[str, str], Tuple[int, int]] = {}
    if not values:
        return index

    section_match: Dict[str, str] = {s.upper(): s for s in config.ORDER_GLASS_SECTIONS}
    legacy_upper = {s.upper() for s in config.ORDER_GLASS_LEGACY_SECTIONS}

    section_by_col: Dict[int, List[Tuple[int, Optional[str]]]] = {}

    def section_column_history(section_col: int) -> List[Tuple[int, Optional[str]]]:
        """Return list of (row_idx, section_or_None) events for a given column."""
        if section_col in section_by_col:
            return section_by_col[section_col]
        events: List[Tuple[int, Optional[str]]] = []
        for r_idx, row in enumerate(values):
            cell = _normalize_cell(row[section_col - 1]) if section_col - 1 < len(row) else ''
            if not cell:
                continue
            cell_u = cell.upper()
            matched = None
            if cell_u in section_match:
                matched = section_match[cell_u]
            else:
                for header_u, header_orig in section_match.items():
                    if header_u in cell_u:
                        matched = header_orig
                        break
            if matched is not None:
                events.append((r_idx, matched))
                continue
            legacy_hit = cell_u in legacy_upper or any(lg in cell_u for lg in legacy_upper)
            if legacy_hit:
                events.append((r_idx, None))
        section_by_col[section_col] = events
        return events

    def section_at(section_col: int, row_idx: int) -> Optional[str]:
        events = section_column_history(section_col)
        active: Optional[str] = None
        for ev_row, ev_section in events:
            if ev_row <= row_idx:
                active = ev_section
            else:
                break
        return active

    for pair in config.ORDER_GLASS_COLUMN_PAIRS:
        if len(pair) == 3:
            model_col, qty_col, section_col = pair
        else:
            model_col, qty_col = pair
            section_col = model_col

        for r_idx, row in enumerate(values):
            cell = _normalize_cell(row[model_col - 1]) if model_col - 1 < len(row) else ''
            if not cell:
                continue
            cell_u = cell.upper()

            if cell_u in section_match or any(h in cell_u for h in section_match.keys()):
                continue
            if cell_u in legacy_upper or any(lg in cell_u for lg in legacy_upper):
                continue
            if cell_u in ('MODELO', 'MODELOS', 'CANTIDAD', 'STOCK'):
                continue
            if cell_u in config.GLASS_BRANDS:
                continue

            current_section = section_at(section_col, r_idx)
            if current_section is None:
                continue

            normalized = normalize_model_name(cell)
            if not normalized:
                continue
            key = (current_section, normalized)
            if key not in index:
                index[key] = (r_idx + 1, qty_col)

    return index
