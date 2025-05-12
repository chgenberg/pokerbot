#!/usr/bin/env python
"""
Bygger poker-databasen poker_ranges.db från katalogstrukturen …\data\tree

• Går rekursivt genom alla undermappar
• Läser exakt en JSON-fil per mapp
• Avkodar mappnamnet (ex. 'ffr25_btn') → action-sekvens + position
• Normaliserar positioner med en alias-tabell (UTG = LJ = LowJack …)
• Lagrar allt i SQLite-tabellerna: nodes, ranges, position_alias
"""

import os
import json
import re
import sqlite3
import shutil
from pathlib import Path

# ------------------------------------------------------------
#  KONFIGURATION
# ------------------------------------------------------------
BASE_TREE = Path(r"C:\Users\Propietario\Desktop\data\tree")
DB_DIR    = Path(r"C:\Users\Propietario\Desktop\data\db")
DB_PATH   = DB_DIR / "poker_ranges.db"

# ------------------------------------------------------------
#  POSITION­ALIASER
#   canonical : [ list med alla alias ]
# ------------------------------------------------------------
POSITION_ALIASES = {
    "UTG": ["UTG", "EP1", "P1", "LJ", "LOWJACK", "LOW_JACK"],
    "HJ" : ["HJ", "HIGHJACK", "P2", "P3"],
    "CO" : ["CO", "CUTOFF"],
    "BTN": ["BTN", "BUTTON"],
    "SB" : ["SB", "SMALLBLIND", "SMALL_BLIND"],
    "BB" : ["BB", "BIGBLIND", "BIG_BLIND"],
}

POSITION_ORDER = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]  # 6-handed

def _sanitize(s: str) -> str:
    """Bort med mellanslag/underscore + till VERSALER"""
    return s.upper().replace(" ", "").replace("_", "")

# alias   -> canonical
ALIAS_TO_CANON = { _sanitize(a): canon
                   for canon, lst in POSITION_ALIASES.items()
                   for a in lst }

# alias   -> ordinal (1..6)
ALIAS_TO_ORD   = { _sanitize(a): 1 + POSITION_ORDER.index(canon)
                   for canon, lst in POSITION_ALIASES.items()
                   for a in lst }

# ------------------------------------------------------------
#  HJÄLPFUNKTIONER
# ------------------------------------------------------------
def decode_folder_name(folder: str) -> tuple[str, str]:
    """
    'ffr25_btn' → ('PF:F-F-R2.5', 'BTN')
    'ccx_lj'    → ('PF:C-C-X',    'LJ')
    """
    if "_" not in folder:
        raise ValueError("Mappnamnet saknar '_'")

    seq_part, pos_part = folder.rsplit("_", 1)
    actions: list[str] = []
    i = 0
    while i < len(seq_part):
        ch = seq_part[i]
        if ch in "fcx":          # fold / call / check
            actions.append(ch.upper())
            i += 1
        elif ch == "r":          # raise + belopp
            m = re.match(r"r(\d+)", seq_part[i:])
            if m:
                digits = m.group(1)          # '25' → 2.5
                if len(digits) == 1:
                    amt = digits
                else:
                    amt = f"{digits[:-1]}.{digits[-1]}"
                actions.append(f"R{amt}")
                i += 1 + len(digits)
            else:
                actions.append("R")
                i += 1
        else:                    # okänt tecken → hoppa
            i += 1

    raw_seq = "PF:" + "-".join(actions) if actions else "PF:"
    return raw_seq, pos_part


def init_db(db_path: Path) -> sqlite3.Connection:
    """Skapar (eller nollställer) databasen + alla tabeller"""
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    c    = conn.cursor()

    c.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE position_alias (
            alias     TEXT PRIMARY KEY,
            canonical TEXT NOT NULL,
            ordinal   INTEGER NOT NULL
        );

        CREATE TABLE nodes (
            id              INTEGER PRIMARY KEY,
            action_sequence TEXT NOT NULL,
            position        TEXT NOT NULL,   -- kanoniskt namn
            folder_name     TEXT NOT NULL,
            file_path       TEXT NOT NULL
        );

        CREATE TABLE ranges (
            id        INTEGER PRIMARY KEY,
            node_id   INTEGER NOT NULL,
            action    TEXT NOT NULL,   -- 'c', 'f', 'x', 'r' …
            combo     TEXT NOT NULL,   -- 'AdKd', '2d2c' …
            frequency REAL NOT NULL,
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        );
        """
    )

    # Fyll alias-tabellen
    rows = [(alias, canon, ALIAS_TO_ORD[_sanitize(alias)])
            for canon, aliases in POSITION_ALIASES.items()
            for alias in aliases]
    c.executemany(
        "INSERT INTO position_alias (alias, canonical, ordinal) VALUES (?, ?, ?)",
        rows
    )

    conn.commit()
    return conn


def canonize_pos(raw_pos: str) -> str:
    """UTG/lj/low jack -> 'UTG' (om känt), annars versalt råvärde"""
    key = _sanitize(raw_pos)
    return ALIAS_TO_CANON.get(key, raw_pos.upper())


def import_tree(base_dir: Path, conn: sqlite3.Connection):
    c = conn.cursor()
    node_cnt = range_cnt = 0

    for dirpath, _, files in os.walk(base_dir):
        json_files = [f for f in files if f.endswith(".json")]
        if len(json_files) != 1:
            continue                            # hoppa mappar utan exakt en JSON

        folder    = os.path.basename(dirpath)
        file_path = os.path.join(dirpath, json_files[0])

        try:
            raw_seq, raw_pos = decode_folder_name(folder)
        except Exception as e:
            print(f"[SKIP] {folder}: {e}")
            continue

        pos = canonize_pos(raw_pos)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # --- nodes ---
        c.execute(
            """
            INSERT INTO nodes (action_sequence, position, folder_name, file_path)
            VALUES (?, ?, ?, ?)
            """,
            (raw_seq, pos, folder, file_path)
        )
        node_id = c.lastrowid
        node_cnt += 1

        # --- ranges ---
        # data = { 'c': {...}, 'f': {...}, ... }
        for action_code, combos in data.items():
            for combo, freq in combos.items():
                c.execute(
                    """
                    INSERT INTO ranges (node_id, action, combo, frequency)
                    VALUES (?, ?, ?, ?)
                    """,
                    (node_id, action_code, combo, float(freq))
                )
                range_cnt += 1

    conn.commit()
    print(f"✓ Import klar – {node_cnt} noder och {range_cnt} handrader insatta.")


# ------------------------------------------------------------
#  MAIN
# ------------------------------------------------------------
if __name__ == "__main__":
    BASE_TREE.mkdir(parents=True, exist_ok=True)  # säkerställ att mapp finns
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = init_db(DB_PATH)
    import_tree(BASE_TREE, conn)
    conn.close()

    print(f"\nDatabasen skapad: {DB_PATH}")
    print("Alias-tabellen innehåller även 'LJ / LOWJACK' → UTG.\n")
