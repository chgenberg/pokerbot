#!/usr/bin/env python3
"""
poker_assistant.py
------------------
AI-assistent som svarar på preflop-frågor genom att slå upp
data i **poker_ranges.db** (lägg den i samma mapp som skriptet).

Krav
-----
pip install openai pandas
export OPENAI_API_KEY="din-nyckel"
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


# ---------------------------------------------------------------------------
#  KONFIGURATION
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent          # samma mapp som .py
DB_PATH  = ROOT_DIR / "poker_ranges.db"
LOG_FILE = ROOT_DIR / "assistant_log.txt"

ACTION_CODE = {"fold": "f", "call": "c", "check": "x"}
RAISE_RE    = re.compile(r"raise\s*([\d.]+)", re.I)

SUITS = ["c", "d", "h", "s"]


# ---------------------------------------------------------------------------
#  DB-HANTERING
# ---------------------------------------------------------------------------
def db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        sys.exit(f"❌ Databasen saknas: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


def canonize_pos(conn: sqlite3.Connection, raw: str | None) -> str | None:
    """'low jack' → 'UTG'   (alias‐tabellen)"""
    if raw is None:
        return None
    row = conn.execute(
        """
        SELECT canonical
        FROM position_alias
        WHERE REPLACE(UPPER(alias),' ','') = REPLACE(UPPER(?),' ','')
        """,
        (raw,)
    ).fetchone()
    return row[0] if row else raw.upper()


def node_id_for(pos: str, seq: str, conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM nodes WHERE position = ? AND action_sequence = ?",
        (pos, seq)
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
#  PARSERS
# ---------------------------------------------------------------------------
def parse_actions(txt: str) -> Sequence[str]:
    """'fold, fold' → ['fold', 'fold']   |   'raise to 2.5'"""
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
                enc.append(f"R{float(m.group(1))}")
    return "PF:" + "-".join(enc) if enc else "PF:"


# matchar exakta kombos (6d5s) samt handkoder (65s, AKo, AA)
COMBO_RE = re.compile(r"\b([2-9TJQKA][cdhs]\s*[2-9TJQKA][cdhs])\b", re.I)
HAND_RE  = re.compile(r"\b([2-9TJQKA]{2}[so]?|([2-9TJQKA])\2)\b", re.I)


def combos_for_hand(code: str) -> list[str]:
    """
    '6d5s' → exakt en kombo
    '65s'  → 4 suited kombos
    '65o'  → 12 offsuit kombos
    '65'   → 16 kombos (4s + 12o)
    'AA'   → 6 par-kombos
    """
    code = code.lower().replace(" ", "")

    # exakt kombo, t.ex. 6d5s, askh
    if len(code) == 4 and code[1] in "cdhs" and code[3] in "cdhs":
        r1, s1, r2, s2 = code[0], code[1], code[2], code[3]
        return [f"{r1.upper()}{s1}{r2.upper()}{s2}"]

    code = code.upper()
    if len(code) == 2:                # par eller ospecificerat suited/off
        a, b = code
        if a == b:                    # par: 6 kombos
            return [f"{a}{s1}{b}{s2}"
                    for i, s1 in enumerate(SUITS) for s2 in SUITS[i+1:]]
        # 16 kombos: 4 suited + 12 offsuit
        suited  = [f"{a}{s}{b}{s}" for s in SUITS]
        offsuit = [f"{a}{s1}{b}{s2}"
                   for s1 in SUITS for s2 in SUITS if s1 != s2]
        return suited + offsuit

    if len(code) == 3:                # AKs / AKo
        a, b, flag = code
        if flag == "S":
            return [f"{a}{s}{b}{s}" for s in SUITS]
        return [f"{a}{s1}{b}{s2}"
                for s1 in SUITS for s2 in SUITS if s1 != s2]

    return []


# ---------------------------------------------------------------------------
#  STRATEGI-UPPSLAG
# ---------------------------------------------------------------------------
def query_ranges(conn: sqlite3.Connection, node_id: int,
                 combos: list[str]) -> pd.DataFrame:
    if not combos:
        return pd.DataFrame(columns=["action", "combo", "frequency"])
    qs = ",".join("?" * len(combos))
    return pd.read_sql_query(
        f"""
        SELECT action, combo, frequency
        FROM ranges
        WHERE node_id = ? AND combo IN ({qs})
        """,
        conn,
        params=[node_id, *combos],
    )


def recommend(df: pd.DataFrame) -> str:
    if df.empty:
        return "⚠️ Ingen data för just den handen i databasen."
    pivot = (df.pivot_table(index="action", values="frequency", aggfunc="mean")
               .sort_values("frequency", ascending=False))
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
    print("\n🃏 Poker Range Assistant – skriv 'exit' för att stänga 🃏\n")

    while True:
        q = input("Fråga: ").strip()
        if q.lower() in {"exit", "quit"}:
            break

        # -------- tolka fråga ------------
        actions = parse_actions(q)
        seq     = encode_action_sequence(actions)

        pos_raw = re.search(
            r"\b(utg|hj|co|btn|sb|bb|low ?jack|hijack|cutoff|button|small blind|big blind)\b",
            q, re.I)
        pos_can = canonize_pos(conn, pos_raw.group(0) if pos_raw else None)

        if m := COMBO_RE.search(q):
            hand_code = m.group(1).replace(" ", "")
        else:
            m = HAND_RE.search(q)
            hand_code = m.group(1).upper() if m else None

        # -------- DB-uppslag -------------
        if hand_code and pos_can:
            node = node_id_for(pos_can, seq, conn)
            if node:
                df   = query_ranges(conn, node, combos_for_hand(hand_code))
                info = recommend(df)
            else:
                info = f"🔍 Hittar ingen nod för {pos_can} efter {seq}."
        else:
            info = ("Kunde inte förstå position / hand. "
                    "Ex: '6d5s utg', '65s CO after fold, fold'.")

        # -------- GPT-polish -------------
        try:
            rsp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content":
                     "Du är en koncis pokerekspert. Svara på svenska."},
                    {"role": "user",   "content": f"Fråga: {q}\n\n{info}"}
                ],
                max_tokens=300,
                temperature=0.4,
            )
            gpt_ans = rsp.choices[0].message["content"].strip()
        except Exception as e:
            gpt_ans = f"(API-fel: {e})\n\n{info}"

        print("\n" + gpt_ans + "\n")
        log(q, gpt_ans)

    conn.close()
    print("Avslutar …")


if __name__ == "__main__":
    main()
