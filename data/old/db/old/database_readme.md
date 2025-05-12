# Pokerstrategi-databas

Detta är ett system för att konvertera pokerstrategi-trädet till en relationsdatabas. Systemet består av två huvudskript:

1. `create_database.py` - Skapar databasschema och grundläggande tabeller
2. `populate_database.py` - Läser alla mappnoder från trädet och importerar data

## Installera beroenden

För att köra skripten behöver du Python 3.6 eller senare. Inga externa moduler behövs då systemet använder Pythons standardbibliotek.

## Steg 1: Skapa databas

Kör följande kommando för att skapa databasen:

```
python create_database.py
```

Detta kommer att:
- Skapa en SQLite-databas i `C:\Users\Propietario\Desktop\data\db\poker_strategy.db`
- Skapa alla nödvändiga tabeller och index
- Generera en beskrivningsfil (`databas_beskrivning.txt`) med information om databasstrukturen

## Steg 2: Importera data

Kör följande kommando för att importera all data från mappstrukturen:

```
python populate_database.py
```

Detta kommer att:
- Genomsöka hela mappstrukturen rekursivt från `C:\Users\Propietario\Desktop\data\tree`
- Läsa varje `all_expanded.json`-fil i mappstrukturens noder
- Importera alla händer, aktioner och frekvenser till databasen
- Visa statistik om antal importerade noder, händer och strategier

## Databasstruktur

Databasen består av fem tabeller:

1. `positions` - Spelarpositioner (utg, hj, co, btn, sb, bb)
2. `actions` - Aktionstyper (fold, call, check, raise)
3. `nodes` - Noder/beslutspunkter i spelträdet
4. `hands` - Pokerhänder (med normaliserade representationer)
5. `strategies` - Strategier (kombination av nod, hand, aktion och frekvens)

För detaljerad information om tabellernas struktur, se filen `databas_beskrivning.txt` som skapas av `create_database.py`.

## Använda databasen

När databasen är skapad och fylld med data kan du använda SQLite för att ställa frågor, t.ex:

```
sqlite3 "C:\Users\Propietario\Desktop\data\db\poker_strategy.db"
```

Exempel på SQLite-frågor:

```sql
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
```

## Anpassningar

Om du behöver ändra databasstrukturen eller importlogiken, kan följande filer modifieras:

- `create_database.py` - För att ändra databasschema
- `populate_database.py` - För att ändra importlogik

Se till att köra `create_database.py` följt av `populate_database.py` efter ändringar för att återskapa databasen. 