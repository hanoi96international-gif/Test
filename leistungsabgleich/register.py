"""Fachlicher Kern: Fallregister, Abfrage mit Zweckbindung, Erstattungsansprüche, Protokoll."""

import datetime as dt
import hashlib
import hmac
import json
import re
import sqlite3
import unicodedata

ARTEN = {"jobcenter": "Jobcenter (SGB II)", "wohngeld": "Wohngeldstelle (WoGG)"}
STATUS = ("beantragt", "bewilligt", "abgelehnt", "eingestellt")
ANSPRUCH_STATUS = ("angemeldet", "anerkannt", "teilweise_anerkannt", "abgelehnt", "erledigt")

SCHEMA = """
CREATE TABLE IF NOT EXISTS faelle (
    behoerde TEXT NOT NULL, aktenzeichen TEXT NOT NULL, art TEXT NOT NULL,
    person TEXT NOT NULL, status TEXT NOT NULL, antrag_am TEXT,
    von TEXT, bis TEXT, monatsbetrag REAL, kontakt TEXT, geaendert TEXT NOT NULL,
    PRIMARY KEY (behoerde, aktenzeichen));
CREATE INDEX IF NOT EXISTS faelle_person ON faelle(person);
CREATE TABLE IF NOT EXISTS ansprueche (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    von_behoerde TEXT NOT NULL, von_aktenzeichen TEXT NOT NULL,
    an_behoerde TEXT NOT NULL, an_aktenzeichen TEXT NOT NULL,
    zeitraum_von TEXT NOT NULL, zeitraum_bis TEXT NOT NULL, betrag REAL,
    rechtsgrundlage TEXT NOT NULL, begruendung TEXT, status TEXT NOT NULL,
    antwort TEXT, anerkannter_betrag REAL, erstellt TEXT NOT NULL, geaendert TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS protokoll (
    zeit TEXT NOT NULL, behoerde TEXT NOT NULL, aktion TEXT NOT NULL,
    aktenzeichen TEXT, details TEXT);
"""


class Fehler(Exception):
    """Fachlicher Fehler, wird von der API als 4xx zurückgegeben."""

    def __init__(self, text: str, code: int = 400):
        super().__init__(text)
        self.code = code


def _norm(text: str) -> str:
    text = text.strip().lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(alt, neu)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", text)


def pseudonym(schluessel: bytes, nachname: str, vorname: str, geburtsdatum: str) -> str:
    """Gleiches Pseudonym bei beiden Behörden, ohne dass Klardaten das Register erreichen.

    Der Schlüssel liegt nur bei den beteiligten Behörden. Schreibweisen wie
    „Müller“/„Mueller“ oder „Anna-Lena“/„Anna Lena“ ergeben dasselbe Pseudonym.
    """
    dt.date.fromisoformat(geburtsdatum)  # wirft bei falschem Format
    nachricht = f"{_norm(nachname)}|{_norm(vorname)}|{geburtsdatum}".encode()
    return hmac.new(schluessel, nachricht, hashlib.sha256).hexdigest()


def _datum(wert, feld, pflicht=False):
    if wert in (None, ""):
        if pflicht:
            raise Fehler(f"Feld '{feld}' fehlt")
        return None
    try:
        return dt.date.fromisoformat(wert).isoformat()
    except (TypeError, ValueError):
        raise Fehler(f"Feld '{feld}' muss ein Datum JJJJ-MM-TT sein") from None


def _jetzt():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def laeuft(fall: dict, stichtag: dt.date) -> bool:
    if fall["status"] != "bewilligt" or not fall["von"]:
        return False
    return dt.date.fromisoformat(fall["von"]) <= stichtag and (
        not fall["bis"] or stichtag <= dt.date.fromisoformat(fall["bis"]))


