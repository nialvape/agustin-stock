"""GLASS sheet parsing and order-sheet indexing utilities.

Wanted sheet layout (per brand block):
    BRAND | [act/X] | COMUN | [faltante] | [act/X] | 5D | [faltante] | [act/X] | OSC | [faltante]

Rules:
- The brand name (SAMSUNG, IPHONE, …) anchors the block at its column.
- Scanning right from there we collect quality tokens (COMUN, 5D, OSC) and
  faltante tokens.  The faltante column that immediately follows a quality
  token (with only stock/empty cells in between) belongs to that quality.
- SAMSUNG appears twice (A-line and S-line); the sub_line is inferred from
  the first model name in the block.
"""

from typing import Dict, List, Optional, Tuple

from . import sheet_config as config


GlassKey = Tuple[str, str, str, str]   # (brand, sub_line, model, quality)

_QUALITY_TOKENS = {'COMUN', '5D', 'OSC'}


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


def _norm(value) -> str:
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


def _is_stock_header(token: str) -> bool:
    u = (token or '').strip().upper()
    if u in {'STOCK', 'STK', 'ACTUAL', 'ACT'}:
        return True
    if u.startswith('ACT/') or u.startswith('ACT\\'):
        return True
    if 'ACT' in u.replace(' ', '') and '/' in u:
        return True
    return False


def _is_faltante(token: str) -> bool:
    u = (token or '').strip().upper()
    return bool(u) and (
        u in {'FALTANTE', 'FALTA', 'FALT', 'MISSING'} or u.startswith('FALT')
    )


def _parse_block_header(row: List[str], brand_col: int) -> Optional[dict]:
    """Scan right from brand_col to collect quality_cols and faltante_cols.

    Strategy: iterate columns left to right.
    - Quality token   → register it; it becomes the "pending quality".
    - Faltante token  → assign it to the pending quality (if any).
    - Stock header    → skip (visual reference column, ignore).
    - Another brand   → stop (start of a new block).
    - Anything else   → stop.

    Returns None if not all three qualities (COMUN, 5D, OSC) are found.
    """
    quality_cols: Dict[str, int] = {}
    faltante_cols: Dict[str, int] = {}
    last_quality: Optional[str] = None

    for c in range(brand_col + 1, min(len(row), brand_col + 35)):
        token = _norm(row[c]).upper()
        if not token:
            continue
        if token in config.GLASS_BRANDS:
            break
        if token in _QUALITY_TOKENS:
            if token in quality_cols:
                break   # duplicate → new block in same row, stop
            quality_cols[token] = c
            last_quality = token
        elif _is_faltante(token):
            if last_quality is not None and last_quality not in faltante_cols:
                faltante_cols[last_quality] = c
        elif _is_stock_header(token):
            pass    # skip stock-reference columns
        else:
            break   # unexpected token → end of this block header

    if not _QUALITY_TOKENS.issubset(quality_cols.keys()):
        return None

    return {'quality_cols': quality_cols, 'faltante_cols': faltante_cols}


def detect_blocks(values: List[List[str]]) -> List[dict]:
    """Detect all brand blocks in a glass sheet.

    Returns a list of block dicts with keys:
      brand, sub_line, header_row, model_col,
      quality_cols, faltante_cols, model_rows, models.

    Legacy aliases (qualities, stock_cols, comun_col, qty5d_col, qtyosc_col,
    block_end_col) are also populated for backwards compatibility.
    """
    if not values:
        return []

    n_rows = len(values)
    found: List[Tuple[int, int, str, dict]] = []  # (row, col, brand, parsed)

    for r, row in enumerate(values):
        for c, cell in enumerate(row):
            text = _norm(cell).upper()
            if text not in config.GLASS_BRANDS:
                continue
            parsed = _parse_block_header(row, c)
            if parsed is None:
                continue
            found.append((r, c, text, parsed))

    # Index header rows per column to compute block boundaries
    rows_by_col: Dict[int, List[int]] = {}
    for r, c, _brand, _parsed in found:
        rows_by_col.setdefault(c, []).append(r)
    for lst in rows_by_col.values():
        lst.sort()

    samsung_seen = 0
    blocks = []

    for r, c, brand, parsed in found:
        col_rows = rows_by_col[c]
        next_header = n_rows
        for hr in col_rows:
            if hr > r:
                next_header = hr
                break

        quality_cols: Dict[str, int] = parsed['quality_cols']
        faltante_cols: Dict[str, int] = parsed['faltante_cols']

        model_rows: List[int] = []
        models: List[str] = []
        for rr in range(r + 1, next_header):
            row_data = values[rr] if rr < n_rows else []
            model = _norm(row_data[c]) if c < len(row_data) else ''
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
            'header_row': r,
            'model_col': c,
            'quality_cols': quality_cols,
            'faltante_cols': faltante_cols,
            'model_rows': model_rows,
            'models': models,
            # legacy aliases
            'qualities': quality_cols,
            'stock_cols': {},
            'comun_col': quality_cols.get('COMUN', -1),
            'qty5d_col': quality_cols.get('5D', -1),
            'qtyosc_col': quality_cols.get('OSC', -1),
            'block_end_col': max(quality_cols.values(), default=c),
        })

    blocks.sort(key=lambda b: (b['model_col'], b['header_row']))
    return blocks


