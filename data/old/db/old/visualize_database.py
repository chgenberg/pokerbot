#!/usr/bin/env python3
"""
visualize_database.py
---------------------
Skapar en HTML-rapport över databasens schema.
Kräver inga externa beroenden.

Körning:
    python visualize_database.py [sökväg-till-db]
Resulterande fil:
    db_schema.html  –   sparas i samma mapp som skriptet.
"""

import os
import sqlite3
import sys
import datetime

# --- Konfiguration --------------------------------------------------------
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)  # Katalogen ovanför

# Möjliga platser för databasen
POSSIBLE_DB_PATHS = [
    os.path.join(SCRIPT_DIR, "poker_strategy.db"),       # I samma mapp som skriptet
    os.path.join(PARENT_DIR, "poker_strategy.db"),       # I huvudmappen
]

OUTPUT_FILE = os.path.join(SCRIPT_DIR, "db_schema.html")
# --------------------------------------------------------------------------


def collect_schema(conn):
    """Hämtar tabeller, kolumner och FK-relationer från SQLite."""
    cur = conn.cursor()

    # Alla användartabeller (skippar interna sqlite_*)
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%';
    """)
    tables = [row[0] for row in cur.fetchall()]

    schema_data = {}
    for table in tables:
        # Kolumner
        cur.execute(f"PRAGMA table_info('{table}')")
        columns = cur.fetchall()  # cid, name, type, notnull, dflt, pk

        # Foreign-keys
        cur.execute(f"PRAGMA foreign_key_list('{table}')")
        fks = cur.fetchall()

        # Indexar
        cur.execute(f"PRAGMA index_list('{table}')")
        indexes = cur.fetchall()

        # Sampla data (första 5 raderna)
        try:
            cur.execute(f"SELECT * FROM '{table}' LIMIT 5")
            sample_data = cur.fetchall()
            column_names = [description[0] for description in cur.description]
        except sqlite3.Error:
            sample_data = []
            column_names = []

        schema_data[table] = {
            'columns': columns,
            'foreign_keys': fks,
            'indexes': indexes,
            'sample_data': sample_data,
            'column_names': column_names
        }

    return schema_data


def generate_html(schema_data, db_path):
    """Genererar HTML-rapporten."""
    html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Databasschema - {os.path.basename(db_path)}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.5; }}
        h1, h2, h3 {{ color: #2c3e50; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ text-align: left; padding: 8px; border: 1px solid #ddd; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .table-container {{ margin-bottom: 40px; padding: 10px; border: 1px solid #eee; border-radius: 5px; }}
        .fk {{ color: #3498db; }}
        .pk {{ color: #e74c3c; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Databasschema: {os.path.basename(db_path)}</h1>
    <p>Genererad: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    <h2>Tabellöversikt</h2>
    <ul>
"""

    # Innehållsförteckning
    for table in schema_data:
        html += f'        <li><a href="#{table}">{table}</a></li>\n'
    
    html += "    </ul>\n"

    # Detaljer för varje tabell
    for table, data in schema_data.items():
        html += f"""
    <div class="table-container" id="{table}">
        <h2>Tabell: {table}</h2>
        
        <h3>Kolumner</h3>
        <table>
            <tr>
                <th>Namn</th>
                <th>Typ</th>
                <th>Not Null</th>
                <th>Default</th>
                <th>Primary Key</th>
            </tr>
"""

        for cid, name, col_type, notnull, default, pk in data['columns']:
            pk_class = ' class="pk"' if pk else ''
            html += f"""
            <tr>
                <td{pk_class}>{name}</td>
                <td>{col_type}</td>
                <td>{"Ja" if notnull else "Nej"}</td>
                <td>{default if default else ""}</td>
                <td>{"Ja" if pk else "Nej"}</td>
            </tr>"""
        
        html += """
        </table>
"""

        # Foreign keys
        if data['foreign_keys']:
            html += """
        <h3>Foreign Keys</h3>
        <table>
            <tr>
                <th>Från kolumn</th>
                <th>Till tabell</th>
                <th>Till kolumn</th>
            </tr>
"""
            for fk in data['foreign_keys']:
                _, _, from_col, to_table, to_col, *_ = fk
                html += f"""
            <tr>
                <td>{from_col}</td>
                <td>{to_table}</td>
                <td>{to_col}</td>
            </tr>"""
            
            html += """
        </table>
"""

        # Dataexempel
        if data['sample_data']:
            html += """
        <h3>Dataexempel</h3>
        <table>
            <tr>
"""
            for col in data['column_names']:
                html += f"                <th>{col}</th>\n"
            html += "            </tr>\n"
            
            for row in data['sample_data']:
                html += "            <tr>\n"
                for value in row:
                    html += f"                <td>{value}</td>\n"
                html += "            </tr>\n"
            
            html += """
        </table>
"""
        
        html += """
    </div>
"""

    html += """
</body>
</html>
"""
    return html


def find_database():
    """Letar efter databas på olika möjliga platser."""
    # Först: kolla om användaren angett sökväg som argument
    if len(sys.argv) > 1:
        return sys.argv[1]
        
    # Sedan: pröva möjliga platser
    for path in POSSIBLE_DB_PATHS:
        if os.path.exists(path):
            print(f"Hittade databas på: {path}")
            return path
            
    return None


def main():
    db_path = find_database()
    
    if not db_path or not os.path.exists(db_path):
        print("❌ Hittar inte databasen!")
        print("Användning: python visualize_database.py [sökväg-till-db]")
        print("Försökte leta på:", *POSSIBLE_DB_PATHS, sep="\n  - ")
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        schema_data = collect_schema(conn)

    if not schema_data:
        print(f"❌ Inga tabeller hittades i databasen: {db_path}")
        sys.exit(1)

    html_output = generate_html(schema_data, db_path)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_output)
    
    print(f"✅ Databasvisualisering sparad som: {OUTPUT_FILE}")
    print(f"   Öppna filen i en webbläsare för att se resultatet.")


if __name__ == "__main__":
    main()