# Betriebshandbuch Leistungsabgleich (Beta 0.9)

Für die IT der Kommune bzw. des Jobcenters und für die Pilotverantwortlichen.

## 1. Bevor echte Daten fließen (Pilot-Checkliste)

Die Software ist eine Beta. Die folgenden Punkte sind **nicht technisch** und müssen vor dem
ersten echten Fall geklärt sein:

- [ ] Rechtsgrundlage für die Übermittlung geprüft (u. a. §§ 67 ff. SGB X, § 69 SGB X), Ergebnis schriftlich
- [ ] Vereinbarung zwischen Jobcenter und Wohngeldstelle über den Pilot (Zweck, Umfang, Dauer, Ansprechpersonen)
- [ ] Datenschutz-Folgenabschätzung (Art. 35 DSGVO) und Verzeichnis der Verarbeitungstätigkeiten ergänzt
- [ ] Datenschutzbeauftragte beider Stellen und Personalräte beteiligt
- [ ] Fachaufsicht hat Rechenregel und Rechtsgrundlagen in den Texten geprüft (siehe README, „Was automatisch passiert“)
- [ ] Freigrenze für automatische Anerkennung festgelegt (Empfehlung für den Start: keine, also alles von Hand)
- [ ] Löschfristen mit dem Datenschutz abgestimmt (Voreinstellung: Fälle 24, Erstattungen 48, Protokoll 24 Monate)
- [ ] Betrieb im Behördennetz, Zugriff nur aus den beteiligten Dienststellen
- [ ] Kennzahlen für die Auswertung vereinbart (siehe Abschnitt 6)

## 2. Installation

Voraussetzung: Python ab 3.10, keine weiteren Pakete.

**Variante A: systemd**
```bash
sudo cp -r leistungsabgleich /opt/leistungsabgleich/
sudo mkdir -p /etc/leistungsabgleich && sudo cp deploy/behoerden.beispiel.json /etc/leistungsabgleich/behoerden.json
sudo cp deploy/leistungsabgleich*.service deploy/leistungsabgleich-wartung.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now leistungsabgleich leistungsabgleich-wartung.timer
curl -s http://127.0.0.1:8080/status
```

**Variante B: Container**
```bash
docker build -f deploy/Dockerfile -t leistungsabgleich:0.9.0b1 .
docker run -d --name abgleich -v /srv/abgleich:/daten -p 127.0.0.1:8080:8080 leistungsabgleich:0.9.0b1
```

Der Dienst lauscht standardmäßig nur auf 127.0.0.1. Davor gehört ein TLS-Reverse-Proxy (z. B.
nginx) mit dem Zertifikat der Behörde. Alternativ direkt mit `--zertifikat` und `--zertifikat-schluessel`.

## 3. Behörden und Schlüssel einrichten

Für jede Behörde mindestens zwei Schlüssel anlegen:

| Rolle | Wer nutzt ihn | darf |
|---|---|---|
| `fachverfahren` | Fachverfahren oder Meldewerkzeug | Fälle melden |
| `sachbearbeitung` | Weboberfläche | abgleichen, Arbeitskorb, entscheiden, Kennzahlen, Protokoll |

```bash
python -m leistungsabgleich schluessel --rolle sachbearbeitung
```
Der Schlüssel geht über einen sicheren Weg an die Behörde. In `behoerden.json` steht nur der
Hash. Danach die Konfiguration prüfen und den Dienst neu starten:
```bash
python -m leistungsabgleich pruefen --konfig /etc/leistungsabgleich/behoerden.json
sudo systemctl restart leistungsabgleich
```
**Schlüssel wechseln:** neuen Eintrag hinzufügen, neu starten, alten Eintrag nach der Umstellung löschen.

**Pseudonym-Schlüssel** (`ABGLEICH_SCHLUESSEL`): ein gemeinsamer Zufallswert für beide Behörden,
z. B. mit `python -m leistungsabgleich schluessel` erzeugt. Er liegt **nur bei den Behörden**
(Meldewerkzeug bzw. Fachverfahren), nie auf dem Server. Wer ihn ändert, muss alle Fälle neu melden.

## 4. Melden im Pilot ohne Fachverfahrensanbindung

Solange die Fachverfahren nicht angebunden sind, exportiert die Behörde eine CSV-Datei
(Vorlage: `docs/meldevorlage.csv`) und meldet sie von einem Arbeitsplatz der Behörde:

```bash
export ABGLEICH_SCHLUESSEL=…   # gemeinsamer Pseudonym-Schlüssel
export ABGLEICH_API_KEY=…      # Schlüssel mit Rolle fachverfahren
python -m leistungsabgleich melden faelle.csv --url https://abgleich.intern --probelauf   # erst prüfen
python -m leistungsabgleich melden faelle.csv --url https://abgleich.intern --bearbeiter mkern
```
Namen und Geburtsdaten werden lokal in Pseudonyme umgerechnet und verlassen den Arbeitsplatz
nicht. Fehler in der Datei werden mit Zeilennummer gemeldet, bevor etwas gesendet wird.
Jede Meldung ersetzt den Stand des Falls vollständig. Also immer alle Monate eines Falls mitschicken.

## 5. Laufender Betrieb

| Was | Wie |
|---|---|
| Läuft der Dienst? | `GET /status` (ohne Anmeldung), Container-Healthcheck ist eingebaut |
| Logs | eine JSON-Zeile je Anfrage auf stderr (journald/Docker), ohne Aktenzeichen oder Pseudonyme |
| Fehlermeldung von Nutzern | enthält eine Anfrage-Nr., die im Log unter `anfrage` steht |
| Sicherung | nächtlich per Timer (`wartung`), 14 Stände in `/var/lib/leistungsabgleich/sicherungen` |
| Wiederherstellen | Dienst stoppen, Sicherung als `abgleich.db` zurückkopieren, Dienst starten |
| Löschfristen | laufen mit `wartung` automatisch |
| Update | Dienst stoppen, Programmordner ersetzen, starten. Die Datenbank wird automatisch migriert. Vorher Sicherung! |
| Brute-Force-Schutz | 10 falsche Schlüssel pro Minute und Adresse, danach 60 s Sperre (HTTP 429) |
| Schnittstellenbeschreibung | `GET /openapi.json` für die Hersteller der Fachverfahren |

## 6. Pilot auswerten

- **Kennzahlen** in der Oberfläche bzw. `GET /kennzahlen`: Anzahl Erstattungen je Status, Anteil
  automatisch anerkannt, durchschnittliche Tage von der Anmeldung bis zur Erstattung, Abgleiche.
- **Feedback** der Nutzer: `python -m leistungsabgleich feedback --db …`
- **CSV-Export** der Erstattungen für Kasse und Controlling: Button in der Oberfläche.

Vorschlag für den Vergleich vorher/nachher: Durchlaufzeit Anmeldung → Zahlungseingang,
Bearbeitungsminuten je Fall (Stichprobe), Anzahl Rückforderungen beim Bürger.

## 7. Bekannte Grenzen der Beta

- Ein Server für beide Behörden, SQLite-Datenbank: gut für einige zehntausend Fälle, nicht für ein ganzes Land.
- Anmeldung per Schlüssel und Kürzel, keine Anbindung an das Active Directory oder an Single Sign-on.
- Wer zusätzlich gezahlt hat, nachdem eine Erstattung entschieden wurde, bekommt dafür keine neue Forderung. Das erledigt ein Mensch.
- Teilmonate und Kinderzuschlag werden nicht gesondert berechnet. Die gemeldeten Monatsbeträge zählen.
