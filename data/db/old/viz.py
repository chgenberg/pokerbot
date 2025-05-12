#!/usr/bin/env python
# browse_db.py – interaktiv utforskning av poker_ranges.db

import sqlite3
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from tabulate import tabulate

DB_PATH = Path(r"C:\Users\Propietario\Desktop\data\db\poker_ranges.db")


# ------------------------------------------------------------------
#  SQL-hjälpare
# ------------------------------------------------------------------
def open_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(path)
    return sqlite3.connect(path)


def get_positions(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT position, COUNT(*) AS n "
        "FROM nodes GROUP BY position ORDER BY n DESC",
        conn
    )


def get_nodes_for_position(conn, pos: str) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT id, action_sequence AS seq, folder_name "
        "FROM nodes WHERE position = ? ORDER BY seq",
        conn, params=(pos,)
    )


def summary_for_node(conn, node_id: int) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT action, SUM(frequency) AS freq "
        "FROM ranges WHERE node_id = ? GROUP BY action "
        "ORDER BY freq DESC",
        conn, params=(node_id,)
    )


def top_combos(conn, node_id: int, action: str, limit=20) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT combo, frequency "
        "FROM ranges WHERE node_id = ? AND action = ? "
        "ORDER BY frequency DESC LIMIT ?",
        conn, params=(node_id, action, limit)
    )


# ------------------------------------------------------------------
#  Interaktiv loop
# ------------------------------------------------------------------
def main():
    conn = open_db(DB_PATH)

    while True:
        # --- nivå 1: positioner ---
        pos_df = get_positions(conn)
        print("\n=== Positioner ===")
        print(tabulate(pos_df, headers="keys", showindex=True, tablefmt="psql"))

        sel = input("\nVälj index (Enter för avsluta): ").strip()
        if sel == "":
            break
        if not sel.isdigit() or int(sel) not in pos_df.index:
            continue

        position = pos_df.loc[int(sel), "position"]

        # --- nivå 2: noder för vald position ---
        node_df = get_nodes_for_position(conn, position)
        if node_df.empty:
            print("Inga noder.")
            continue

        print(f"\n=== Noder för {position} ===")
        print(tabulate(node_df, headers="keys", showindex=True, tablefmt="psql"))

        sel2 = input("\nVälj nod-index (Enter för bakåt): ").strip()
        if sel2 == "":
            continue
        if not sel2.isdigit() or int(sel2) not in node_df.index:
            continue

        node_id = int(node_df.loc[int(sel2), "id"])

        # --- nivå 3: statistik för vald nod ---
        summ = summary_for_node(conn, node_id)
        print(f"\n=== Action-frekvenser – node {node_id} ===")
        print(tabulate(summ, headers=["Action", "Total frekvens"], tablefmt="psql"))

        # visa topp-kombos per action
        for act in summ["action"]:
            combos = top_combos(conn, node_id, act)
            print(f"\n-- Topp {len(combos)} kombos för '{act}' --")
            print(tabulate(combos, headers=["Combo", "Freq"], tablefmt="github"))

        # snabb graf?
        if input("\nVisa stapel-graf? (y/N): ").lower() == "y":
            plt.figure()
            plt.bar(summ["action"], summ["freq"])
            plt.title(f"Node {node_id} – action-frekvenser")
            plt.tight_layout()
            plt.show()

        input("\n[Enter] för bakåt")

    conn.close()
    print("Avslutar.")


if __name__ == "__main__":
    main()
