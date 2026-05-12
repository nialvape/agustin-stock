"""WANTED accesorios ↔ fila del pedido (columna A de ``ACCE``).

1. ``WANTED_TO_ORDER_ALIASES``: equivalencias razonables (mismo ítem / nombre casi igual).
2. Coincidencia exacta o normalizada.
3. Fuzzy solo como respaldo (umbral alto) para probar generación de órdenes.

Los valores de alias deben existir en la columna A del pedido (misma ortografía
que en la planilla). Si tu pedido difiere, ajustá el dict o el umbral ``FUZZY_MIN_SCORE``.
"""

from __future__ import annotations

import re
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

# Umbral del respaldo fuzzy (0–1). Más alto = menos emparejamientos dudosos.
FUZZY_MIN_SCORE = 0.52

_ORDER_SECTION_LABELS: FrozenSet[str] = frozenset({
    'CARGADORES ENTEROS',
    'CABLES',
    'AURICULAR',
    'PARLANTE',
    'ACCESORIOS',
    'MEMO-PEN',
})

_WANTED_CATEGORY: FrozenSet[str] = frozenset({
    'CARGADORES', 'ADAPTADORES', 'CABLES', 'HOLDER',
    'PARLANTES', 'ACCESORIOS', 'MEMO-PEN', 'AURICULARES',
    'PRODUCTO',
})