def hinweise(eigene_art: str, fremde: list[dict], stichtag: dt.date) -> list[str]:
    """Kurze Entscheidungshilfe für Eilfälle. Ersetzt keine Prüfung im Einzelfall."""
    texte = []
    for f in fremde:
        if f["art"] == "wohngeld" and eigene_art == "jobcenter":
            if laeuft(f, stichtag):
                texte.append(
                    f"Wohngeld läuft ({f['von']} bis {f['bis'] or 'offen'}, {f['behoerde']}). Bei Bewilligung "
                    "von Bürgergeld entfällt der Wohngeldanspruch (§ 7 Abs. 1 WoGG): Wohngeldstelle "
                    "informieren und für Überschneidungsmonate Erstattung nach § 104 SGB X anmelden.")
            elif f["status"] == "beantragt":
                texte.append(
                    f"Wohngeld ist seit {f['antrag_am'] or 'unbekannt'} beantragt ({f['behoerde']}). Vorrang prüfen "
                    "(§ 12a SGB II): Reicht Wohngeld (ggf. mit Kinderzuschlag) zur Deckung, kann "
                    "Bürgergeld vorläufig bzw. bis zur Entscheidung gezahlt und Erstattung angemeldet werden.")
        if f["art"] == "jobcenter" and eigene_art == "wohngeld":
            if laeuft(f, stichtag):
                texte.append(
                    f"Bürgergeld läuft ({f['von']} bis {f['bis'] or 'offen'}, {f['behoerde']}). Wohngeld ist für "
                    "diesen Zeitraum in der Regel ausgeschlossen (§ 7 Abs. 1 Nr. 1 WoGG).")
            elif f["status"] == "beantragt":
                texte.append(
                    f"Bürgergeld ist seit {f['antrag_am'] or 'unbekannt'} beantragt ({f['behoerde']}). Mit dem "
                    "Jobcenter abstimmen; bei späterer Bewilligung Erstattung nach § 104 SGB X anmelden.")
            elif f["status"] == "eingestellt" and f["bis"]:
                texte.append(
                    f"Bürgergeld endete am {f['bis']}. Wohngeld ab dem Folgemonat möglich; "
                    "§ 7 Abs. 1 WoGG prüfen.")
    return texte


