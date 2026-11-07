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

---

# 🎯 Bounty-Radar

Viele Open-Source-Projekte und Firmen **bezahlen für behobene Fehler**: über Algora, IssueHunt,
Opire oder eigene „Bounty“-Labels, oft 50–5.000 $ pro Issue. Der Radar durchsucht GitHub
**jede Nacht automatisch** nach solchen offenen Aufgaben. Er bewertet sie nach
*Betrag ÷ Konkurrenz* und schreibt die besten 25 in ein Issue „🎯 Bounty-Radar“ in diesem Repo.
GitHub schickt dir dazu eine Benachrichtigung aufs Handy.

**Einrichten:**
1. Branch in `main` mergen, dann *Actions → Bounty-Radar → Run workflow*.
2. Optional unter *Settings → Secrets and variables → Actions → Variables* setzen:
   - `BOUNTY_SPRACHEN`, z. B. `python,typescript,rust` (leer = alle Sprachen)
   - `BOUNTY_MIN_BETRAG`, z. B. `100`

**Und dann?** Such dir eine Aufgabe aus dem Bericht aus und öffne eine Claude-Code-Sitzung mit
dem Projekt. Wir analysieren den Fehler zusammen, bauen den Fix und reichen ihn ein.
Ausgezahlt wird, wenn das Projekt den Pull Request annimmt.

Lokal: `python -m bounty_radar --sprachen python --min-betrag 100` (ohne Token langsamer wegen Rate-Limit).

**Ehrlich:** Beliebte Bounties sind schnell vergeben, und manche Projekte nehmen nur Fixes von
Leuten an, die ihren Code gut kennen. Der Radar spart dir die Suche, die eigentliche Arbeit ist der Fix.

---

# 🏛️ Leistungsabgleich Jobcenter ↔ Wohngeldstelle

Ein Prototyp für eine **direkte Schnittstelle zwischen Jobcenter (SGB II) und Wohngeldstelle**.
Mit der Familienkasse gibt es den digitalen Erstattungsweg schon, hier fehlt er bisher.
Folge: In Eilfällen wartet man Tage oder Wochen auf Rückmeldung der anderen Behörde.

**Was die Schnittstelle kann**

- **Abgleich in beide Richtungen:** Das Jobcenter sieht, ob für die Person Wohngeld *beantragt* ist
  oder *gerade läuft* (Zeitraum, Betrag, Aktenzeichen, Ansprechperson). Umgekehrt sieht die
  Wohngeldstelle laufende oder beantragte Bürgergeld-Fälle.
- **Entscheidungshinweise für Eilfälle**, z. B. „Wohngeld läuft, bei Bürgergeld-Bewilligung
  entfällt es (§ 7 WoGG), Erstattung nach § 104 SGB X anmelden“.
- **Erstattungsansprüche digital:** anmelden (auch erst dem Grunde nach, § 111 SGB X), später
  beziffern. Die Gegenseite erkennt an, erkennt teilweise an oder lehnt mit Begründung ab.
  Danach wird der Anspruch als erledigt markiert.

**Datenschutz ist eingebaut, nicht nachgerüstet**

- Im Register stehen **keine Namen**, nur ein Pseudonym (HMAC aus Name + Geburtsdatum). Den
  Schlüssel haben nur die Behörden. „Müller“ und „Mueller“ ergeben dasselbe Pseudonym.
- **Zweckbindung:** Abfragen geht nur über ein eigenes, gemeldetes Aktenzeichen.
  Gezieltes Herumsuchen ist damit ausgeschlossen.
- **Protokoll** jeder Meldung und Abfrage, auch abgelehnter, abrufbar über `GET /protokoll`.

**Ausprobieren**

```bash
python -m leistungsabgleich demo          # Eilfall Schritt für Schritt
python -m leistungsabgleich schluessel    # API-Schlüssel erzeugen → behoerden.json
python -m leistungsabgleich serve --db abgleich.db --behoerden behoerden.json
```

Alle Endpunkte stehen oben in `leistungsabgleich/__main__.py`. Beispiel Abgleich:
`GET /faelle/BG-12345/abgleich` mit `Authorization: Bearer <Schlüssel des Jobcenters>`.

**Ehrlich: Was vor einem echten Einsatz fehlt.** Das ist ein Prototyp zum Zeigen und Diskutieren.
Für den Echtbetrieb braucht es:
- eine **Rechtsgrundlage** für den Abgleich ohne Einzelanfrage (§ 69 SGB X, ggf. landesrechtliche
  Regelung oder Vereinbarung zwischen Träger und Kommune) sowie eine Datenschutz-Folgenabschätzung
  nach Art. 35 DSGVO,
- Betrieb im Behördennetz mit TLS und Anbindung an die Fachverfahren (z. B. ALLEGRO bei den
  Jobcentern, die Wohngeld-Software der Kommune), statt die Daten von Hand zu melden,
- langfristig ein XÖV-konformes Nachrichtenformat und Abstimmung mit BA, Land und IT-Dienstleister.
