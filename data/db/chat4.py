# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
poker_assistant.py
------------------
Command-line-assistent som svarar på *pre-flop-frågor* via `poker_ranges.db`.

Nyheter i denna version
-----------------------
• Fångar fler uttryck: *raises, raised, 3-bet, limp, open…*
• Tillåter **raise utan belopp**  → kodas som »R« (generisk size).
• Fuzzy-sök: noder där actionsekvensen innehåller valfri raise hittas med
  LIKE även om databasen lagrar "R2.5", "R3" osv.
• Kortare fallback-frågor om hand/position saknas.
• Skyddar procentsiffrorna från att ändras av GPT-polish.
• Stöder kortalias f/c/x/k och kan returnera upp till 2500 tokens.

Krav
----
    pip install openai pandas
    (sätt env-variabeln OPENAI_API_KEY)
"""

from __future__ import annotations
import os, re, sys, time, sqlite3, json
from pathlib import Path
from typing import Iterable, Sequence

import openai, pandas as pd

# --------------------------------------------------------------------------- #
#  CONFIG                                                                     #
# --------------------------------------------------------------------------- #
ROOT_DIR   = Path(__file__).resolve().parent
DB_PATH    = ROOT_DIR / "poker_ranges.db"
LOG_FILE   = ROOT_DIR / "assistant_log.txt"
MAX_TOKENS = 2500                          # ← 10× tidigare värde

ACTION_CODE = {"fold": "f", "call": "c", "check": "x"}

# alias → kanoniskt action-ord
ACTION_ALIAS = {
    "fold":  "fold",  "folds":  "fold",  "muck":  "fold",
    "call":  "call",  "calls":  "call",  "flat":  "call",
    "check": "check", "checks": "check",
    "limp":  "call",  "open":   "raise", "opens": "raise",
    "raise": "raise", "raises": "raise", "raised": "raise",
    "3bet":  "raise", "3-bet":  "raise", "4bet":  "raise", "4-bet": "raise",

    # --- nya kortalias ------------------------------------------------------
    "f": "fold",
    "c": "call",
    "x": "check",
    "k": "check",
}

# matchar "raise", "raises", "3-bet" osv, med eller utan siffra
RAISE_RE = re.compile(
    r"\b(?:3[ -]?bet|4[ -]?bet|raise[sd]?|open[sd]?)\b(?:\s*([\d.]+))?",
    re.I,
)

SUITS = ["c", "d", "h", "s"]

COMBO_RE = re.compile(r"\b([2-9TJQKA][cdhs]\s*[2-9TJQKA][cdhs])\b", re.I)
HAND_RE  = re.compile(r"\b([2-9TJQKA]{2}[so]?|([2-9TJQKA])\2)\b", re.I)
POS_RE   = re.compile(
    r"\b(utg|hj|co|btn|sb|bb|low ?jack|hijack|cutoff|button|small blind|big blind)\b",
    re.I,
)

SYSTEM_MSG = (
    "You are a concise poker expert. "
    "Insert the EXACT 'Actions:' block you receive; do not edit its numbers."
)

# --------------------------------------------------------------------------- #
#  DATABASE HELPERS                                                           #
# --------------------------------------------------------------------------- #
def db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        sys.exit(f"Database not found: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


def canonize_pos(conn: sqlite3.Connection, raw: str | None) -> str | None:
    """Map any alias to its canonical position (table position_alias)."""
    if raw is None:
        return None
    row = conn.execute(
        """
        SELECT canonical
        FROM position_alias
        WHERE REPLACE(UPPER(alias),' ','') = REPLACE(UPPER(?),' ','')
        """,
        (raw,),
    ).fetchone()
    return row[0] if row else raw.upper()


def node_id_for(pos: str, seq: str, conn: sqlite3.Connection) -> int | None:
    """
    Om sekvensen innehåller en generisk 'R' utan tal, leta efter den första
    noden vars action_sequence matchar med valfri raise-storlek.
    """
    if "R" in seq and not re.search(r"R\d", seq):
        like = seq.replace("R", "R%")          # 'PF:F-R' ⇒ 'PF:F-R%'
        row = conn.execute(
            "SELECT id FROM nodes "
            "WHERE position = ? AND action_sequence LIKE ? "
            "ORDER BY id LIMIT 1",
            (pos, like),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM nodes "
            "WHERE position = ? AND action_sequence = ?",
            (pos, seq),
        ).fetchone()
    return row[0] if row else None


# --------------------------------------------------------------------------- #
#  PARSERS                                                                    #
# --------------------------------------------------------------------------- #
def parse_actions(text: str) -> Sequence[str]:
    """Returnera kanoniska tokens: fold, call, check, raise <size?>"""
    acts: list[str] = []
    tokens = text.lower().replace(",", " ").replace("-", " ").replace(";", " ").replace("after", " ").split()
    i = 0
    while i < len(tokens):
        t = tokens[i].strip(" \"'""''")
        # Kolla om token är en känd action
        canon = ACTION_ALIAS.get(t)
        if canon:
            acts.append(canon)
            i += 1
            continue
        # Kolla om det är en raise med siffra direkt efter
        if t in {"raise", "raises", "raised", "open", "opens", "3bet", "3-bet", "4bet", "4-bet"}:
            # Kolla om nästa token är en siffra
            if i + 1 < len(tokens):
                try:
                    size = float(tokens[i+1].replace(",", "."))
                    acts.append(f"raise {size}")
                    i += 2
                    continue
                except ValueError:
                    pass
            acts.append("raise")
            i += 1
            continue
        i += 1
    return acts


def encode_action_sequence(actions: Iterable[str]) -> str:
    enc: list[str] = []
    for act in actions:
        if act in ACTION_CODE:                       # fold / call / check
            enc.append(ACTION_CODE[act].upper())
        elif act.startswith("raise"):
            bits = act.split()
            if len(bits) == 2:                       # raise 2.5
                enc.append(f"R{float(bits[1])}")
            else:                                    # bara 'raise'
                enc.append("R")                      # generisk raise
    return "PF:" + "-".join(enc) if enc else "PF:"


def combos_for_hand(code: str) -> list[str]:
    code = code.lower().replace(" ", "")

    # exakt combo, t.ex. 6d5s
    if len(code) == 4 and code[1] in "cdhs" and code[3] in "cdhs":
        r1, s1, r2, s2 = code[0], code[1], code[2], code[3]
        return [f"{r1.upper()}{s1}{r2.upper()}{s2}"]

    code = code.upper()
    if len(code) == 2:  # par eller odef. suited/off
        a, b = code
        if a == b:      # pocket par
            return [
                f"{a}{s1}{b}{s2}"
                for i, s1 in enumerate(SUITS)
                for s2 in SUITS[i + 1 :]
            ]
        suited  = [f"{a}{s}{b}{s}" for s in SUITS]
        offsuit = [
            f"{a}{s1}{b}{s2}"
            for s1 in SUITS
            for s2 in SUITS
            if s1 != s2
        ]
        return suited + offsuit

    if len(code) == 3:  # AKs / AKo
        a, b, flag = code
        if flag == "S":
            return [f"{a}{s}{b}{s}" for s in SUITS]
        return [
            f"{a}{s1}{b}{s2}"
            for s1 in SUITS
            for s2 in SUITS
            if s1 != s2
        ]
    return []


# --------------------------------------------------------------------------- #
#  RANGE LOOK-UP                                                              #
# --------------------------------------------------------------------------- #
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


def summarise(df: pd.DataFrame) -> str:
    """Returnera blocket 'Actions:' med alla actions + medelfrekvens."""
    if df.empty:
        return "No data for that hand in the database."

    pivot = (
        df.pivot_table(index="action",
                       values="frequency",
                       aggfunc="mean")
          .sort_values("frequency", ascending=False)
    )
    lines = [f"{a.upper():<4}: {f*100:.1f} %" for a, f in pivot["frequency"].items()]
    return "Actions:\n  " + "\n  ".join(lines)


# --------------------------------------------------------------------------- #
#  LOGGING                                                                    #
# --------------------------------------------------------------------------- #
def log(user_q: str, answer: str) -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f.write(f"USER: {user_q}\nAI  : {answer}\n{'-'*80}\n")


# --------------------------------------------------------------------------- #
#  MAIN LOOP                                                                  #
# --------------------------------------------------------------------------- #
def gpt_parse_question(question: str) -> dict | None:
    """Använd GPT för att tolka fråga och returnera dict med hand, position, actions."""
    prompt = (
        "Extrahera hand, position och action-sekvens ur denna fråga. "
        "Action-sekvensen ska vara en lista av actions (t.ex. ['fold', 'call', 'raise 2.5']). "
        "Om det står 'after first person folds', ska actions vara ['fold']. "
        "Om det står 'after fold, fold', ska actions vara ['fold', 'fold']. "
        "Om det står 'after limp', ska actions vara ['call']. "
        "Returnera som JSON: {\"hand\": ..., \"position\": ..., \"actions\": [...]}. "
        "Om något saknas, använd null.\n\n"
        "Exempel: 'What should I do with AKs on CO after fold, fold?' → actions: ['fold', 'fold']\n"
        "Exempel: 'What should I do with QQ on BTN after limp?' → actions: ['call']\n"
        "Exempel: 'What should I do with 6d5s UTG?' → actions: []\n"
        "Fråga: " + question
    )
    try:
        rsp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Du är en pokerexpert och returnerar alltid endast JSON, aldrig förklaringar."},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=200,
            temperature=0.0,
        )
        content = rsp.choices[0].message["content"].strip()
        # Försök hitta JSON i svaret
        start = content.find('{')
        end = content.rfind('}')+1
        if start != -1 and end != -1:
            return json.loads(content[start:end])
    except Exception as exc:
        pass
    return None


def main() -> None:
    if "OPENAI_API_KEY" not in os.environ:
        sys.exit("Set the OPENAI_API_KEY environment variable first.")
    openai.api_key = os.environ["OPENAI_API_KEY"]

    conn = db()
    print("\nPoker Range Assistant – type 'exit' to quit\n")

    while True:
        q = input("Question: ").strip()
        if q.lower() in {"exit", "quit"}:
            break

        # --- NYTT: Försök tolka med GPT först ---
        parsed = gpt_parse_question(q)
        print("GPT tolkningsresultat:", parsed)  # DEBUG
        if parsed:
            actions = parsed.get("actions") or []
            seq     = encode_action_sequence(actions)
            pos_can = canonize_pos(conn, parsed.get("position"))
            hand_code = parsed.get("hand")
        else:
            # Fallback till gamla parsern
            actions = parse_actions(q)
            seq     = encode_action_sequence(actions)
            pos_raw = POS_RE.search(q)
            pos_can = canonize_pos(conn, pos_raw.group(0) if pos_raw else None)
            if (m := COMBO_RE.search(q)):
                hand_code = m.group(1).replace(" ", "")
            else:
                m = HAND_RE.search(q)
                hand_code = m.group(1).upper() if m else None

        # ------------------------------------------------------------------ #
        #  DATABASE LOOKUP                                                   #
        # ------------------------------------------------------------------ #
        if not hand_code or not pos_can:
            draft = ("Could not detect both hand and position. "
                     "Example: 'AKs CO after fold, fold' or '6d5s UTG'.")
        else:
            node = node_id_for(pos_can, seq, conn)
            if node:
                df    = query_ranges(conn, node, combos_for_hand(hand_code))
                draft = summarise(df)
            else:
                draft = f"No node found for {pos_can} after sequence {seq}."

        # ------------------------------------------------------------------ #
        #  GPT POLISH                                                        #
        # ------------------------------------------------------------------ #
        if draft.startswith("Actions:"):
            user_msg = f"Question: {q}\n\n{draft}"
            try:
                rsp = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_MSG},
                        {"role": "user",   "content": user_msg},
                    ],
                    max_tokens=MAX_TOKENS,
                    temperature=0.3,
                )
                final_ans = rsp.choices[0].message["content"].strip()
            except Exception as exc:
                final_ans = f"(OpenAI error: {exc})\n\n{draft}"
        else:
            final_ans = draft

        print("\n" + final_ans + "\n")
        log(q, final_ans)

    conn.close()
    print("Good-bye!")


if __name__ == "__main__":
    main()
