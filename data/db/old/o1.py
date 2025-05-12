#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
poker_chat.py – terminal-chat som kopplar OpenAI-modellen “o1” mot SQLite-
databasen poker_ranges.db och hämtar exakta solver-frekvenser automatiskt.

• Modellen flaggar behov av data med ett JSON-objekt + raden NEED_SOLVERDATA
• Skriptet tolkar objektet, gör SQL-slag, summerar/medelvärdesberäknar och
  skriver ut resultatet – sedan fortsätter konversationen sömlöst.

Kör:
    setx OPENAI_API_KEY "din-nyckel"   (en gång i PowerShell/CMD)
    python poker_chat.py
Avsluta med  quit  eller  exit.
"""

import os
import time
import json
import sqlite3
from pathlib import Path

import openai
from openai.error import Timeout, OpenAIError

# ──────────────────────────────────────────────────────────────────────────────
#  KONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────
MODEL_NAME  = "o1"             # byt modellnamn vid behov
TIMEOUT     = 12               # sek för API-anrop
DB_PATH     = Path("poker_ranges.db")   # måste ligga i samma mapp
FLAG        = "NEED_SOLVERDATA"         # exakt rad från modellen

# ──────────────────────────────────────────────────────────────────────────────
#  OPENAI-nyckel
# ──────────────────────────────────────────────────────────────────────────────
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise EnvironmentError("Miljövariabeln OPENAI_API_KEY saknas.")

# ──────────────────────────────────────────────────────────────────────────────
#  SYSTEM-PROMPT (tvingar modellen att ge strukturerad begäran)
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_MSG = {
    "role": "system",
    "content": (
        "Du är en poker-GTO-assistent. När du behöver exakta solver-siffror "
        "ger du först en kort generell förklaring. Därefter – på en EGEN rad – "
        "skriver du ett JSON-objekt med fälten position, action_sequence, hand "
        "och action (t.ex. 'r', 'c', 'f'). Rad två = NEED_SOLVERDATA.\n"
        "Exempel:\n"
        "{\"position\":\"UTG\",\"action_sequence\":\"PF:R2.5\",\"hand\":\"ATs\","
        "\"action\":\"r\"}\n"
        "NEED_SOLVERDATA"
    ),
}

# ──────────────────────────────────────────────────────────────────────────────
#  HJÄLP: Tidsstämpel
# ──────────────────────────────────────────────────────────────────────────────
def ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

# ──────────────────────────────────────────────────────────────────────────────
#  Hand-expansion: “ATs” ⇒ [AcTc, AdTd, AhTh, AsTs]  |  “QQ” ⇒ sex kombos
# ──────────────────────────────────────────────────────────────────────────────
SUITS = ["c", "d", "h", "s"]

def expand_hand(hand: str) -> list[str]:
    hand = hand.strip().upper()
    # pocket pair (ex. QQ)
    if len(hand) == 2 and hand[0] == hand[1]:
        r = hand[0]
        return [f"{r}{s1}{r}{s2}"
                for i, s1 in enumerate(SUITS)
                for s2 in SUITS[i+1:]]
    # offsuit / suited (ex. AKo, ATs)
    if len(hand) == 3:
        r1, r2, typ = hand[0], hand[1], hand[2]
        if typ == "S":                      # suited
            return [f"{r1}{s}{r2}{s}" for s in SUITS]
        if typ == "O":                      # off-suit
            return [f"{r1}{s1}{r2}{s2}"
                    for s1 in SUITS for s2 in SUITS if s1 != s2]
    # redan en exakt kombo (ex. AcKd)
    return [hand]

# ──────────────────────────────────────────────────────────────────────────────
#  Databas-uppslag  (med enkel fallback för sekvens)
# ──────────────────────────────────────────────────────────────────────────────
def fetch_freq(db: Path, pos: str, seq: str, hand: str, action: str):
    """
    Returnerar (total_frekvens, antal_kombos) eller (None, 0) om ingen träff.
    • position och alias matchas via tabellen position_alias
    • seq måste finnas exakt; fallback: om seq == 'PF' och action == 'r' →
      första raise-nod 'PF:R%' för samma position.
    • hand expanderas automatiskt (ATs → fyra kombos).
    """
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # → canonical position
        cur.execute("SELECT canonical FROM position_alias "
                    "WHERE UPPER(alias)=UPPER(?)", (pos,))
        row = cur.fetchone()
        if not row:
            return None, 0
        canonical = row["canonical"]

        # → node
        cur.execute("SELECT id FROM nodes "
                    "WHERE position=? AND action_sequence=?", (canonical, seq))
        row = cur.fetchone()
        if not row:
            if seq.upper() == "PF" and action.lower() == "r":
                cur.execute("""SELECT id FROM nodes
                               WHERE position=? AND action_sequence LIKE 'PF:R%'
                               ORDER BY LENGTH(action_sequence) LIMIT 1""",
                            (canonical,))
                row = cur.fetchone()
        if not row:
            return None, 0
        node_id = row["id"]

        # → combos och fråga ranges-tabellen
        combos = expand_hand(hand)
        placeholders = ",".join("?" * len(combos))
        sql = f"""SELECT SUM(frequency) AS freq, COUNT(*) AS n
                  FROM ranges
                  WHERE node_id=? AND action=? AND combo IN ({placeholders})"""
        cur.execute(sql, (node_id, action.lower(), *combos))
        row = cur.fetchone()
        if not row or row["n"] == 0:
            return None, 0
        return row["freq"], row["n"]

# ──────────────────────────────────────────────────────────────────────────────
#  Tolka modellens JSON + hämta/svara solver-data
# ──────────────────────────────────────────────────────────────────────────────
def handle_solverdata(json_line: str) -> str:
    try:
        data = json.loads(json_line)
        freq, n = fetch_freq(DB_PATH, data["position"],
                             data["action_sequence"], data["hand"], data["action"])
        if freq is None:
            return (f"Ingen rad hittades för {data['hand']} "
                    f"({data['action_sequence']} → {data['position']}).")
        avg = freq / n if n else 0
        return (f"{data['hand']} ({data['position']}, {data['action_sequence']}) – "
                f"total frekvens {freq:.3f} över {n} kombos "
                f"(≈ {avg:.3f} per combo) för action '{data['action']}'.")
    except Exception as e:
        return f"Kunde inte tolka solver-objektet ({e})."

# ──────────────────────────────────────────────────────────────────────────────
#  Chat-loop
# ──────────────────────────────────────────────────────────────────────────────
def chat_loop():
    print(">> Poker-chatbot klar – skriv frågan (quit/exit avslutar)\n")
    messages = [SYSTEM_MSG]

    while True:
        try:
            user_input = input("Du: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAvslutar…")
            break
        if user_input.lower() in {"quit", "exit"}:
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            start = time.time()
            print(f"[{ts()}] Skickar…")
            resp = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=messages,
                timeout=TIMEOUT,
            )
            assistant_text = resp.choices[0].message["content"].rstrip()
            end = time.time()

            # eventuell JSON + FLAG?
            lines = assistant_text.splitlines()
            if lines and lines[-1].strip() == FLAG:
                json_line = lines[-2].strip() if len(lines) >= 2 else ""
                answer    = "\n".join(lines[:-2]).strip()

                print(f"[{ts()}] Svar (t={end - start:.2f}s):\n{answer}\n")
                solver_reply = handle_solverdata(json_line)
                print(solver_reply + "\n")

                messages.append({"role": "assistant",
                                 "content": answer + "\n" + solver_reply})
            else:
                print(f"[{ts()}] Svar (t={end - start:.2f}s):\n{assistant_text}\n")
                messages.append({"role": "assistant", "content": assistant_text})

        except Timeout:
            print("⏱️  Timeout från OpenAI.\n")
        except OpenAIError as e:
            print(f"OpenAI-fel: {e}\n")

# ──────────────────────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Databasen hittades inte: {DB_PATH}")
    chat_loop()
