"""Meldewerkzeug für den Pilotbetrieb ohne Fachverfahrensanbindung.

Liest eine CSV-Datei (Export aus dem Fachverfahren oder Excel), bildet die Pseudonyme lokal
mit dem gemeinsamen Schlüssel und meldet die Fälle an die Schnittstelle. Namen verlassen den
Rechner der Behörde nicht.

CSV (Trennzeichen ; oder ,  UTF-8, Excel-Export geht), eine Zeile je Fall und Monat:
  aktenzeichen;nachname;vorname;geburtsdatum;haushalt;status;antrag_am;bescheid_am;von;bis;kontakt;monat;anspruch;gezahlt
- Datumsangaben als TT.MM.JJJJ oder JJJJ-MM-TT, Monat als MM/JJJJ oder JJJJ-MM
- Beträge in Euro: 312,00 oder 1.234,56
- haushalt: weitere Personen als  Nachname,Vorname,TT.MM.JJJJ  getrennt durch |
- Fälle ohne Monatsbeträge (z. B. beantragt): eine Zeile mit leerem monat
Vorlage: docs/meldevorlage.csv
"""

import csv
import datetime as dt
import io
import json
import re
import ssl
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

from .register import STATUS, pseudonym

SPALTEN = ("aktenzeichen", "nachname", "vorname", "geburtsdatum", "haushalt", "status", "antrag_am", "bescheid_am",
           "von", "bis", "kontakt", "monat", "anspruch", "gezahlt")
FALLFELDER = ("nachname", "vorname", "geburtsdatum", "haushalt", "status", "antrag_am", "bescheid_am", "von", "bis",
              "kontakt")


class CsvFehler(Exception):
    pass


def datum(text: str, zeile: int, feld: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    raise CsvFehler(f"Zeile {zeile}: '{feld}' ist kein Datum: {text!r}")


def monat(text: str, zeile: int) -> str | None:
    text = (text or "").strip()
    if not text:
        return None
    m = re.fullmatch(r"(\d{1,2})[/.](\d{4})", text) or re.fullmatch(r"(\d{4})-(\d{2})", text)
    if not m:
        raise CsvFehler(f"Zeile {zeile}: Monat {text!r} bitte als MM/JJJJ")
    j, mo = (int(m[2]), int(m[1])) if "/" in text or "." in text else (int(m[1]), int(m[2]))
    if not 1 <= mo <= 12:
        raise CsvFehler(f"Zeile {zeile}: Monat {text!r} gibt es nicht")
    return f"{j:04d}-{mo:02d}"


def cent(text: str, zeile: int, feld: str) -> int:
    text = (text or "").strip().replace("€", "").replace(" ", "")
    if not text:
        return 0
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        wert = Decimal(text)
    except InvalidOperation:
        raise CsvFehler(f"Zeile {zeile}: '{feld}' ist kein Betrag: {text!r}") from None
    if wert < 0 or wert != wert.quantize(Decimal("0.01")):
        raise CsvFehler(f"Zeile {zeile}: '{feld}' muss ≥ 0 mit höchstens 2 Nachkommastellen sein")
    return int(wert * 100)


def lesen(text: str, schluessel: bytes) -> list[dict]:
    """CSV → Meldungen. Prüft alles, bevor etwas gesendet wird; Fehler nennen die Zeile."""
    text = text.lstrip("﻿")
    try:
        dialekt = csv.Sniffer().sniff(text.splitlines()[0], delimiters=";,")
    except (csv.Error, IndexError):
        raise CsvFehler("Datei ist leer oder kein CSV") from None
    leser = csv.DictReader(io.StringIO(text), dialect=dialekt)
    kopf = [k.strip().lower() for k in (leser.fieldnames or [])]
    fehlt = [s for s in SPALTEN if s not in kopf]
    if fehlt:
        raise CsvFehler(f"Spalten fehlen: {', '.join(fehlt)}")
    leser.fieldnames = kopf
    faelle, erste = {}, {}
    for nr, z in enumerate(leser, start=2):
        z = {k: (v or "").strip() for k, v in z.items() if k}
        if not any(z.values()):
            continue
        az = z["aktenzeichen"]
        if not az:
            raise CsvFehler(f"Zeile {nr}: aktenzeichen fehlt")
        kern = tuple(z[f] for f in FALLFELDER)
        if az not in faelle:
            if z["status"] not in STATUS:
                raise CsvFehler(f"Zeile {nr}: status muss einer von {', '.join(STATUS)} sein")
            if not (z["nachname"] and z["vorname"]):
                raise CsvFehler(f"Zeile {nr}: nachname und vorname nötig")
            geb = datum(z["geburtsdatum"], nr, "geburtsdatum")
            if not geb:
                raise CsvFehler(f"Zeile {nr}: geburtsdatum fehlt")
            haushalt = []
            for teil in filter(None, (t.strip() for t in z["haushalt"].split("|"))):
                stuecke = [s.strip() for s in teil.split(",")]
                if len(stuecke) != 3:
                    raise CsvFehler(f"Zeile {nr}: haushalt-Eintrag {teil!r} bitte als Nachname,Vorname,TT.MM.JJJJ")
                haushalt.append(pseudonym(schluessel, stuecke[0], stuecke[1], datum(stuecke[2], nr, "haushalt")))
            faelle[az] = {"aktenzeichen": az, "person": pseudonym(schluessel, z["nachname"], z["vorname"], geb),
                          "haushalt": haushalt, "status": z["status"],
                          "antrag_am": datum(z["antrag_am"], nr, "antrag_am"),
                          "bescheid_am": datum(z["bescheid_am"], nr, "bescheid_am"),
                          "von": datum(z["von"], nr, "von"), "bis": datum(z["bis"], nr, "bis"),
                          "kontakt": z["kontakt"] or None, "monate": []}
            erste[az] = (nr, kern)
        elif kern != erste[az][1]:
            raise CsvFehler(f"Zeile {nr}: Falldaten zu {az} weichen von Zeile {erste[az][0]} ab")
        m = monat(z["monat"], nr)
        if m:
            if any(e["monat"] == m for e in faelle[az]["monate"]):
                raise CsvFehler(f"Zeile {nr}: Monat {m} für {az} doppelt")
            faelle[az]["monate"].append({"monat": m, "anspruch_cent": cent(z["anspruch"], nr, "anspruch"),
                                         "gezahlt_cent": cent(z["gezahlt"], nr, "gezahlt")})
    if not faelle:
        raise CsvFehler("Keine Fälle in der Datei")
    return list(faelle.values())


def senden(meldungen: list[dict], url: str, api_key: str, bearbeiter: str | None = None,
           ca: str | None = None) -> list[dict]:
    ctx = ssl.create_default_context(cafile=ca) if url.startswith("https") else None
    ergebnisse = []
    for m in meldungen:
        kopf = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if bearbeiter:
            kopf["X-Bearbeiter"] = bearbeiter
        req = urllib.request.Request(url.rstrip("/") + "/faelle", method="PUT", headers=kopf,
                                     data=json.dumps(m).encode())
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                ergebnisse.append({"aktenzeichen": m["aktenzeichen"], "ok": True} | json.load(r))
        except urllib.error.HTTPError as e:
            try:
                text = json.load(e).get("fehler", str(e))
            except (ValueError, AttributeError):
                text = str(e)
            ergebnisse.append({"aktenzeichen": m["aktenzeichen"], "ok": False, "fehler": text})
    return ergebnisse
