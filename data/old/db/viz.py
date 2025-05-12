#!/usr/bin/env python
"""
Visualiserar poker-databasen som skapades av build_db.py
Kör:  python viz_db.py
"""

import sqlite3
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# ------------------------------------------------------------
#  KONFIG
# ------------------------------------------------------------
DB_PATH = Path(r"C:\Users\Propietario\Desktop\data\db\poker_ranges.db")

# ------------------------------------------------------------
#  HJÄLPFUNKTIONER
# ------------------------------------------------------------
def open_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(path)
    return sqlite3.connect(path)


def list_positions(conn):
    df = pd.read_sql_query(
        "SELECT position, COUNT(*) AS n FROM nodes GROUP BY position ORDER BY n DESC",
        conn)
    print("\n--- Noder per position ---")
    print(df.to_string(index=False))


def plot_nodes_per_position(conn):
    df = pd.read_sql_query(
        "SELECT position, COUNT(*) AS n FROM nodes GROUP BY position",
        conn)
    df = df.sort_values("n", ascending=False)

    plt.figure()
    plt.bar(df["position"], df["n"])
    plt.title("Antal noder per position")
    plt.xlabel("Position")
    plt.ylabel("Noder")
    plt.tight_layout()
    plt.show()


def plot_action_pie(conn):
    df = pd.read_sql_query(
        "SELECT action, SUM(frequency) AS freq FROM ranges GROUP BY action",
        conn)

    plt.figure()
    plt.pie(df["freq"], labels=df["action"], autopct="%1.1f%%")
    plt.title("Total action-frekvens i hela databasen")
    plt.tight_layout()
    plt.show()


def heatmap_for_node(conn, node_id: int):
    df = pd.read_sql_query(
        "SELECT combo, action, frequency FROM ranges WHERE node_id = ?",
        conn, params=(node_id,))

    if df.empty:
        print(f"Ingen data för node {node_id}")
        return

    pivot = (df.pivot(index="combo", columns="action", values="frequency")
               .fillna(0)
               .sort_index())

    plt.figure(figsize=(10, 12))
    plt.imshow(pivot, aspect="auto", interpolation="nearest")
    plt.colorbar(label="Frekvens")
    plt.xticks(range(len(pivot.columns)), pivot.columns)
    plt.yticks(range(len(pivot.index)), pivot.index, fontsize=6)
    plt.title(f"Combo × Action heat-map (node {node_id})")
    plt.tight_layout()
    plt.show()


# ------------------------------------------------------------
#  HUVUDPROGRAM
# ------------------------------------------------------------
def main():
    conn = open_db(DB_PATH)

    list_positions(conn)
    plot_nodes_per_position(conn)
    plot_action_pie(conn)

    # Vill du kolla en specifik nod? Avkommentera raden nedan.
    # heatmap_for_node(conn, 1)   # ersätt 1 med rätt node_id

    conn.close()


if __name__ == "__main__":
    main()
