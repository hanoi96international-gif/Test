"""Wortsuchrätsel mit deutschen Themen-Wortlisten."""

import random

THEMEN = {
    "Tiere": ["HUND", "KATZE", "PFERD", "ELEFANT", "GIRAFFE", "LÖWE", "TIGER", "ZEBRA",
              "PINGUIN", "DELFIN", "ADLER", "EULE", "FUCHS", "HASE", "IGEL", "BIBER",
              "WOLF", "BÄR", "KÄNGURU", "SCHILDKRÖTE", "EICHHÖRNCHEN", "MAULWURF"],
    "Obst & Gemüse": ["APFEL", "BIRNE", "KIRSCHE", "ERDBEERE", "BANANE", "TRAUBE", "PFLAUME",
                      "KAROTTE", "GURKE", "TOMATE", "PAPRIKA", "ZWIEBEL", "KÜRBIS", "SPINAT",
                      "BROKKOLI", "RADIESCHEN", "HIMBEERE", "ZITRONE", "MELONE", "KARTOFFEL"],
    "Natur": ["WALD", "WIESE", "BACH", "BERG", "TAL", "SEE", "FLUSS", "BLUME", "BAUM",
              "MOOS", "FARN", "WOLKE", "REGEN", "SONNE", "GEWITTER", "REGENBOGEN", "STEIN",
              "QUELLE", "SCHMETTERLING", "LAVENDEL", "EICHE", "BIRKE"],
    "Berufe": ["BÄCKER", "LEHRERIN", "ÄRZTIN", "PILOT", "TISCHLER", "GÄRTNER", "KOCH",
               "MALER", "FRISEUR", "POLIZIST", "FÖRSTER", "ELEKTRIKER", "PFLEGER",
               "RICHTERIN", "BAUER", "FISCHER", "MECHANIKER", "ARCHITEKT", "IMKER"],
    "Küche": ["TOPF", "PFANNE", "LÖFFEL", "GABEL", "MESSER", "TELLER", "TASSE", "OFEN",
              "HERD", "SCHNEEBESEN", "SIEB", "REIBE", "NUDELHOLZ", "KESSEL", "SCHÜSSEL",
              "BACKBLECH", "KELLE", "MIXER", "TOASTER", "KÜHLSCHRANK"],
    "Reisen": ["KOFFER", "PASS", "FLUGHAFEN", "BAHNHOF", "HOTEL", "STRAND", "KARTE",
               "KOMPASS", "ZELT", "RUCKSACK", "FÄHRE", "INSEL", "WANDERN", "URLAUB",
               "SOUVENIR", "POSTKARTE", "GEPÄCK", "TICKET", "AUSFLUG", "GRENZE"],
    "Sport": ["FUSSBALL", "TENNIS", "SCHWIMMEN", "LAUFEN", "RADFAHREN", "TURNEN",
              "HANDBALL", "SKIFAHREN", "RUDERN", "SEGELN", "BOXEN", "KLETTERN", "GOLF",
              "HOCKEY", "TISCHTENNIS", "REITEN", "YOGA", "TANZEN", "FECHTEN", "SURFEN"],
    "Musik": ["GITARRE", "KLAVIER", "GEIGE", "TROMMEL", "FLÖTE", "TROMPETE", "HARFE",
              "CELLO", "MELODIE", "RHYTHMUS", "NOTE", "CHOR", "ORCHESTER", "TAKT",
              "SAXOFON", "AKKORDEON", "LIED", "KONZERT", "DIRIGENT", "HARMONIE"],
}

DIRECTIONS = {
    "leicht": [(0, 1), (1, 0)],
    "mittel": [(0, 1), (1, 0), (1, 1), (-1, 1)],
    "schwer": [(0, 1), (1, 0), (1, 1), (-1, 1), (0, -1), (-1, 0), (-1, -1), (1, -1)],
}

# Grob nach deutscher Buchstabenhäufigkeit gewichtet, damit das Füllmaterial natürlich wirkt
FILL = "EEEEEEENNNNNIIIIISSSSRRRRAAAAATTTTDDDHHHUUULLLCCGGMMOOBBWFKZPVÄÖÜJY"


def generate(rng: random.Random, theme: str, size: int = 15, count: int = 12,
             difficulty: str = "mittel"):
    """Gibt (gitter, wörter, positionen) zurück; positionen = Liste von Zellkoordinaten je Wort."""
    words = [w for w in THEMEN[theme] if len(w) <= size]
    rng.shuffle(words)
    grid = [[""] * size for _ in range(size)]
    placed, positions = [], []
    dirs = DIRECTIONS[difficulty]
    for word in words:
        if len(placed) == count:
            break
        for _ in range(200):
            dr, dc = rng.choice(dirs)
            r, c = rng.randrange(size), rng.randrange(size)
            cells = [(r + dr * i, c + dc * i) for i in range(len(word))]
            if all(0 <= a < size and 0 <= b < size and grid[a][b] in ("", word[i])
                   for i, (a, b) in enumerate(cells)):
                for i, (a, b) in enumerate(cells):
                    grid[a][b] = word[i]
                placed.append(word)
                positions.append(cells)
                break
    for row in grid:
        for i, ch in enumerate(row):
            if not ch:
                row[i] = rng.choice(FILL)
    return grid, placed, positions
