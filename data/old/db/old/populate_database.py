import os
import json
import sqlite3
import re

# Sökväg till databasen
db_path = r"C:\Users\Propietario\Desktop\data\db\poker_strategy.db"

# Sökväg till trädet
tree_path = r"C:\Users\Propietario\Desktop\data\tree"

# Anslut till databasen
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Funktion för att extrahera raise-belopp från aktion-kod
def parse_raise_amount(action_code):
    if action_code.startswith('r'):
        try:
            # Extrahera nummer efter 'r' och dela med 10
            return float(action_code[1:]) / 10.0
        except ValueError:
            return None
    return None

# Funktion för att normalisera handkod
def normalize_hand(hand_code):
    """Normalisera handkod som '8s7d' till kanonisk form."""
    if len(hand_code) != 4:
        return hand_code
    
    # Extrahera rank och suit för varje kort
    rank1, suit1 = hand_code[0], hand_code[1]
    rank2, suit2 = hand_code[2], hand_code[3]
    
    # Rangordning av kort-ranks
    rank_order = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
    
    # Om rank2 är högre än rank1, eller om de är lika och suit2 är alfabetiskt före suit1
    if (rank_order.get(rank2, 0) > rank_order.get(rank1, 0)) or \
       (rank_order.get(rank2, 0) == rank_order.get(rank1, 0) and suit2 < suit1):
        return f"{rank2}{suit2}{rank1}{suit1}"
    
    return hand_code

# Funktion för att spara hand i databasen
def save_hand(hand_code):
    """Spara hand och returnera hand_id."""
    canonical = normalize_hand(hand_code)
    
    # Kolla om handen redan finns
    cursor.execute("SELECT id FROM hands WHERE canonical_code = ?", (canonical,))
    result = cursor.fetchone()
    if result:
        return result[0]
    
    # Extrahera rank och suit för varje kort
    first_rank, first_suit = canonical[0], canonical[1]
    second_rank, second_suit = canonical[2], canonical[3]
    
    # Spara ny hand
    cursor.execute(
        "INSERT INTO hands (hand_code, canonical_code, first_rank, first_suit, second_rank, second_suit) VALUES (?, ?, ?, ?, ?, ?)",
        (hand_code, canonical, first_rank, first_suit, second_rank, second_suit)
    )
    return cursor.lastrowid

# Funktion för att tolka mappnamn
def parse_folder_name(folder_name):
    """Tolka mappnamn som 'ffr25fr160_btn' till situationsträng och position."""
    if folder_name.startswith('_'):  # Rotnoden
        return "", folder_name[1:]
    
    parts = folder_name.split('_')
    if len(parts) == 2:
        return parts[0], parts[1]
    
    return "", ""

# Hämta eller skapa nod
def get_or_create_node(situation, position, node_path, parent_situation=None):
    """Hämta eller skapa nod och returnera node_id."""
    # Hämta position_id
    cursor.execute("SELECT id FROM positions WHERE name = ?", (position,))
    position_id = cursor.fetchone()
    if not position_id:
        print(f"Varning: Position '{position}' hittades inte.")
        return None
    position_id = position_id[0]
    
    # Kolla om noden redan finns
    cursor.execute("SELECT id FROM nodes WHERE situation = ? AND position_id = ?", (situation, position_id))
    result = cursor.fetchone()
    if result:
        return result[0]
    
    # Hitta parent_id om det behövs
    parent_id = None
    if parent_situation is not None:
        cursor.execute("SELECT id FROM nodes WHERE situation = ?", (parent_situation,))
        parent_result = cursor.fetchone()
        if parent_result:
            parent_id = parent_result[0]
    
    # Skapa noden
    cursor.execute(
        "INSERT INTO nodes (situation, position_id, parent_id, node_path) VALUES (?, ?, ?, ?)",
        (situation, position_id, parent_id, node_path)
    )
    return cursor.lastrowid

# Hämta action_type_id baserat på aktionskod
def get_action_type_id(action_code):
    """Hämta action_type_id baserat på aktionskod."""
    action_type = 'fold'
    if action_code.startswith('r'):
        action_type = 'raise'
    elif action_code == 'c':
        action_type = 'call'
    elif action_code == 'x':
        action_type = 'check'
    
    cursor.execute("SELECT id FROM actions WHERE action_type = ?", (action_type,))
    result = cursor.fetchone()
    return result[0] if result else None

# Rekursiv funktion för att besöka varje nod i trädet
def process_tree(root_path, current_path="", parent_situation=None):
    full_path = os.path.join(root_path, current_path)
    
    # Kolla om detta är en nod (mapp)
    if not os.path.isdir(full_path):
        return
    
    # Tolka mappnamnet
    folder_name = os.path.basename(current_path) if current_path else "_utg"
    situation, position = parse_folder_name(folder_name)
    
    # Ignorera om detta inte är en giltig nod
    if not position:
        return
    
    node_path = current_path if current_path else "_utg"
    node_id = get_or_create_node(situation, position, node_path, parent_situation)
    
    if node_id is None:
        print(f"Kunde inte skapa nod för: {folder_name}")
        return
    
    # Sökväg till JSON-filen för strategin
    json_path = os.path.join(full_path, "all_expanded.json")
    
    # Läs in strategin om filen finns
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                strategy_data = json.load(f)
            
            # Bearbeta varje aktion i strategin
            for action_code, hands in strategy_data.items():
                action_type_id = get_action_type_id(action_code)
                raise_amount = parse_raise_amount(action_code)
                
                # Behandla varje hand och dess frekvens
                for hand_code, frequency in hands.items():
                    hand_id = save_hand(hand_code)
                    
                    # Spara strategin
                    cursor.execute(
                        """INSERT OR REPLACE INTO strategies 
                           (node_id, hand_id, action_type_id, action_code, raise_amount, frequency) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (node_id, hand_id, action_type_id, action_code, raise_amount, frequency)
                    )
            
            print(f"Bearbetade nod: {folder_name}")
            conn.commit()
        except Exception as e:
            print(f"Fel vid bearbetning av {json_path}: {str(e)}")
    else:
        print(f"Varning: Ingen all_expanded.json i {folder_name}")
    
    # Fortsätt med undermappar (barn-noder)
    for item in os.listdir(full_path):
        item_path = os.path.join(current_path, item) if current_path else item
        process_tree(root_path, item_path, situation)

# Huvudfunktion
def main():
    print("Startar import av pokerstrategidata...")
    
    # Rensa gamla data (valfritt)
    cursor.execute("DELETE FROM strategies")
    cursor.execute("DELETE FROM hands")
    cursor.execute("DELETE FROM nodes")
    conn.commit()
    
    # Starta importprocessen
    process_tree(tree_path)
    
    # Visa statistik
    cursor.execute("SELECT COUNT(*) FROM nodes")
    nodes_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM hands")
    hands_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM strategies")
    strategies_count = cursor.fetchone()[0]
    
    print("\nImport slutförd!")
    print(f"Noder importerade: {nodes_count}")
    print(f"Unika händer: {hands_count}")
    print(f"Strategier: {strategies_count}")
    
    # Stäng anslutningen
    conn.close()

if __name__ == "__main__":
    main() 