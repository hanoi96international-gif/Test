# Änderungen: Leistungsabgleich

## 0.9.0b1 (Beta für den Pilotbetrieb)

**Neu**
- Rollen je API-Schlüssel (`fachverfahren`, `sachbearbeitung`, `alle`); mehrere Schlüssel pro Behörde
- Kürzelpflicht (`X-Bearbeiter`) bei Abgleich, Entscheidung und Erstattung, Kürzel im Protokoll
- Meldewerkzeug für CSV-Dateien (`melden`): Pilot ohne Fachverfahrensanbindung, Pseudonyme werden lokal gebildet
- Kennzahlen für die Pilotauswertung (`GET /kennzahlen`, Reiter „Kennzahlen“)
- Feedback aus der Oberfläche (`POST /feedback`, Befehl `feedback`)
- CSV-Export der Erstattungen für Kasse und Controlling
- OpenAPI-Beschreibung unter `GET /openapi.json`, Statusabfrage unter `GET /status`
- Datenbank-Migrationen (Schema 3), WAL-Modus, Sicherung im laufenden Betrieb (`sicherung`, `wartung`)
- Konfigurationsprüfung (`pruefen`), Docker, systemd mit Härtung und nächtlichem Wartungs-Timer, CI
- Oberfläche: Beta-Hinweis, Dialoge für Teilanerkennung und Ablehnung, Filter und Suche im Arbeitskorb,
  automatische Aktualisierung jede Minute, Versionsanzeige
- Teilanerkennung zeigt die ursprüngliche Forderung weiter an

**Sicherheit**
- Sperre nach 10 Fehlversuchen pro Minute und Adresse
- Zeitlimit für langsame Verbindungen, Verbindung wird nach Fehlern geschlossen
- Server-Log als JSON mit Anfrage-Nr., ohne Aktenzeichen, Pseudonyme oder Query-Parameter
- Warnung beim Start ohne TLS auf einer öffentlichen Adresse

**Behoben**
- Reiter waren auf dem Handy schon vor der Anmeldung sichtbar

## 2.0 (Prototyp)
Automatische Anmeldung und Bezifferung, Arbeitskorb, Weboberfläche.

## 1.0 (Prototyp)
Statusabgleich und manuelle Erstattungsansprüche.