class Register:
    def __init__(self, pfad: str = ":memory:"):
        self.db = sqlite3.connect(pfad, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def _log(self, behoerde, aktion, aktenzeichen=None, **details):
        self.db.execute("INSERT INTO protokoll VALUES (?,?,?,?,?)",
                        (_jetzt(), behoerde, aktion, aktenzeichen, json.dumps(details, ensure_ascii=False)))

    def _eigener_fall(self, behoerde, aktenzeichen):
        row = self.db.execute("SELECT * FROM faelle WHERE behoerde=? AND aktenzeichen=?",
                              (behoerde, aktenzeichen)).fetchone()
        if not row:
            raise Fehler(f"Kein eigener Fall mit Aktenzeichen '{aktenzeichen}' gemeldet", 404)
        return dict(row)

    # --- Fälle melden -------------------------------------------------------------------------

    def melden(self, behoerde: str, art: str, daten: dict) -> dict:
        """Legt einen Fall an oder aktualisiert ihn (gleiche Behörde + Aktenzeichen)."""
        if art not in ARTEN:
            raise Fehler(f"Unbekannte Behördenart '{art}'")
        az = str(daten.get("aktenzeichen") or "").strip()
        person = str(daten.get("person") or "")
        if not az:
            raise Fehler("Feld 'aktenzeichen' fehlt")
        if not re.fullmatch(r"[0-9a-f]{64}", person):
            raise Fehler("Feld 'person' muss das Pseudonym (64 Hex-Zeichen) sein")
        status = daten.get("status")
        if status not in STATUS:
            raise Fehler(f"Feld 'status' muss einer von {', '.join(STATUS)} sein")
        von, bis = _datum(daten.get("von"), "von"), _datum(daten.get("bis"), "bis")
        if status == "bewilligt" and not von:
            raise Fehler("Bei 'bewilligt' ist 'von' Pflicht")
        if von and bis and bis < von:
            raise Fehler("'bis' liegt vor 'von'")
        betrag = daten.get("monatsbetrag")
        if betrag is not None and (not isinstance(betrag, (int, float)) or betrag < 0):
            raise Fehler("'monatsbetrag' muss eine Zahl ≥ 0 sein")
        fall = dict(behoerde=behoerde, aktenzeichen=az, art=art, person=person, status=status,
                    antrag_am=_datum(daten.get("antrag_am"), "antrag_am"), von=von, bis=bis,
                    monatsbetrag=betrag, kontakt=daten.get("kontakt"), geaendert=_jetzt())
        with self.db:
            self.db.execute(
                "INSERT INTO faelle VALUES (:behoerde,:aktenzeichen,:art,:person,:status,:antrag_am,"
                ":von,:bis,:monatsbetrag,:kontakt,:geaendert) ON CONFLICT(behoerde,aktenzeichen) DO UPDATE SET "
                "person=excluded.person,status=excluded.status,antrag_am=excluded.antrag_am,von=excluded.von,"
                "bis=excluded.bis,monatsbetrag=excluded.monatsbetrag,kontakt=excluded.kontakt,"
                "geaendert=excluded.geaendert", fall)
            self._log(behoerde, "melden", az, status=status)
        return fall

    # --- Abfrage ------------------------------------------------------------------------------

    def abfragen(self, behoerde: str, aktenzeichen: str, stichtag: str | None = None) -> dict:
        """Zeigt Fälle anderer Behörden zur Person des eigenen Falls.

        Zweckbindung: Abfragen geht nur über ein eigenes, gemeldetes Aktenzeichen. Damit kann
        niemand „einfach mal nachsehen“, und jede Abfrage steht mit Aktenzeichen im Protokoll.
        """
        try:
            eigen = self._eigener_fall(behoerde, aktenzeichen)
        except Fehler:
            with self.db:
                self._log(behoerde, "abfrage_abgelehnt", aktenzeichen)
            raise
        tag = dt.date.fromisoformat(_datum(stichtag, "stichtag") or dt.date.today().isoformat())
        rows = self.db.execute(
            "SELECT behoerde,aktenzeichen,art,status,antrag_am,von,bis,monatsbetrag,kontakt,geaendert "
            "FROM faelle WHERE person=? AND art<>? ORDER BY geaendert DESC",
            (eigen["person"], eigen["art"])).fetchall()
        fremde = [dict(r) | {"laeuft": laeuft(dict(r), tag)} for r in rows]
        with self.db:
            self._log(behoerde, "abfragen", aktenzeichen, treffer=len(fremde))
        return {"stichtag": tag.isoformat(), "faelle": fremde, "hinweise": hinweise(eigen["art"], fremde, tag)}

    # --- Erstattungsansprüche -----------------------------------------------------------------

    def anspruch_anmelden(self, behoerde: str, daten: dict) -> dict:
        eigen = self._eigener_fall(behoerde, daten.get("aktenzeichen"))
        ziel = self.db.execute(
            "SELECT * FROM faelle WHERE behoerde=? AND aktenzeichen=? AND person=?",
            (daten.get("an_behoerde"), daten.get("an_aktenzeichen"), eigen["person"])).fetchone()
        if not ziel:
            raise Fehler("Zielfall nicht gefunden oder betrifft eine andere Person", 404)
        von = _datum(daten.get("zeitraum_von"), "zeitraum_von", pflicht=True)
        bis = _datum(daten.get("zeitraum_bis"), "zeitraum_bis", pflicht=True)
        if bis < von:
            raise Fehler("'zeitraum_bis' liegt vor 'zeitraum_von'")
        betrag = daten.get("betrag")  # darf bei Anmeldung dem Grunde nach (§ 111 SGB X) noch fehlen
        if betrag is not None and (not isinstance(betrag, (int, float)) or betrag <= 0):
            raise Fehler("'betrag' muss eine positive Zahl sein")
        jetzt = _jetzt()
        with self.db:
            cur = self.db.execute(
                "INSERT INTO ansprueche (von_behoerde,von_aktenzeichen,an_behoerde,an_aktenzeichen,zeitraum_von,"
                "zeitraum_bis,betrag,rechtsgrundlage,begruendung,status,erstellt,geaendert) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (behoerde, eigen["aktenzeichen"], ziel["behoerde"], ziel["aktenzeichen"], von, bis, betrag,
                 daten.get("rechtsgrundlage") or "§ 104 SGB X", daten.get("begruendung"), "angemeldet", jetzt, jetzt))
            self._log(behoerde, "anspruch_anmelden", eigen["aktenzeichen"], anspruch=cur.lastrowid)
        return self.anspruch(behoerde, cur.lastrowid)

    def anspruch(self, behoerde: str, nr: int) -> dict:
        row = self.db.execute("SELECT * FROM ansprueche WHERE id=? AND (von_behoerde=? OR an_behoerde=?)",
                              (nr, behoerde, behoerde)).fetchone()
        if not row:
            raise Fehler("Erstattungsanspruch nicht gefunden", 404)
        return dict(row)

    def ansprueche(self, behoerde: str, richtung: str = "eingehend", status: str | None = None) -> list[dict]:
        spalte = {"eingehend": "an_behoerde", "ausgehend": "von_behoerde"}.get(richtung)
        if not spalte:
            raise Fehler("'richtung' muss eingehend oder ausgehend sein")
        sql, args = f"SELECT * FROM ansprueche WHERE {spalte}=?", [behoerde]
        if status:
            sql, args = sql + " AND status=?", args + [status]
        return [dict(r) for r in self.db.execute(sql + " ORDER BY id DESC", args)]

    def anspruch_beantworten(self, behoerde: str, nr: int, daten: dict) -> dict:
        a = self.anspruch(behoerde, nr)
        status = daten.get("status")
        if a["an_behoerde"] == behoerde:
            erlaubt = ("anerkannt", "teilweise_anerkannt", "abgelehnt")
        else:  # anmeldende Stelle darf beziffern oder als erledigt markieren (Zahlung eingegangen)
            erlaubt = ("angemeldet", "erledigt")
        if status not in erlaubt:
            raise Fehler(f"Status muss einer von {', '.join(erlaubt)} sein", 403 if status in ANSPRUCH_STATUS else 400)
        if status == "abgelehnt" and not daten.get("antwort"):
            raise Fehler("Ablehnung braucht eine Begründung in 'antwort'")
        felder = {"status": status, "geaendert": _jetzt()}
        if "antwort" in daten:
            felder["antwort"] = daten["antwort"]
        if status == "teilweise_anerkannt":
            if not isinstance(daten.get("anerkannter_betrag"), (int, float)):
                raise Fehler("Bei teilweiser Anerkennung ist 'anerkannter_betrag' Pflicht")
            felder["anerkannter_betrag"] = daten["anerkannter_betrag"]
        if status == "angemeldet" and isinstance(daten.get("betrag"), (int, float)):
            felder["betrag"] = daten["betrag"]
        with self.db:
            self.db.execute(f"UPDATE ansprueche SET {', '.join(k + '=?' for k in felder)} WHERE id=?",
                            [*felder.values(), nr])
            self._log(behoerde, "anspruch_" + status, None, anspruch=nr)
        return self.anspruch(behoerde, nr)

    def protokoll(self, behoerde: str) -> list[dict]:
        """Eigene Protokolleinträge (für Datenschutzbeauftragte und Auskunft nach Art. 15 DSGVO)."""
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM protokoll WHERE behoerde=? ORDER BY rowid DESC LIMIT 1000", (behoerde,))]
