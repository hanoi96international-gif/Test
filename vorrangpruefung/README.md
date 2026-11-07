# Vorrangprüfung Wolfsburg (Prototyp)

Prototyp für einen Verbesserungsvorschlag. Er prüft, ob vorrangige Leistungen den Bezug von SGB II oder SGB XII beenden (§ 12a SGB II, § 2 SGB XII).

Zwei Modi:
- **Wohngeld + Kinderzuschlag** für Familien mit Kindern, einschließlich der Kombination beider Leistungen
- **Nur Wohngeld** für Singles, Paare und Rentner

Was geprüft wird: Erwerbsfähigkeit und Regelaltersgrenze (zuständig ist SGB II, SGB XII Kap. 3/4 oder AsylbLG), Mehrbedarfe, Rente mit Grundrentenfreibetrag, Vermögensgrenzen, die 3-Monats-Prognose, KV/PV ohne Grundsicherung einschließlich Zuschuss nach § 26 SGB II / § 32 SGB XII, Rundfunkbeitrag und Sonderfälle (Azubis/Studierende, EU-Arbeitsuchende, AsylbLG, stationäre Unterbringung), Kinder bei den Unterkunftskosten (Kinderwohngeld, Umgangskinder, weitere Personen in der Wohnung, ungeborenes Kind) und Karenzzeit-Rechner.

- `Vorrangpruefung_Wolfsburg.html`: per Doppelklick unter Windows im Browser öffnen. Keine Installation, keine Datenübertragung.
- `vorrangpruefung.html`: Quelldatei der Artifact-Seite.

Sprachen: Deutsch, English, Türkçe, العربية, Українська, Русский. Alle Rechenwerte lassen sich in der Seite unter „Parameter und Quellen“ ändern.
Alle Rechenregeln sind gegen die Gesetzestexte (Stand 07.11.2026), die DA-KiZ und die Mietgrenzen des Jobcenters Wolfsburg ab 01.04.2026 geprüft – siehe PRUEFPROTOKOLL.md.

## Excel-Fassung
- `Vorrangpruefung_Wolfsburg.xlsx`: dieselbe Prüfung als Excel-Arbeitsmappe mit Formeln (keine Makros).
  Blätter: Anleitung, Eingabe (gelbe Felder mit Auswahllisten), Ergebnis, Berechnung (Rechenweg mit Paragrafen), Szenarien, Parameter (alle Rechtswerte mit Quelle).
- Abgleich: 54 Testfälle (14 feste, 40 zufällige) liefern in Excel und Web-Rechner identische Ergebnisse (`werkzeuge/`).
- Neu erzeugen: `python3 werkzeuge/build_xlsx.py Vorrangpruefung_Wolfsburg.xlsx`

## Windows-Programm (.exe)
- `Vorrangpruefung_Wolfsburg.exe`: Doppelklick öffnet den Rechner im Standardbrowser. Keine Installation, keine Administratorrechte, keine Datenübertragung. Die Seite wird nach `%LOCALAPPDATA%\Vorrangpruefung` geschrieben, damit Eingaben gespeichert bleiben.
- Die Datei ist nicht digital signiert; Windows SmartScreen bzw. die IT-Richtlinie kann sie blockieren.
- Neu bauen: `werkzeuge/exe` – vorher `Vorrangpruefung_Wolfsburg.html` als `rechner.html` hineinkopieren, dann `GOOS=windows GOARCH=amd64 go build -ldflags "-H windowsgui -s -w" -o Vorrangpruefung_Wolfsburg.exe .`
