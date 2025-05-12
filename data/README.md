README
Översikt
Detta repo innehåller en fullständig pre-flop-strategi för No-Limit Hold’em organiserad som ett spelträd.
Varje mapp är en nod (beslutspunkt) och innehåller exakt en fil all_expanded.json som beskriver den optimala strategifördelningen för spelaren som är näst på tur att agera.

Mappnamn
php-template
Copy
Edit
<situationssträng>_<position>
situationssträng – sekventiell lista över alla tidigare aktioner i handen, från första spelaren till den som agerar precis före noden.

_ – skiljetecken.

position ∈ {utg, hj, co, btn, sb, bb} – anger vem som fattar beslutet i noden.

Exempel
nginx
Copy
Edit
ffr25fr160_btn
f – första spelaren foldar

f – andra spelaren foldar

r25 – tredje spelaren raisar till 2,5 bb

f – fjärde spelaren foldar

r160 – femte spelaren raisar till 16 bb
→ Button är näste man att agera.

Kodning av aktioner
ini
Copy
Edit
f    = fold
c    = call   (matchar föregående bet/raise)
x    = check
rNN  = raise  till NN/10 bb (ex. r25 = 2,5 bb, r90 = 9 bb)
Rai  = raise all-in
Filformat all_expanded.json
Toppnycklarna är samtliga tillgängliga aktioner i noden.

Handkod: två kort <Rank><Suit>, t.ex. 8s7d.

Samma hand kan förekomma i omvänd ordning (7d8s).

Frekvens ∈ [0, 1] anger hur ofta handen väljer aktionen.

Summan över alla aktioner för en given hand = 1,00.

Kortnotation
Rank: 2 – 9, T, J, Q, K, A

Suit: c (clubs), d (diamonds), h (hearts), s (spades)

Import-tips
Sortera korten fallande i rank (alfabetiskt som fallback) så att 8s7d och 7d8s behandlas som samma kombination.

Mapphierarki
Rotnoden _utg/ saknar situationssträng → första beslutet i handen, spelare i UTG.

Varje efterföljande nivå skapas genom att

lägga till aktuell aktion till situationssträngen

byta position till nästa spelare som är on turn.

Databas-förslag (PostgreSQL)
Tabeller
positions

actions

nodes

hands

strategies

Index / Nycklar
UNIQUE (node_id, hand_id) behövs ej – en hand kan ha flera rader (en per aktion).

Index på canonical i hands och situation i nodes för snabb uppslagning.

En materialiserad vy kan bygga kedjan av aktioner genom att splitta situation-strängen.

Normaliserings-steg vid import
Parsa mappnamn → situation, position.

Infoga/hämta rad i nodes.

För varje toppnyckel i JSON:
a. hämta/infoga rad i actions (inkl. raise_bb)
b. för varje handkod → normalisera & hämta/infoga i hands
c. infoga rad i strategies

Varför denna struktur?
Rekonstruera hela trädet via parent_id.

Ställ frågor som ”vilka händer vill HJ 3-betta mot en UTG-raise?”.

Lägg till nya noder/varianter utan att röra existerande data.

Lycka till! ♠️♦️♥️♣️