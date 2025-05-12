Databasen
SQLite-fil: data/db/poker_ranges.db

Tabeller
Tabell	Viktiga kolumner	Innehåll
position_alias	alias, canonical, ordinal	Översättning alias → kanonisk position
(t.ex. LJ → UTG, ordinal = 1).
nodes	id, action_sequence, position, folder_name, file_path	En rad per spelträd-nod (underkatalog i tree/).
ranges	id, node_id, action, combo, frequency	En rad per hand-kombination och beslut.

Position-alias som redan finns
yaml
Copy
Edit
UTG:  UTG, EP1, P1, LJ, LOWJACK
HJ :  HJ,  HIGHJACK, P2, P3
CO :  CO,  CUTOFF
BTN:  BTN, BUTTON
SB :  SB,  SMALLBLIND, SMALL_BLIND
BB :  BB,  BIGBLIND,   BIG_BLIND
Lägg till fler genom att stoppa in rader i position_alias innan du importerar data.