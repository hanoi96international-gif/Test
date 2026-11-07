# Verbesserungsvorschlag: Digitaler Erstattungsweg zwischen Jobcenter und Wohngeldstelle

*Vorlage, bitte mit eigenen Zahlen und dem Namen der eigenen Dienststelle ergänzen.*

## Ausgangslage

Viele Haushalte stehen an der Grenze zwischen Bürgergeld und Wohngeld und wechseln zwischen
beiden Leistungen. Überschneiden sich die Bewilligungen, entstehen Erstattungsansprüche nach
§§ 102 ff. SGB X. Heute läuft das meist so:

1. Das Jobcenter meldet den Anspruch schriftlich dem Grunde nach an, um die Frist zu wahren (§ 111 SGB X).
2. Nach der Bewilligung fragt eine Seite nach Zeiträumen und Beträgen, die andere sucht sie heraus.
3. Die Bezifferung wird von Hand gerechnet, geprüft, verschickt und beantwortet.
4. Parallel wird der Bescheid aufgehoben und häufig beim Bürger zurückgefordert, obwohl die
   Erstattung den Betrag decken würde.

Mit der Familienkasse gibt es für Erstattungen bereits einen digitalen Weg. Zwischen Jobcenter
und Wohngeldstelle fehlt er bisher.

**Eigene Zahlen (bitte ergänzen):**
- Erstattungsfälle Jobcenter ↔ Wohngeldstelle pro Monat: ___
- Durchschnittliche Bearbeitungszeit je Fall (beide Seiten zusammen): ___ Minuten
- Durchschnittliche Dauer von der Anmeldung bis zum Zahlungseingang: ___ Wochen
- Fälle mit Doppelzahlung bzw. Rückforderung beim Bürger pro Jahr: ___

## Vorschlag

Eine Schnittstelle, an die beide Fachverfahren den Stand ihrer Fälle melden (Status,
Bescheiddatum, Monatsbeträge). Daraus ergibt sich automatisch:

- **Statusabfrage:** Läuft bei der anderen Stelle ein Antrag oder eine Bewilligung? Mit Aktenzeichen und Ansprechperson.
- **Automatische Anmeldung**, sobald eine Stelle zahlt und bei der anderen ein Antrag läuft.
- **Automatische Bezifferung** Monat für Monat, sobald die andere Stelle bewilligt.
- **Hinweis vor der Auszahlung:** Das Fachverfahren erfährt sofort, welcher Teil der Nachzahlung an die andere Behörde geht.
- **Arbeitskorb:** Die Sachbearbeitung sieht nur noch, was sie tun muss: in der Regel den Bescheid aufheben und die Erstattung bestätigen. Bis zu einer Freigrenze kann die Anerkennung automatisch erfolgen.
- **Sonderfälle** (abweichender Haushalt, Doppelbezug) werden erkannt und gezielt zur Prüfung vorgelegt.

Ein lauffähiger Prototyp zeigt den Ablauf an Beispielfällen (siehe README, `serve --demo`).

## Nutzen

| | heute | mit Schnittstelle |
|---|---|---|
| Anmeldung | Schreiben, Fristüberwachung | automatisch |
| Bezifferung | Nachfragen, Rechnen, Schreiben | automatisch, zur Bestätigung |
| Aufhebung | Bescheid + oft Rückforderung beim Bürger | Bescheid, Rückforderung entfällt meist |
| Durchlaufzeit | Wochen | Tage |
| Doppelzahlungen | werden spät bemerkt | werden vor der Auszahlung verhindert |

Geschätzte Ersparnis: ___ Fälle × ___ Minuten = ___ Stunden pro Monat.
Für die Bürgerinnen und Bürger entfallen Rückforderungen und Unsicherheit.

## Datenschutz

- Nur Fälle mit möglicher Überschneidung sind betroffen; ausgetauscht wird nur, was für die Erstattung nötig ist.
- Keine Namen in der Schnittstelle, sondern Pseudonyme, deren Schlüssel nur die Behörden haben.
- Abfragen nur über ein eigenes Aktenzeichen, jede Abfrage wird protokolliert.
- Löschfristen sind eingebaut.
- Nötig: Prüfung der Rechtsgrundlage (u. a. §§ 67 ff. SGB X), Datenschutz-Folgenabschätzung, Einbindung der Datenschutzbeauftragten und des Personalrats.

## Nächste Schritte

1. Fallzahlen und Bearbeitungszeiten erheben.
2. Fachaufsicht und Datenschutz zur Rechenregel und Rechtsgrundlage anhören.
3. Klären, ob BA, Land oder IT-Dienstleister bereits an einer Lösung arbeiten.
4. Pilot mit einer Wohngeldstelle und einem Jobcenter, zunächst nur Statusabfrage und Anmeldung.
