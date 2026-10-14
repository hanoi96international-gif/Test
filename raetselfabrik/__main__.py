"""Erzeugt ein komplettes Rätselheft samt Verkaufstext.

Aufruf:  python -m raetselfabrik [--woche 2026-W42] [--format a4|letter] [--ausgabe dist]
"""

import argparse
import datetime as dt
import random
from functools import partial
from pathlib import Path

from . import labyrinth, sudoku, wortsuche
from .pdf import Book, draw_labyrinth, draw_sudoku, draw_wortsuche

DIFFICULTIES = ["leicht", "mittel", "schwer"]


def build(year, week, page_format, out_dir, per_type):
    themes = sorted(wortsuche.THEMEN)
    theme = themes[(year * 53 + week) % len(themes)]
    rng = random.Random(year * 100 + week)  # gleiche Woche -> gleiches Heft
    edition = f"Ausgabe {year}-{week:02d}"
    slug = f"raetselfabrik-{year}-KW{week:02d}-{page_format}"

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{slug}.pdf"
    book = Book(str(pdf_path), f"Rätselfabrik – {theme}", edition, page_format)
    book.cover(theme, [f"{per_type} Sudokus", f"{per_type} Wortsuchrätsel", f"{per_type} Labyrinthe",
                       "leicht · mittel · schwer"])
    book.intro()
    solutions = []

    for i in range(per_type):
        diff = DIFFICULTIES[i * 3 // per_type]
        puzzle, solution = sudoku.generate(rng, diff)
        label = f"Sudoku {i + 1} ({diff})"
        book.full_page(label, lambda x, y, w, h, p=puzzle: draw_sudoku(book.c, x + (w - min(w, h)) / 2, y + h - min(w, h), min(w, h), p))
        solutions.append((label, lambda x, y, w, h, p=puzzle, s=solution: draw_sudoku(book.c, x, y + h - min(w, h), min(w, h), p, s)))

    for i in range(per_type):
        diff = DIFFICULTIES[i * 3 // per_type]
        grid, words, positions = wortsuche.generate(rng, theme, size=13 + 2 * DIFFICULTIES.index(diff),
                                                    count=10 + 2 * DIFFICULTIES.index(diff), difficulty=diff)
        label = f"Wortsuche {i + 1} ({diff})"
        word_lines = [" · ".join(words[k:k + 4]) for k in range(0, len(words), 4)]
        book.full_page(label, lambda x, y, w, h, g=grid: draw_wortsuche(book.c, x + (w - min(w, h)) / 2, y + h - min(w, h), min(w, h), g),
                       footer_lines=["Gesucht:"] + word_lines)
        solutions.append((label, lambda x, y, w, h, g=grid, p=positions: draw_wortsuche(book.c, x, y + h - min(w, h), min(w, h), g, p)))

    for i in range(per_type):
        diff = DIFFICULTIES[i * 3 // per_type]
        scale = 1 + DIFFICULTIES.index(diff)
        walls, path = labyrinth.generate(rng, width=10 + 6 * scale, height=13 + 8 * scale)
        label = f"Labyrinth {i + 1} ({diff})"
        book.full_page(label, partial(draw_labyrinth, book.c, walls=walls))
        solutions.append((label, partial(draw_labyrinth, book.c, walls=walls, path=path)))

    book.solution_pages(solutions)
    book.save()

    listing = out_dir / f"{slug}-verkaufstext.md"
    listing.write_text(LISTING.format(theme=theme, edition=edition, n=per_type,
                                      pages=book.page_no + 1, fmt=page_format.upper()), encoding="utf-8")
    return pdf_path, listing


LISTING = """# Rätselheft „{theme}“ – {n} Sudokus, {n} Wortsuchen, {n} Labyrinthe ({edition})

**Vorgeschlagener Preis:** 2,99 € (digitaler Download) · 6,99 € (gedruckt, z. B. Amazon KDP)

## Beschreibung

Gemütliche Rätselzeit garantiert! Dieses Heft zum Thema **{theme}** enthält {pages} Seiten
im Format {fmt} zum Ausdrucken:

- {n} Sudokus in drei Schwierigkeitsstufen (leicht, mittel, schwer), jedes mit eindeutiger Lösung
- {n} Wortsuchrätsel mit deutschen Wörtern rund um „{theme}“
- {n} Labyrinthe, von entspannt bis knifflig
- Alle Lösungen am Ende des Heftes

Ideal für lange Abende, Zugfahrten, Wartezimmer, Seniorinnen und Senioren, Familien und
alle, die ihr Gehirn fit halten möchten. Sofort herunterladen, ausdrucken, losrätseln!

## Tags

rätselheft, sudoku, wortsuche, labyrinth, rätsel zum ausdrucken, gedächtnistraining,
geschenk, senioren, {theme}, druckvorlage, pdf, rätselbuch, beschäftigung
"""


def main():
    today = dt.date.today().isocalendar()
    ap = argparse.ArgumentParser(description="Erzeugt ein druckfertiges Rätselheft als PDF.")
    ap.add_argument("--woche", default=f"{today.year}-W{today.week:02d}", help="z. B. 2026-W42")
    ap.add_argument("--format", choices=["a4", "letter"], default="a4")
    ap.add_argument("--anzahl", type=int, default=12, help="Rätsel pro Typ")
    ap.add_argument("--ausgabe", type=Path, default=Path("dist"))
    args = ap.parse_args()
    year, week = args.woche.split("-W")
    pdf, listing = build(int(year), int(week), args.format, args.ausgabe, args.anzahl)
    print(f"PDF:         {pdf}\nVerkaufstext: {listing}")


if __name__ == "__main__":
    main()
