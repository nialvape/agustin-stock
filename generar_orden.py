#!/usr/bin/env python3
"""Lee config.txt y ejecuta generate_order.py según locales y tipos de stock."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.txt"
GENERATE = ROOT / "generate_order.py"

_ALL_LOCALES = frozenset(
    {"todos", "all", "*", "todas", "cualquiera", "every", "everyone"}
)


def _truthy(raw: str) -> bool:
    s = (raw or "").strip().lower()
    return s in ("1", "true", "yes", "si", "sí", "on", "s", "y")


def load_config(path: Path) -> dict:
    """Devuelve locales: list[str] | None (None = todos) y stock_types: list['GLASS'|'ACCESORIOS']."""
    locales_mode_all = True
    locale_list: list[str] = []
    do_glass = True
    do_acc = True

    if not path.is_file():
        print(f"No existe {path}. Copiá config.txt de ejemplo o crealo.")
        sys.exit(1)

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip().upper()
        val = val.strip()

        if key in ("LOCALES", "LOCALE", "STORES", "STORE", "SUCURSALES"):
            vlow = val.lower()
            if vlow in _ALL_LOCALES or not val:
                locales_mode_all = True
                locale_list = []
            else:
                locales_mode_all = False
                locale_list = [x.strip() for x in val.split(",") if x.strip()]
        elif key == "GLASS":
            do_glass = _truthy(val)
        elif key in ("ACCESORIOS", "ACCE", "ACCESORIO"):
            do_acc = _truthy(val)

    stock_types: list[str] = []
    if do_glass:
        stock_types.append("GLASS")
    if do_acc:
        stock_types.append("ACCESORIOS")

    if not stock_types:
        print("config.txt: activá al menos uno entre GLASS=si y ACCESORIOS=si")
        sys.exit(1)

    if not locales_mode_all and not locale_list:
        print("config.txt: LOCALES está vacío. Usá TODOS o una lista como COTO, LA PLATA")
        sys.exit(1)

    return {
        "all_stores": locales_mode_all,
        "stores": locale_list,
        "stock_types": stock_types,
    }


def main() -> None:
    cfg = load_config(CONFIG_PATH)
    stock_types: list[str] = cfg["stock_types"]
    all_stores: bool = cfg["all_stores"]
    stores: list[str] = cfg["stores"]

    jobs: list[tuple[str | None, str]] = []
    for st in stock_types:
        if all_stores:
            jobs.append((None, st))
        else:
            for store in stores:
                jobs.append((store, st))

    print(f"Ejecuciones planificadas: {len(jobs)}")
    for store, st in jobs:
        label = store or "(todos los locales)"
        print(f"\n--- {label} | {st} ---")
        cmd = [sys.executable, str(GENERATE), "--stock_type", st]
        if store:
            cmd.extend(["--store", store])
        r = subprocess.run(cmd, cwd=str(ROOT))
        if r.returncode != 0:
            print(f"[ERROR] generate_order terminó con código {r.returncode}")
            sys.exit(r.returncode)

    print("\nListo: todas las ejecuciones terminaron bien.")


if __name__ == "__main__":
    main()