# wanted (texto en planilla) -> order columna A (tal cual en tu ACCE de referencia)
WANTED_TO_ORDER_ALIASES: Dict[str, str] = {
    'JBL GO4': 'JBL G0 4',
    'IPHONE C- LIGHTNING': 'IPHONE C-LIGHTNING 20W',
    'IPHONE C-LIGHTNING': 'IPHONE C-LIGHTNING 20W',
    'POWERBANK 10000 MAH': 'BATTERY PACK 10000 C/LOGO',
    'POWERBANK 20000 MAH': 'BATTERY PACK 10000 C/LOGO',
    'POWERBANK 30000 MAH': 'BATTERY PACK 10000 C/LOGO',
    'BATTERY PACK': 'BATTERY PACK 10000 C/LOGO',
    'MAGSAFE CHARGER INALAMBRICO': 'MAGSAFE CHARGER',
    'INALAMBRICO': 'INALAMBRICO 3 EN 1 MESA',
    'INALAMBRICO PLEGABLE': 'INALAMBRICO 3 EN 1 PLEGABLE',
    'INALAMBRICO PLEGABLE   ': 'INALAMBRICO 3 EN 1 PLEGABLE',
    'INALAMBRICO MESA 3 EN 1': 'INALAMBRICO 3 EN 1 MESA',
    'INALAMBRICO MESA 3 EN 1 ': 'INALAMBRICO 3 EN 1 MESA',
    'AUTO PRO21 ULTRA RAPIDO C': 'PRO 21 AUTO USB+C',
    'AUTO PRO21 ULTRA RAPIDO C ': 'PRO 21 AUTO USB+C',
    'AUTO PRO21 ULTRA RAPIDO IPHONE': 'PRO 21 AUTO USB+LIGHTNING',
    'AUTO PRO21 ULTRA RAPIDO IPHONE ': 'PRO 21 AUTO USB+LIGHTNING',
    'IPHONE C 20W': 'IPHONE 20W ALTO OBLICUA',
    'IPHONE C 35W': 'IPHONE 35W ALTO OBLICUA',
    'IPHONE C 40W': 'IPHONE 40W',
    'IPHONE USB 5W': 'IPHONE 20W ALTO OBLICUA',
    'IPHONE C-C': 'IPHONE C-C 20W',
    'C RAP-PUXIDA DK-45': 'PUXIDA DK-45 4.2 C',
    'C RAP': 'PUXIDA DK-45 4.2 C',
    'V8 GEN': 'V8 GEN PROMI MICRO',
    'V8 RAP': 'PUXIDA E-51 3A V8',
    'IP RAP': 'IPHONE 20W ALTO OBLICUA',
    'PARED C-C RAP': 'IPHONE 35W ALTO OBLICUA',
    'PRO 21 45W': 'PRO 21 AUTO USB+C',
    'AUTO RAPIDO USB-C': 'PRO 21 AUTO USB+C',
    'AUTO RAPIDO USB-C (MINI)': 'AUTO PUXIDA G-26 (MINI)',
    'AUTO RAPIDO USB-USB': 'PRO 21 AUTO USB+LIGHTNING',
    'ADAPTADOR USB DK-31': 'PUXIDA DK-41',
    'ADAPTADOR USB RAPIDO DK-41/BL-40': 'PUXIDA DK-41',
    'ADAPTADOR USB+C 25W DK-33/DK-33/BL-70': 'PUXIDA DK-33/BL-70',
    'ADAPTADOR USB+C 45W DK-56': 'PUXIDA DK-56',
    'SAMSUNG C-C 1.8': 'SAMSUNG C-C 1.8m',
    'IPHONE USB-IP': 'LIGHTNING-USB',
    'IPHONE C-IP': 'LIGHTNING-C',
    'AUX-C': 'AUXILIAR-C E-102',
    'AUX-IP': 'AUXILIAR-IP E-101',
    'PALO DE SELFIE': 'TRIPODE-PALO SELFIE PUXIDA',
    'TRIPODE CONTROL': 'TRIPODE FETUZZ F-SR003',
    'TRIPODE INTELIGENTE': 'TRIPODE FETUZZ F-SR003',
    'TRIPODE FETUZZ': 'TRIPODE FETUZZ F-SR003',
    'LAPIZ OPTICO': 'LAPIZ OPTICO UNIVERSAL',
    'OTG USB-C': 'OTG TC-USB FETUZZ FL005',
    'OTG C-IP': 'OTG TC-L FETUZZ FL007',
    'OTG C-USB': 'OTG USB-TC FETUZZ FL006',
    'FLIP 6': 'FLIP 6',
    'FLIP 6 ': 'FLIP 6',
    'FLIP 6 MAX': 'FLIP 6 MAX',
    'FLIP 6 MAX ': 'FLIP 6 MAX',
    'BEATS PRO': 'BEATS',
    'AIRPOD NEGRO': 'E6S NEGRO',
    'AIRPOD PUXIDA C-80': 'BT PUXIDA C-80',
    'AIRPOD PUXIDA C-82': 'BT PUXIDA C-82',
    'IPHONE LIGHTNING': 'IPHONE LIGHTNING DIRECTO',
    'IPHONE "C"': 'IPHONE C DIRECTO',
    'MOTO-BICI': 'MOTO BICI',
    'TYG BICI': 'TYG BICI',
    'PARED INTER': 'ADAPTADOR INTERNACIONAL',
    'CAR BT X8': 'RECEPTOR BLUETOTH AUXILIAR',
    'CAR BT': 'RECEPTOR BLUETOTH AUXILIAR',
    'CAR BT ': 'RECEPTOR BLUETOTH AUXILIAR',
    'KARAOKE': 'TG-464',
    'IPX6': 'TG-464',
    'SOUL XK 200': 'TG-464',
    'SOUL XS 10 (BICI)': 'TYG BICI',
    'SOUL XK 50': 'TG 645',
    'SOUL XK 50 ': 'TG 645',
    'SOUL XS650': 'TG 645',
    'M9': 'TG 645',
    'P192 BOOM BOX 3 PRO': 'TG 645',
    'BOOM S380': 'TG 645',
    'RX11S': 'CHARGE 10',
    'P16 PRO': 'P21 PRO',
    'C-C RAP': 'C-C PUXIDA CB-55',
    'C-LIGHTNING RAP': 'C-LIGHTNING CB-15',
    'DESMONTABLE': 'ADAPTADOR-CABEZAL',
    'MAGNETICO TIPO C': 'MOTOROLA C-C',
    'MAGNETICO C-C': 'SAMSUNG C-C 1m',
    'MESA /REPOSERA': 'INALAMBRICO 3 EN 1 MESA',
    'PUXIDA LUCES C-C': 'PUXIDA 4 IN 1 CB-50',
    'PUXIDA LUCES C-IP': 'PUXIDA C-IP CB 0-8 (CARGA)',
    'LAMBOTECH LT-416': 'LAMBOTECH TYPE C',
    'FETUZZ F-SP001': 'PUXIDA SP-01',
    'FETUZZ F-SP012': 'PUXIDA SP-06',
    'SOPORTE LAMBOTECH 069': 'SOPORTE AUTO',
    'SOPORTE PUXIDA MESA SP-02': 'PUXIDA SP-06',
    'SOPORTE PUXIDA MESA SP-03': 'SP-03 MESA',
    'SOPORTE PUXIDA MESA SP-10': 'SP-10',
    'SOPORTE PUXIDA TABLET SP-50': 'PUXIDA SP-31',
    'SOPORTE PUXIDA TABLET SP-51': 'PUXIDA SP-35',
    'RT-620/RT-803': 'RT-620-803(ESPEJO)',
    'RT-699': 'RT-69b (SOPAPA 360)',
    'RT-60F': 'RT-69b (SOPAPA 360)',
    'B072': 'RT-620-803(ESPEJO)',
    'Q40': 'PUXIDA SP-08',
    'A052': 'SOPORTE AUTO',
    'RCA': 'AUXILIAR E203',
    'HDMI 1.5M': 'C-38 TPC',
    'HDMI- C': 'C-28 TPC',
    'AIRPOD SPORT 200': 'E6S NEGRO',
    'AIRPOD SPORT 250': 'ULTRAPODS',
    'AIRPOD W70': 'ULTRAPODS',
    'PUXIDA C-105': 'BT PUXIDA C-80',
    'SOUL BT S150': 'VINCHA PUXIDA BT C-107',
    'SOUL CABLE 500': 'AUXILIAR-C E-102',
    'SOUL S389': 'SONY M5',
    'SOUL S589': 'BEATS',
    'TWS 1100': 'ULTRAPODS',
    'TWS 1400': 'BEATS',
    'TWS 200': 'E6S NEGRO',
    'VINCHA GAMER': 'VINCHA HAVIT H220D',
    'BT SPORT B-019': 'C-20 AUXILIAR',
    'BT SPORT B-020': 'C-22 AUXILIAR',
    'SOUL BT 250': 'VINCHA HAVIT H220D',
    'SOUL BT 400': 'VINCHA PUXIDA BT C-107',
    'POP SOCKET': 'SOPORTE AUTO',
    'ANILLO BRILLO': 'SOPORTE AUTO',
    'ANILLO SOPORTE': 'SOPORTE AUTO',
    'CORREA MANO': 'SOPORTE AUTO',
    'EXTENSOR USB': 'OTG USB-TC FETUZZ FL006',
    'ENTRADA TIPO C': 'C-28 TPC',
    'MICROFONO CORBATERO TIPO C': 'C-20 AUXILIAR',
    'MICROFONO CORBATERO IPHONE': 'C-22 AUXILIAR',
    'MICROFONO CORBATERO CON BASE': 'C-28 TPC',
    'AURI SAMSUNG': 'SAMSUNG BLANCO BOLSITA',
    'AURI MOTOROLA': 'MOTOROLA C',
    'AURI IP': 'IPHONE LIGHTNING DIRECTO',
    'MOTOROLA V8': 'MOTOROLA C',
}


