#!/usr/bin/env python3
"""
poker_assistant.py
------------------
AI-assistent som svarar på frågor om preflop-strategi
genom att slå upp data i SQLite-filen **poker_ranges.db**.

Lägg bara databasen i samma mapp som detta skript,
så hittar den den automatiskt.

Krav
-----
pip install openai pandas tabulate
Miljövariabel:  OPENAI_API_KEY
"""

from __future__ import annotations
import os
import re
import sys
import time
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

import openai
import pandas as pd
from tabulate import tabulate


# ---------------------------------------------------------------------------
#  KONFIGURATION
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent          # ← **samma mapp som .py**
DB_PATH  = ROOT_DIR / "poker_ranges.db"
LOG_FILE = ROOT_DIR / "assistant_log.txt"

POSITION_ORDER = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]  # 6-handed

ACTION_CODE = {"fold": "f", "call": "c", "check": "x"}
RAISE_RE = re.compile(r"raise\s*([\d.]+)", re.I)


# ---------------------------------------------------------------------------
#  DB-HANTERING
# ---------------------------------------------------------------------------
def db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        sys.exit(f"❌ Databasen saknas: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


def canonize_pos(conn: sqlite3.Connection, raw: str | None) -> str | None:
    """’low jack’ → ’UTG’,  None → None"""
    if raw is None:
        return None
    cur = conn.execute(
        "SELECT canonical FROM position_alias "
        "WHERE REPLACE(UPPER(alias), ' ', '') = REPLACE(UPPER(?), ' ', '')",
        (raw,),
    ).fetchone()
    return cur[0] if cur else raw.upper()


def node_id_for(pos: str, seq: str, conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM nodes WHERE position = ? AND action_sequence = ?",
        (pos, seq),
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
#  PARSERS
# ---------------------------------------------------------------------------
def parse_actions(txt: str) -> Sequence[str]:
    """Ex. 'fold, fold' → ['fold','fold']"""
    acts: list[str] = []
    for part in re.split(r"[,\-;]|after", txt.lower()):
        part = part.strip()
        if not part:
            continue
        if any(w in part for w in ("fold", "call", "check")):
            acts.append(part.split()[0])
        else:
            m = RAISE_RE.search(part)
            if m:
                acts.append(f"raise {m.group(1)}")
    return acts


def encode_action_sequence(actions: Iterable[str]) -> str:
    enc = []
    for a in actions:
        a = a.lower()
        if a in ACTION_CODE:
            enc.append(ACTION_CODE[a].upper())
        else:
            m = RAISE_RE.match(a)
            if m:
                amt = float(m.group(1))
                enc.append(f"R{amt}")
    return "PF:" + "-".join(enc) if enc else "PF:"


SUITS = ["c", "d", "h", "s"]


def combos_for_hand(code: str) -> list[str]:
    """’AKs’ → lista med exakta kombos."""
    code = code.upper()
    if len(code) == 2:  # par
        r = code[0]
        return [f"{r}{SUITS[i]}{r}{SUITS[j]}"
                for i in range(4) for j in range(i + 1, 4)]
    if len(code) == 3:
        a, b, flag = code
        if flag == "S":  # suited
            return [f"{a}{s}{b}{s}" for s in SUITS]
        return [f"{a}{s1}{b}{s2}"
                for s1 in SUITS for s2 in SUITS if s1 != s2]
    return []


# ---------------------------------------------------------------------------
#  STRATEGI-UPPSLAG
# ---------------------------------------------------------------------------
def query_ranges(conn: sqlite3.Connection, node_id: int,
                 combos: list[str]) -> pd.DataFrame:
    placeholders = ",".join("?" * len(combos))
    return pd.read_sql_query(
        f"""
        SELECT action, combo, frequency
        FROM ranges
        WHERE node_id = ? AND combo IN ({placeholders})
        """,
        conn,
        params=[node_id, *combos],
    )


def recommend(df: pd.DataFrame) -> str:
    if df.empty:
        return "⚠️ Ingen data för just den handen i databasen."
    pivot = df.pivot_table(index="action", values="frequency",
                           aggfunc="mean").sort_values("frequency",
                                                       ascending=False)
    top = pivot.index[0]
    details = "\n".join(f"{a}: {f*100:.1f} %" for a, f in pivot["frequency"].items())
    return f"Rekommenderad åtgärd: **{top.upper()}**\n\nFrekvenser:\n{details}"


# ---------------------------------------------------------------------------
#  LOGG
# ---------------------------------------------------------------------------
def log(q: str, ans: str) -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"USER: {q}\nAI  : {ans}\n{'-'*80}\n")


# ---------------------------------------------------------------------------
#  HUVUDLOOP
# ---------------------------------------------------------------------------
def main() -> None:
    if "OPENAI_API_KEY" not in os.environ:
        sys.exit("❌ Sätt miljövariabeln OPENAI_API_KEY.")
    openai.api_key = os.environ["OPENAI_API_KEY"]

    conn = db()
    print("\n🃏 Poker Range Assistant  – skriv 'exit' för att stänga 🃏\n")

    while True:
        q = input("Fråga: ").strip()
        if q.lower() in {"exit", "quit"}:
            break

        # ---------- tolka fråga ----------
        actions = parse_actions(q)
        seq     = encode_action_sequence(actions)

        pos_raw = re.search(
            r"\b(utg|hj|co|btn|sb|bb|low ?jack|hijack|cutoff|button|small blind|big blind)\b",
            q, re.I)
        pos_can = canonize_pos(conn, pos_raw.group(0) if pos_raw else None)

        hand_m  = re.search(r"\b([2-9TJQKA]{2}[so]?|([2-9TJQKA])\2)\b", q, re.I)
        hand    = hand_m.group(1).upper() if hand_m else None

        answer  = ""
        if hand and pos_can:
            node = node_id_for(pos_can, seq, conn)
            if node:
                df  = query_ranges(conn, node, combos_for_hand(hand))
                answer = recommend(df)
            else:
                answer = f"🔍 Hittar ingen nod för {pos_can} efter {seq}."
        else:
            answer = ("Kunde inte förstå position / hand. "
                      "Ex: 'AKs on CO after fold, fold'.")

        # ---------- GPT-polish ----------
        try:
            rsp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "Du är en koncis pokerekspert. "
                        "Svara på svenska, kort men tydligt.")},
                    {"role": "user", "content": f"Fråga: {q}\n\n{answer}"}
                ],
                max_tokens=250,
                temperature=0.4,
            )
            gpt_ans = rsp.choices[0].message["content"].strip()
        except Exception as e:
            gpt_ans = f"(API-fel: {e})\n\n{answer}"

        print("\n" + gpt_ans + "\n")
        log(q, gpt_ans)

    conn.close()
    print("Avslutar …")


if __name__ == "__main__":
    main()