def parse_glass_values(
    values: List[List[str]],
    blocks: Optional[List[dict]] = None,
) -> Dict[GlassKey, int]:
    """Parse glass sheet values into {(brand, sub_line, model, quality): qty}.

    If a block has faltante_cols the qty is read from the faltante column;
    otherwise from the quality column itself (stock/deseado layout).
    """
    if blocks is None:
        blocks = detect_blocks(values)

    products: Dict[GlassKey, int] = {}
    for block in blocks:
        brand = block['brand']
        sub_line = block['sub_line']
        quality_cols: Dict[str, int] = block.get('quality_cols') or block.get('qualities', {})
        faltante_cols: Dict[str, int] = block.get('faltante_cols') or {}

        for model, row_idx in zip(block['models'], block['model_rows']):
            row = values[row_idx] if row_idx < len(values) else []
            for quality, qcol in quality_cols.items():
                if quality in config.GLASS_IGNORED_QUALITIES:
                    continue
                src = faltante_cols.get(quality, qcol)
                qty = _to_int(row[src]) if src < len(row) else 0
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


def parse_glass_wanted(spreadsheet_id: str) -> Tuple[Dict[GlassKey, int], bool]:
    """Read the wanted GLASS sheet.

    Returns ({(brand, sub_line, model, quality): faltante_qty}, uses_faltante_layout).
    """
    from .google_sheets import get_worksheet

    try:
        ws = get_worksheet(spreadsheet_id, config.WANTED_GLASS_TAB)
        if ws is None:
            return {}, False
        values = ws.get_all_values()
    except Exception as e:
        print(f"Error parsing glass wanted: {e}")
        return {}, False

    blocks = detect_blocks(values)
    uses_faltante = any(bool(b.get('faltante_cols')) for b in blocks)
    return parse_glass_values(values, blocks=blocks), uses_faltante


# ---------------------------------------------------------------------------
# Model name normalisation
# ---------------------------------------------------------------------------

def normalize_model_name(name: str) -> str:
    if not name:
        return ''
    s = str(name).strip().upper()
    while '  ' in s:
        s = s.replace('  ', ' ')
    if s.startswith('IP '):
        s = s[3:]
    s = s.replace(' ', '').replace('-', '').replace('_', '')
    return s


# ---------------------------------------------------------------------------
# Order-sheet index
# ---------------------------------------------------------------------------

def index_order_sheet(values: List[List[str]]) -> Dict[Tuple[str, str], Tuple[int, int]]:
    """Build an index of an order sheet tab.

    Returns dict mapping (section, normalized_model) -> (row_1based, qty_col_1based).
    Legacy sections (IPHONE 9D, REDMI 9D, …) are skipped.
    """
    index: Dict[Tuple[str, str], Tuple[int, int]] = {}
    if not values:
        return index

    section_match: Dict[str, str] = {s.upper(): s for s in config.ORDER_GLASS_SECTIONS}
    legacy_upper = {s.upper() for s in config.ORDER_GLASS_LEGACY_SECTIONS}

    _section_cache: Dict[int, List[Tuple[int, Optional[str]]]] = {}

    def _section_events(section_col_1based: int) -> List[Tuple[int, Optional[str]]]:
        if section_col_1based in _section_cache:
            return _section_cache[section_col_1based]
        events: List[Tuple[int, Optional[str]]] = []
        col0 = section_col_1based - 1
        for r_idx, row in enumerate(values):
            cell = _norm(row[col0]) if col0 < len(row) else ''
            if not cell:
                continue
            cell_u = cell.upper()
            matched: Optional[str] = None
            if cell_u in section_match:
                matched = section_match[cell_u]
            else:
                for hu, ho in section_match.items():
                    if hu in cell_u:
                        matched = ho
                        break
            if matched is not None:
                events.append((r_idx, matched))
                continue
            if cell_u in legacy_upper or any(lg in cell_u for lg in legacy_upper):
                events.append((r_idx, None))
        _section_cache[section_col_1based] = events
        return events

    def _section_at(section_col_1based: int, row_idx: int) -> Optional[str]:
        active: Optional[str] = None
        for ev_row, ev_sec in _section_events(section_col_1based):
            if ev_row <= row_idx:
                active = ev_sec
            else:
                break
        return active

    skip_upper = {'MODELO', 'MODELOS', 'CANTIDAD', 'STOCK'}

    for pair in config.ORDER_GLASS_COLUMN_PAIRS:
        if len(pair) == 3:
            model_col, qty_col, section_col = pair
        else:
            model_col, qty_col = pair
            section_col = model_col

        col0 = model_col - 1
        for r_idx, row in enumerate(values):
            cell = _norm(row[col0]) if col0 < len(row) else ''
            if not cell:
                continue
            cell_u = cell.upper()
            if cell_u in section_match or any(h in cell_u for h in section_match):
                continue
            if cell_u in legacy_upper or any(lg in cell_u for lg in legacy_upper):
                continue
            if cell_u in skip_upper or cell_u in config.GLASS_BRANDS:
                continue

            current_section = _section_at(section_col, r_idx)
            if current_section is None:
                continue

            normalized = normalize_model_name(cell)
            if not normalized:
                continue
            key = (current_section, normalized)
            if key not in index:
                index[key] = (r_idx + 1, qty_col)

    return index