def _norm(s: str) -> str:
    s = (s or '').strip().upper()
    s = s.replace('"', '').replace("'", '')
    s = re.sub(r'[\s/]+', ' ', s)
    s = re.sub(r'[^A-Z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _tokens(s: str) -> List[str]:
    return [t for t in _norm(s).split() if len(t) > 1]


def parse_order_column_a_products(values: Sequence[Sequence[str]]) -> List[str]:
    names: List[str] = []
    if not values:
        return names
    for row in values[1:]:
        if not row:
            continue
        cell = str(row[0]).strip()
        if not cell:
            continue
        if cell.upper() in _ORDER_SECTION_LABELS:
            continue
        names.append(cell)
    return names


def wanted_category_titles() -> FrozenSet[str]:
    return _WANTED_CATEGORY


def collect_wanted_product_names(values: Sequence[Sequence[str]]) -> List[str]:
    seen = set()
    out: List[str] = []
    for row in values:
        for col_idx, qty_col in ((0, 3), (4, 7)):
            if len(row) <= col_idx:
                continue
            name = str(row[col_idx]).strip()
            if not name or name.upper() in _WANTED_CATEGORY:
                continue
            try:
                q = int(float(str(row[qty_col]).strip())) if len(row) > qty_col and row[qty_col] else 0
            except (ValueError, TypeError):
                q = 0
            if q <= 0:
                continue
            if name not in seen:
                seen.add(name)
                out.append(name)
    return out


def collect_all_wanted_product_names(values: Sequence[Sequence[str]]) -> List[str]:
    """Todos los nombres en columnas A y E de la WANTED (excl. títulos de categoría).

    No filtra por faltante ni stock: sirve para sembrar filas en ``product_mapping``.
    """
    seen = set()
    out: List[str] = []
    for row in values:
        for col_idx in (0, 4):
            if len(row) <= col_idx:
                continue
            name = str(row[col_idx]).strip()
            if not name or name.upper() in _WANTED_CATEGORY:
                continue
            if name not in seen:
                seen.add(name)
                out.append(name)
    return out


def match_wanted_to_order(
    wanted: str,
    order_names: Sequence[str],
) -> Tuple[Optional[str], str]:
    w = (wanted or '').strip()
    if not w:
        return None, 'empty'

    alias = WANTED_TO_ORDER_ALIASES.get(w) or WANTED_TO_ORDER_ALIASES.get(w.strip())
    if alias:
        if alias in order_names:
            return alias, 'alias'
        al = alias.lower()
        for o in order_names:
            if o.lower() == al:
                return o, 'alias_ci'

    w_low = w.lower()
    for o in order_names:
        if o.lower() == w_low:
            return o, 'exact_ci'

    nw = _norm(w)
    norm_map = {_norm(o): o for o in order_names}
    if nw in norm_map:
        return norm_map[nw], 'norm_exact'

    wt = set(_tokens(w))
    best_j = 0.0
    best_name: Optional[str] = None
    for o in order_names:
        no = _norm(o)
        ot = set(_tokens(o))
        if not wt or not ot:
            continue
        inter = len(wt & ot)
        union = len(wt | ot) or 1
        j = inter / union
        if nw and (no in nw or nw in no) and min(len(nw), len(no)) >= 4:
            j = max(j, 0.5)
        if j > best_j:
            best_j = j
            best_name = o

    if best_name is not None and best_j >= FUZZY_MIN_SCORE:
        return best_name, f'fuzzy={best_j:.2f}'

    return None, 'no_match'


def load_order_accesorios_product_names(spreadsheet_id: str, tab: str) -> List[str]:
    from .google_sheets import get_worksheet

    ws = get_worksheet(spreadsheet_id, tab)
    if ws is None:
        return []
    return parse_order_column_a_products(ws.get_all_values())


def build_wanted_to_order_map(
    wanted_names: Sequence[str],
    order_names: Sequence[str],
) -> Tuple[Dict[str, str], List[str]]:
    order_list = list(order_names)
    mapping: Dict[str, str] = {}
    failures: List[str] = []
    for w in wanted_names:
        hit, _why = match_wanted_to_order(w, order_list)
        if hit:
            mapping[w] = hit
        else:
            failures.append(w)
    return mapping, failures
