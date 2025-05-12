import os
import json
import re
import sqlite3
import shutil

# ------------------------------------------------------------
#  Inställningar
# ------------------------------------------------------------
BASE_TREE = r"C:\Users\Propietario\Desktop\data\tree"
DB_DIR    = r"C:\Users\Propietario\Desktop\data\db"
DB_PATH   = os.path.join(DB_DIR, "poker_ranges.db")

# ------------------------------------------------------------
#  Hjälpfunktioner
# ------------------------------------------------------------
def decode_folder_name(folder: str) -> tuple[str, str]:
    """
    'ffr25_btn'  ->  ('PF:F-F-R2.5', 'BTN')
    'ccx_sb'      ->  ('PF:C-C-X',    'SB')
    """
    if '_' not in folder:
        raise ValueError(f"Foldernamnet saknar '_': {folder}")

    seq_part, pos_part = folder.rsplit('_', 1)
    actions: list[str] = []

    i = 0
    while i < len(seq_part):
        ch = seq_part[i]
        if ch in "fcx":                        # fold / call / check
            actions.append(ch.upper())
            i += 1
        elif ch == 'r':                        # raise + belopp
            m = re.match(r"r(\d+)", seq_part[i:])
            if m:
                digits = m.group(1)            # '25' → 2.5
                if len(digits) == 1:
                    amt = digits
                else:
                    amt = f"{digits[:-1]}.{digits[-1]}"
                actions.append(f"R{amt}")
                i += 1 + len(digits)
            else:
                actions.append("R")
                i += 1
        else:                                  # okända tecken – hoppa
            i += 1

    raw_seq = "PF:" + "-".join(actions) if actions else "PF:"
    return raw_seq, pos_part.upper()


def init_db(db_path: str) -> sqlite3.Connection:
    """Skapar (eller nollställer) databasen och tabellerna."""
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    cur.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE nodes (
            id              INTEGER PRIMARY KEY,
            action_sequence TEXT NOT NULL,
            position        TEXT NOT NULL,
            folder_name     TEXT NOT NULL,
            file_path       TEXT NOT NULL
        );

        CREATE TABLE ranges (
            id        INTEGER PRIMARY KEY,
            node_id   INTEGER NOT NULL,
            action    TEXT NOT NULL,      -- 'c', 'f', 'x', 'r' …
            combo     TEXT NOT NULL,      -- 'AdKd', '2d2c' …
            frequency REAL NOT NULL,
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        );
        """
    )
    conn.commit()
    return conn


def import_tree(base_dir: str, conn: sqlite3.Connection):
    cur = conn.cursor()
    node_cnt = range_cnt = 0

    for dirpath, _, files in os.walk(base_dir):
        json_files = [f for f in files if f.endswith(".json")]
        if len(json_files) != 1:
            continue                          # inget eller flera JSON → hoppa

        folder    = os.path.basename(dirpath)
        file_path = os.path.join(dirpath, json_files[0])

        try:
            raw_seq, pos = decode_folder_name(folder)
        except Exception as e:
            print(f"[SKIP] {folder}: {e}")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cur.execute(
            """
            INSERT INTO nodes (action_sequence, position, folder_name, file_path)
            VALUES (?, ?, ?, ?)
            """,
            (raw_seq, pos, folder, file_path),
        )
        node_id = cur.lastrowid
        node_cnt += 1

        # data = { 'c': {...}, 'f': {...}, ... }
        for action_code, combos in data.items():
            for combo, freq in combos.items():
                cur.execute(
                    """
                    INSERT INTO ranges (node_id, action, combo, frequency)
                    VALUES (?, ?, ?, ?)
                    """,
                    (node_id, action_code, combo, float(freq)),
                )
                range_cnt += 1

    conn.commit()
    print(f"✓ Klart! {node_cnt} noder och {range_cnt} kombinationer importerade.")


# ------------------------------------------------------------
#  Huvudprogram
# ------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(DB_DIR, exist_ok=True)
    conn = init_db(DB_PATH)
    import_tree(BASE_TREE, conn)
    conn.close()
