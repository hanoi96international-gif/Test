# 🧩 Rätselfabrik

Eine automatische Fabrik für **druckfertige Rätselhefte**. Jeden Montag erzeugt GitHub Actions
ein neues Heft mit 12 Sudokus, 12 deutschen Wortsuchrätseln und 12 Labyrinthen, jeweils mit
Lösungen. Dazu kommen Vorschaubilder und ein fertiger Verkaufstext.
Du musst die Dateien nur noch hochladen und verkaufen.

## Was du jede Woche bekommst (unter *Releases*)

| Datei | Wofür |
|---|---|
| `raetselfabrik-JJJJ-KWnn-a4.pdf` | Digitaler Download für Etsy, Gumroad, Ko-fi oder eBay |
| `raetselfabrik-JJJJ-KWnn-letter.pdf` | Innenteil für ein gedrucktes Taschenbuch bei Amazon KDP |
| `*-cover.png`, `*-vorschau-*.png` | Produktbilder |
| `*-verkaufstext.md` | Titel, Beschreibung, Preisvorschlag und Tags zum Kopieren |

Das Thema wechselt automatisch (Tiere, Obst & Gemüse, Natur, Berufe, Küche, Reisen, Sport,
Musik). Gleiche Kalenderwoche ergibt immer das gleiche Heft.

## Einmalig einrichten (ca. 30 Minuten)

1. Diesen Branch in `main` mergen, denn geplante Workflows laufen nur auf dem Standard-Branch.
2. Unter *Actions → Wöchentliches Rätselheft → Run workflow* das erste Heft sofort erzeugen.
3. Einen Verkaufskanal anlegen:
   - **Etsy** (ca. 0,20 $ pro Listing plus Gebühren) oder **Gumroad / Ko-fi** (kostenlos, Provision pro Verkauf):
     PDF als digitalen Download hochladen.
   - **Amazon KDP** (kostenlos): Letter-PDF als Taschenbuch-Innenteil hochladen, Cover im KDP-Cover-Creator bauen.
4. Danach jeden Montag: Release öffnen, Dateien hochladen, Text einfügen. Das dauert etwa 10 Minuten.

## Lokal ausprobieren

```bash
pip install -r requirements.txt
python -m raetselfabrik                         # aktuelle Woche, A4
python -m raetselfabrik --woche 2026-W50 --format letter --anzahl 20
python -m pytest -q tests
```

## Ehrlicher Hinweis

Einnahmen sind nicht garantiert. Der Markt für Rätselhefte ist groß, aber umkämpft.
Was erfahrungsgemäß hilft: viele Listings (jede Woche ein neues), gut sichtbare Vorschaubilder,
Bündel („3 Hefte zum Preis von 2“) und Nischen wie „Großdruck für Senioren“ oder Saisonthemen.
Die Rätsel werden selbst generiert, es gibt also keine Urheberrechtsprobleme.
