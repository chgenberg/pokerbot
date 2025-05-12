#!/usr/bin/env python3
"""
poker_assistant.py
------------------
En AI-assistent för pokerstrategi som använder OpenAI API och 
kopplar samman med poker_strategy.db databasen.

Användning:
    python poker_assistant.py

Kräver:
    pip install openai
    Miljövariabeln OPENAI_API_KEY måste vara satt.
"""

import os
import sys
import sqlite3
import openai
import time
from pathlib import Path

# --- Konfiguration --------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "poker_strategy.db"
LOG_FILE = SCRIPT_DIR / "ai_assistant_log.txt"
# --------------------------------------------------------------------------

def get_db_connection():
    """Ansluter till databasen"""
    if not DB_PATH.exists():
        print(f"❌ Databas hittades inte: {DB_PATH}")
        sys.exit(1)
        
    return sqlite3.connect(DB_PATH)

def get_table_info(conn):
    """Hämtar information om databastabeller"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    table_info = {}
    for table in tables:
        cursor.execute(f"PRAGMA table_info('{table}')")
        columns = [row[1] for row in cursor.fetchall()]
        table_info[table] = columns
        
    return table_info

def query_database(conn, query):
    """Kör en SQL-fråga mot databasen"""
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        if cursor.description:
            column_names = [desc[0] for desc in cursor.description]
            return {"columns": column_names, "data": results}
        return {"columns": [], "data": results}
    except sqlite3.Error as e:
        return {"error": str(e)}

def format_query_results(results):
    """Formaterar databasresultat till text"""
    if "error" in results:
        return f"Databasfel: {results['error']}"
    
    if not results["data"]:
        return "Inga resultat hittades."
    
    text = []
    # Columner
    text.append(" | ".join(results["columns"]))
    text.append("-" * len(text[0]))
    
    # Data
    for row in results["data"]:
        text.append(" | ".join(str(value) for value in row))
    
    return "\n".join(text)

def get_strategy_for_context(conn, position=None, action=None, hand_type=None):
    """Hämtar relevanta strategier baserat på kontext"""
    conditions = []
    params = []
    
    if position:
        conditions.append("position = ?")
        params.append(position)
    
    if action:
        conditions.append("action = ?")
        params.append(action)
    
    if hand_type:
        conditions.append("hand_type = ?")
        params.append(hand_type)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = f"""
        SELECT position, action, hand_type, strategy_text
        FROM strategy_table
        WHERE {where_clause}
        LIMIT 5
    """
    
    cursor = conn.cursor()
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    if not results:
        return "Ingen specifik strategi hittad för dessa parametrar."
    
    text = []
    for row in results:
        text.append(f"Position: {row[0]}, Action: {row[1]}, Handtyp: {row[2]}")
        text.append(f"Strategi: {row[3]}")
        text.append("-" * 50)
    
    return "\n".join(text)

def log_interaction(user_prompt, ai_response):
    """Loggar interaktionen till fil"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n--- {timestamp} ---\n")
        f.write(f"Användare: {user_prompt}\n")
        f.write(f"AI: {ai_response}\n")
        f.write("-" * 80 + "\n")

def main():
    # Kontrollera att API-nyckeln finns
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ Ställ in miljövariabeln OPENAI_API_KEY.")
        print("   Windows PowerShell:  $env:OPENAI_API_KEY = 'din-nyckel'")
        print("   Windows CMD:         set OPENAI_API_KEY=din-nyckel")
        sys.exit(1)
    
    # Sätt OpenAI API-nyckel (äldre API-format)
    openai.api_key = api_key
    
    # Anslut till databasen
    conn = get_db_connection()
    
    # Hämta databasstruktur för kontext
    table_info = get_table_info(conn)
    db_structure = "\n".join([
        f"Tabell: {table}, Kolumner: {', '.join(columns)}"
        for table, columns in table_info.items()
    ])
    
    print("\n🃏 Poker Strategy Assistant 🃏")
    print("Ställ frågor om pokerstrategier eller be om specifika råd.")
    print("Skriv 'exit' för att avsluta.\n")
    
    # Interaktiv loop
    while True:
        user_input = input("\nFråga: ").strip()
        
        if user_input.lower() in ['exit', 'quit', 'avsluta']:
            print("Avslutar...")
            break
        
        start_time = time.time()
        
        # Förbered system prompt med databaskontext
        system_prompt = f"""
Du är en pokerexpert som ger strategisk rådgivning baserat på databas med pokerstrategi.

Databasen har följande struktur:
{db_structure}

När någon frågar om specifika händer, positioner eller situationer, använd denna kontext 
för att ge precisa svar. Om du inte kan besvara frågan med den tillgängliga informationen, 
förklara varför och föreslå hur användaren kan omformulera sin fråga.

Svara alltid på svenska. Var koncis men tydlig.
"""
        
        # Förbered användarens fråga med extra kontext
        query_context = ""
        
        # Försök identifiera nyckelord i användarens fråga (utöka efter behov)
        position_keywords = ["utg", "hj", "co", "btn", "sb", "bb", "hijack", "cutoff", "button", "small blind", "big blind"]
        action_keywords = ["raise", "call", "fold", "check", "3-bet", "4-bet"]
        hand_types = ["pocket pairs", "suited connectors", "offsuit", "broadway", "premium"]
        
        identified_position = None
        identified_action = None
        identified_hand = None
        
        for keyword in position_keywords:
            if keyword.lower() in user_input.lower():
                identified_position = keyword
                break
                
        for keyword in action_keywords:
            if keyword.lower() in user_input.lower():
                identified_action = keyword
                break
                
        for keyword in hand_types:
            if keyword.lower() in user_input.lower():
                identified_hand = keyword
                break
        
        # Om vi identifierade relevanta parametrar, hämta strategikontext
        if any([identified_position, identified_action, identified_hand]):
            query_context = get_strategy_for_context(
                conn, 
                position=identified_position, 
                action=identified_action,
                hand_type=identified_hand
            )
        
        user_prompt = f"""
{user_input}

Relevant information från databasen:
{query_context}
"""
        
        try:
            # Gör API-anropet med äldre API-format
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=800,
                temperature=0.7,
                request_timeout=10  # Använd request_timeout istället för timeout
            )
            
            elapsed_time = time.time() - start_time
            ai_response = response.choices[0].message['content']  # Observera skillnaden i svarsstrukturen
            
            # Visa svaret
            print(f"\nSvar ({elapsed_time:.2f}s):")
            print(ai_response)
            
            # Logga interaktionen
            log_interaction(user_input, ai_response)
            
        except Exception as e:
            print(f"❌ Fel vid API-anrop: {e}")
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(f"FEL: {str(e)}\n")
    
    # Stäng databasanslutning
    conn.close()

if __name__ == "__main__":
    main()