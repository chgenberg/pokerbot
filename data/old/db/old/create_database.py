import os
import sqlite3
import json
from datetime import datetime

# Skapa databasmapp om den inte existerar
db_dir = r"C:\Users\Propietario\Desktop\data\db"
os.makedirs(db_dir, exist_ok=True)

# Databasfil
db_path = os.path.join(db_dir, "poker_strategy.db")

# Skapa anslutning till databasen
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Skapa tabeller
cursor.executescript('''
-- Skapa tabeller
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY,
    action_type TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY,
    situation TEXT NOT NULL,
    position_id INTEGER REFERENCES positions(id),
    parent_id INTEGER REFERENCES nodes(id),
    node_path TEXT UNIQUE NOT NULL,
    UNIQUE(situation, position_id)
);

CREATE TABLE IF NOT EXISTS hands (
    id INTEGER PRIMARY KEY,
    hand_code TEXT NOT NULL,
    canonical_code TEXT NOT NULL UNIQUE,
    first_rank TEXT NOT NULL,
    first_suit TEXT NOT NULL,
    second_rank TEXT NOT NULL,
    second_suit TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY,
    node_id INTEGER REFERENCES nodes(id),
    hand_id INTEGER REFERENCES hands(id),
    action_type_id INTEGER REFERENCES actions(id),
    action_code TEXT NOT NULL,
    raise_amount REAL NULL,
    frequency REAL NOT NULL CHECK (frequency >= 0 AND frequency <= 1),
    UNIQUE(node_id, hand_id, action_code)
);

-- Skapa index
CREATE INDEX IF NOT EXISTS idx_nodes_situation ON nodes(situation);
CREATE INDEX IF NOT EXISTS idx_nodes_position ON nodes(position_id);
CREATE INDEX IF NOT EXISTS idx_hands_canonical ON hands(canonical_code);
CREATE INDEX IF NOT EXISTS idx_strategies_node ON strategies(node_id);
CREATE INDEX IF NOT EXISTS idx_strategies_hand ON strategies(hand_id);
CREATE INDEX IF NOT EXISTS idx_strategies_combined ON strategies(node_id, hand_id);
''')

# Fyll på positions-tabellen
positions = [('utg',), ('hj',), ('co',), ('btn',), ('sb',), ('bb',)]
cursor.executemany("INSERT OR IGNORE INTO positions (name) VALUES (?)", positions)

# Fyll på actions-tabellen
actions = [('fold',), ('call',), ('check',), ('raise',)]
cursor.executemany("INSERT OR IGNORE INTO actions (action_type) VALUES (?)", actions)

# Funktion för att extrahera raise-belopp från aktion-kod
def parse_raise_amount(action_code):
    if action_code.startswith('r'):
        try:
            # Extrahera nummer efter 'r' och dela med 10
            return float(action_code[1:]) / 10.0
        except ValueError:
            return None
    return None

# Commit ändringar
conn.commit()

# Skapa beskrivningsfil
description = f'''
DATABASBESKRIVNING - POKER STRATEGY DATABASE
Skapad: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Sökväg: {db_path}

TABELLSTRUKTUR:
===============

1. positions
   - id: Unikt ID för position
   - name: Positionsnamn (utg, hj, co, btn, sb, bb)

2. actions
   - id: Unikt ID för aktionstyp
   - action_type: Typ av aktion (fold, call, check, raise)

3. nodes
   - id: Unikt ID för beslutspunkt i spelträdet
   - situation: String som beskriver tidigare aktioner
   - position_id: ID för spelaren som ska agera
   - parent_id: ID för föräldranod (NULL för rot)
   - node_path: Faktisk sökväg i mappstrukturen

4. hands
   - id: Unikt ID för pokerhanden
   - hand_code: Original handkod (t.ex. "8s7d")
   - canonical_code: Normaliserad handkod
   - first_rank, first_suit: Första kortets värde och färg
   - second_rank, second_suit: Andra kortets värde och färg

5. strategies
   - id: Unikt ID för strategi
   - node_id: Beslutspunkt
   - hand_id: Hand
   - action_type_id: Typ av aktion
   - action_code: Original aktionskod (t.ex. "r25")
   - raise_amount: Extraherat raise-belopp om aktion är raise
   - frequency: Frekvens (0-1) för denna strategi

INDEXERING:
===========
- idx_nodes_situation: Index på nodes.situation
- idx_nodes_position: Index på nodes.position_id
- idx_hands_canonical: Index på hands.canonical_code
- idx_strategies_node: Index på strategies.node_id
- idx_strategies_hand: Index på strategies.hand_id
- idx_strategies_combined: Index på (node_id, hand_id)

DATAFLÖDE:
==========
1. Mappnamn (t.ex. "ffr25fr160_btn") parsas till situation ("ffr25fr160") och position ("btn").
2. Noden registreras i databasen med koppling till föräldranoden.
3. För varje aktion i all_expanded.json:
   - Aktionskod och typ extraheras.
   - För varje hand och dess frekvens:
     - Handen normaliseras och sparas.
     - Strategin sparas med koppling till nod, hand och aktion.

EXEMPELFRÅGOR:
==============
-- Hitta optimala händer för 3-bet från CO mot UTG
SELECT h.canonical_code, s.frequency, s.raise_amount
FROM strategies s
JOIN hands h ON s.hand_id = h.id
JOIN nodes n ON s.node_id = n.id
JOIN actions a ON s.action_type_id = a.id
WHERE n.situation = 'r25' 
AND n.position_id = (SELECT id FROM positions WHERE name = 'co')
AND a.action_type = 'raise'
ORDER BY s.frequency DESC
LIMIT 20;

-- Hitta alla händer som alltid foldas i en specifik situation
SELECT h.canonical_code
FROM strategies s
JOIN hands h ON s.hand_id = h.id
JOIN nodes n ON s.node_id = n.id
JOIN actions a ON s.action_type_id = a.id
WHERE n.situation = 'r25fr90' 
AND n.position_id = (SELECT id FROM positions WHERE name = 'bb')
AND a.action_type = 'fold'
AND s.frequency = 1.0;
'''

# Spara beskrivningen till en fil
with open(os.path.join(db_dir, "databas_beskrivning.txt"), "w", encoding="utf-8") as f:
    f.write(description)

# Stäng anslutningen
conn.close()

print(f"Databas skapad: {db_path}")
print(f"Beskrivningsfil skapad: {os.path.join(db_dir, 'databas_beskrivning.txt')}") 