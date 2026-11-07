"""Speicher und Ablauf: Fälle melden, Erstattungen automatisch anlegen, Arbeitskorb, Protokoll."""

import datetime as dt
import hashlib
import hmac
import json
import re
import sqlite3
import unicodedata

from . import erstattung as er

STATUS = ("beantragt", "bewilligt", "abgelehnt", "eingestellt")
PSEUDONYM_RE = re.compile(r"[0-9a-f]{64}")
MONAT_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])")

SCHEMA = """
CREATE TABLE IF NOT EXISTS faelle (
    behoerde TEXT NOT NULL, aktenzeichen TEXT NOT NULL, art TEXT NOT NULL, person TEXT NOT NULL,
    haushalt TEXT NOT NULL, status TEXT NOT NULL, antrag_am TEXT, bescheid_am TEXT, von TEXT, bis TEXT,
    monate TEXT NOT NULL, kontakt TEXT, geaendert TEXT NOT NULL,
    PRIMARY KEY (behoerde, aktenzeichen));
CREATE TABLE IF NOT EXISTS mitglieder (
    behoerde TEXT NOT NULL, aktenzeichen TEXT NOT NULL, person TEXT NOT NULL,
    PRIMARY KEY (behoerde, aktenzeichen, person));
CREATE INDEX IF NOT EXISTS mitglieder_person ON mitglieder(person);
CREATE TABLE IF NOT EXISTS erstattungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    berechtigt TEXT NOT NULL, berechtigt_az TEXT NOT NULL, berechtigt_art TEXT NOT NULL,
    verpflichtet TEXT NOT NULL, verpflichtet_az TEXT NOT NULL, rechtsgrundlage TEXT NOT NULL,
    status TEXT NOT NULL, positionen TEXT NOT NULL, pruefhinweise TEXT NOT NULL DEFAULT '[]',
    korrektur TEXT NOT NULL DEFAULT '[]', anerkannt_cent INTEGER, begruendung TEXT,
    automatisch INTEGER NOT NULL DEFAULT 0, angemeldet TEXT NOT NULL, geaendert TEXT NOT NULL,
    gefordert_cent INTEGER);
CREATE INDEX IF NOT EXISTS erstattungen_v ON erstattungen(verpflichtet, verpflichtet_az);
CREATE INDEX IF NOT EXISTS erstattungen_b ON erstattungen(berechtigt, berechtigt_az);
CREATE TABLE IF NOT EXISTS protokoll (
    zeit TEXT NOT NULL, behoerde TEXT NOT NULL, aktion TEXT NOT NULL, aktenzeichen TEXT, details TEXT,
    bearbeiter TEXT);
CREATE INDEX IF NOT EXISTS protokoll_behoerde ON protokoll(behoerde, zeit);
CREATE TABLE IF NOT EXISTS feedback (
    zeit TEXT NOT NULL, behoerde TEXT NOT NULL, bearbeiter TEXT, seite TEXT, text TEXT NOT NULL);
"""

# Schrittweise Änderungen an bestehenden Datenbanken. Index = Zielversion - 2 (Version 1 = Stand 2.0).
MIGRATIONEN = [
    """ALTER TABLE protokoll ADD COLUMN bearbeiter TEXT;
       CREATE INDEX IF NOT EXISTS protokoll_behoerde ON protokoll(behoerde, zeit);
       CREATE TABLE IF NOT EXISTS feedback (
           zeit TEXT NOT NULL, behoerde TEXT NOT NULL, bearbeiter TEXT, seite TEXT, text TEXT NOT NULL);""",
    # 3: ursprüngliche Forderung bleibt bei Teilanerkennung sichtbar
    "ALTER TABLE erstattungen ADD COLUMN gefordert_cent INTEGER;",
]
SCHEMA_VERSION = len(MIGRATIONEN) + 1


class Fehler(Exception):
    """Fachlicher Fehler, die API gibt ihn mit passendem HTTP-Status zurück."""

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
    """Gleiches Pseudonym bei beiden Behörden, ohne dass Namen das Register erreichen.

    Der Schlüssel liegt nur bei den Fachverfahren der Behörden, nicht beim Register.
    „Müller“/„Mueller“ und „Anna-Lena“/„Anna Lena“ ergeben dasselbe Pseudonym.
    """
    dt.date.fromisoformat(geburtsdatum)
    nachricht = f"{_norm(nachname)}|{_norm(vorname)}|{geburtsdatum}".encode()
    return hmac.new(schluessel, nachricht, hashlib.sha256).hexdigest()


def _datum(wert, feld):
    if wert in (None, ""):
        return None
    try:
        return dt.date.fromisoformat(wert).isoformat()
    except (TypeError, ValueError):
        raise Fehler(f"'{feld}' muss ein Datum JJJJ-MM-TT sein") from None


def _cent(wert, feld):
    if isinstance(wert, bool) or not isinstance(wert, int) or wert < 0:
        raise Fehler(f"'{feld}' muss ein ganzzahliger Cent-Betrag ≥ 0 sein")
    return wert


def _jetzt():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _monate_zurueck(tag: dt.date, n: int) -> str:
    j, m = divmod(tag.year * 12 + tag.month - 1 - n, 12)
    return dt.date(j, m + 1, 1).isoformat()


class Register:
    def __init__(self, pfad: str = ":memory:", behoerden: dict | None = None):
        """behoerden: {id: {"art", "name", "auto_anerkennung_bis_cent"}}"""
        self.behoerden = behoerden or {}
        self.db = sqlite3.connect(pfad, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        if pfad != ":memory:":
            self.db.execute("PRAGMA journal_mode = WAL")  # Lesen blockiert Schreiben nicht, robust bei Absturz
        self.db.execute("PRAGMA synchronous = NORMAL")
        self._migrieren()

    def _migrieren(self):
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        neu = not self.db.execute("SELECT 1 FROM sqlite_master WHERE name='faelle'").fetchone()
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"Datenbank hat Version {version}, dieses Programm kennt nur {SCHEMA_VERSION}")
        with self.db:
            if neu:
                self.db.executescript(SCHEMA)
            else:
                for nr in range(max(version, 1), SCHEMA_VERSION):
                    self.db.executescript(MIGRATIONEN[nr - 1])
            self.db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def name(self, behoerde: str) -> str:
        return self.behoerden.get(behoerde, {}).get("name", behoerde)

    def _log(self, behoerde, aktion, aktenzeichen=None, bearbeiter=None, **details):
        self.db.execute("INSERT INTO protokoll (zeit,behoerde,aktion,aktenzeichen,details,bearbeiter) "
                        "VALUES (?,?,?,?,?,?)", (_jetzt(), behoerde, aktion, aktenzeichen,
                                                 json.dumps(details, ensure_ascii=False), bearbeiter))

    # --- Laden --------------------------------------------------------------------------------

    @staticmethod
    def _zu_fall(row):
        f = dict(row)
        f["monate"], f["haushalt"] = json.loads(f["monate"]), json.loads(f["haushalt"])
        return f

    @staticmethod
    def _zu_erstattung(row):
        e = dict(row)
        for k in ("positionen", "pruefhinweise", "korrektur"):
            e[k] = json.loads(e[k])
        e["automatisch"] = bool(e["automatisch"])
        return e

    def _fall(self, behoerde, az):
        row = self.db.execute("SELECT * FROM faelle WHERE behoerde=? AND aktenzeichen=?", (behoerde, az)).fetchone()
        return self._zu_fall(row) if row else None

    def _eigener_fall(self, behoerde, az):
        fall = self._fall(behoerde, str(az or ""))
        if not fall:
            raise Fehler(f"Kein eigener Fall mit Aktenzeichen '{az}' gemeldet", 404)
        return fall

    def _partner(self, fall):
        """Fälle der anderen Behördenart, die mindestens eine Person mit diesem Fall teilen."""
        platz = ",".join("?" * len(fall["haushalt"]))
        rows = self.db.execute(
            f"SELECT DISTINCT f.* FROM faelle f JOIN mitglieder m ON m.behoerde=f.behoerde AND "
            f"m.aktenzeichen=f.aktenzeichen WHERE m.person IN ({platz}) AND f.art<>? ORDER BY f.geaendert DESC",
            [*fall["haushalt"], fall["art"]])
        return [self._zu_fall(r) for r in rows]

    def _erstattungen_paar(self, jc, wg):
        rows = self.db.execute(
            "SELECT * FROM erstattungen WHERE (berechtigt=? AND berechtigt_az=? AND verpflichtet=? AND "
            "verpflichtet_az=?) OR (berechtigt=? AND berechtigt_az=? AND verpflichtet=? AND verpflichtet_az=?) "
            "ORDER BY id", (jc["behoerde"], jc["aktenzeichen"], wg["behoerde"], wg["aktenzeichen"],
                            wg["behoerde"], wg["aktenzeichen"], jc["behoerde"], jc["aktenzeichen"]))
        return [self._zu_erstattung(r) for r in rows]

    def _aussen(self, e):
        """Erstattung für die Ausgabe: mit Summe, Zeitraum und Behördennamen."""
        return e | {"summe_cent": er.summe(e["positionen"]), "zeitraum": er.zeitraum(e["positionen"]),
                    "hoechstens_cent": sum(p["hoechstens"] for p in e["positionen"].values()),
                    "berechtigt_name": self.name(e["berechtigt"]), "verpflichtet_name": self.name(e["verpflichtet"])}

    # --- Fälle melden -------------------------------------------------------------------------

    def melden(self, behoerde: str, art: str, daten: dict, bearbeiter: str | None = None) -> dict:
        """Legt einen Fall an oder ersetzt ihn vollständig (gleiche Behörde + Aktenzeichen).

        Das Fachverfahren schickt bei jeder Änderung den aktuellen Stand, inklusive Monatsbeträgen.
        Die Antwort sagt sofort, was vor der Auszahlung einzubehalten ist.
        """
        if art not in er.ARTEN:
            raise Fehler(f"Unbekannte Behördenart '{art}'")
        az = str(daten.get("aktenzeichen") or "").strip()
        if not az or len(az) > 64:
            raise Fehler("'aktenzeichen' fehlt oder ist zu lang")
        person = daten.get("person")
        haushalt = daten.get("haushalt") or []
        if not isinstance(haushalt, list):
            raise Fehler("'haushalt' muss eine Liste von Pseudonymen sein")
        for p in [person, *haushalt]:
            if not isinstance(p, str) or not PSEUDONYM_RE.fullmatch(p):
                raise Fehler("'person' und 'haushalt' müssen Pseudonyme (64 Hex-Zeichen) sein")
        status = daten.get("status")
        if status not in STATUS:
            raise Fehler(f"'status' muss einer von {', '.join(STATUS)} sein")
        von, bis = _datum(daten.get("von"), "von"), _datum(daten.get("bis"), "bis")
        if status == "bewilligt" and not von:
            raise Fehler("Bei 'bewilligt' ist 'von' Pflicht")
        if von and bis and bis < von:
            raise Fehler("'bis' liegt vor 'von'")
        monate = {}
        eintraege = daten.get("monate") or []
        if not isinstance(eintraege, list) or len(eintraege) > 120:
            raise Fehler("'monate' muss eine Liste mit höchstens 120 Einträgen sein")
        for e in eintraege:
            if not isinstance(e, dict) or not MONAT_RE.fullmatch(str(e.get("monat", ""))):
                raise Fehler("Jeder Eintrag in 'monate' braucht 'monat' im Format JJJJ-MM")
            if e["monat"] in monate:
                raise Fehler(f"Monat {e['monat']} ist doppelt gemeldet")
            monate[e["monat"]] = {"anspruch": _cent(e.get("anspruch_cent", 0), "anspruch_cent"),
                                  "gezahlt": _cent(e.get("gezahlt_cent", 0), "gezahlt_cent")}
        fall = dict(behoerde=behoerde, aktenzeichen=az, art=art, person=person, haushalt=sorted({person, *haushalt}),
                    status=status, antrag_am=_datum(daten.get("antrag_am"), "antrag_am"),
                    bescheid_am=_datum(daten.get("bescheid_am"), "bescheid_am"), von=von, bis=bis,
                    monate=dict(sorted(monate.items())), kontakt=str(daten.get("kontakt") or "")[:200] or None,
                    geaendert=_jetzt())
        alt = self._fall(behoerde, az)
        if alt and alt["art"] != art:
            raise Fehler("Aktenzeichen gehört zu einer anderen Behördenart", 409)
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO faelle VALUES (:behoerde,:aktenzeichen,:art,:person,:haushalt,:status,"
                ":antrag_am,:bescheid_am,:von,:bis,:monate,:kontakt,:geaendert)",
                fall | {"haushalt": json.dumps(fall["haushalt"]), "monate": json.dumps(fall["monate"])})
            self.db.execute("DELETE FROM mitglieder WHERE behoerde=? AND aktenzeichen=?", (behoerde, az))
            self.db.executemany("INSERT INTO mitglieder VALUES (?,?,?)", [(behoerde, az, p) for p in fall["haushalt"]])
            self._log(behoerde, "melden", az, bearbeiter, status=status, monate=len(monate))
            self._neu_berechnen(fall)
        return {"aktenzeichen": az, "einbehalten": self.einbehalten(behoerde, az),
                "aufgaben": self.arbeitskorb(behoerde, az, protokollieren=False)}

    def _neu_berechnen(self, fall):
        schluessel = (fall["behoerde"], fall["aktenzeichen"])
        partner = set()
        for p in self._partner(fall):
            partner.add((p["behoerde"], p["aktenzeichen"]))
            self._paar_berechnen(*((fall, p) if fall["art"] == er.JC else (p, fall)))
        # Betrifft ein Partnerfall nach einer Korrektur nicht mehr dieselben Personen, entfällt die offene Forderung
        rows = self.db.execute("SELECT * FROM erstattungen WHERE (berechtigt=? AND berechtigt_az=?) OR "
                               "(verpflichtet=? AND verpflichtet_az=?)", schluessel * 2).fetchall()
        for e in map(self._zu_erstattung, rows):
            gegen = {(e["berechtigt"], e["berechtigt_az"]), (e["verpflichtet"], e["verpflichtet_az"])} - {schluessel}
            if e["status"] in er.OFFEN and not gegen & partner:
                self.db.execute("DELETE FROM erstattungen WHERE id=?", (e["id"],))
                self._log(e["berechtigt"], "erstattung_entfallen", e["berechtigt_az"], erstattung=e["id"])

    def _paar_berechnen(self, jc, wg):
        bestehend = self._erstattungen_paar(jc, wg)
        erg = er.auswerten({er.JC: jc, er.WG: wg}, bestehend)
        hinweise_paar = []
        if set(jc["haushalt"]) != set(wg["haushalt"]):
            hinweise_paar.append("Wohngeld-Haushalt und Bedarfsgemeinschaft sind nicht deckungsgleich, "
                                 "deshalb Beträge von Hand nachrechnen.")
        jetzt = _jetzt()
        for d in (er.JC, er.WG):
            x, y = (jc, wg) if d == er.JC else (wg, jc)
            pos = erg["soll"][d]
            offen = next((e for e in bestehend if e["berechtigt_art"] == d and e["status"] in er.OFFEN), None)
            if not pos:
                if offen:
                    self.db.execute("DELETE FROM erstattungen WHERE id=?", (offen["id"],))
                    self._log(x["behoerde"], "erstattung_entfallen", x["aktenzeichen"], erstattung=offen["id"])
                continue
            hinweise = list(hinweise_paar)
            unklar = [m for m in erg["unklar"] if m in pos]
            if unklar:
                hinweise.append(f"In {er.zeitraum(unklar)} haben beide Stellen gezahlt und haben noch offene "
                                "Beträge, deshalb die Richtung der Erstattung klären.")
            betrag, auto = er.summe(pos), False
            if any(p["betrag"] is None for p in pos.values()):
                status = "angemeldet"
            elif hinweise:
                status = "pruefung"
            else:
                status = "beziffert"
                grenze = self.behoerden.get(y["behoerde"], {}).get("auto_anerkennung_bis_cent")
                if grenze is not None and betrag <= grenze:
                    status, auto = "anerkannt", True
            werte = {"status": status, "positionen": json.dumps(pos, sort_keys=True),
                     "pruefhinweise": json.dumps(hinweise, ensure_ascii=False),
                     "anerkannt_cent": betrag if auto else None, "automatisch": int(auto)}
            if offen:
                vorher = {"status": offen["status"], "positionen": json.dumps(offen["positionen"], sort_keys=True),
                          "pruefhinweise": json.dumps(offen["pruefhinweise"], ensure_ascii=False),
                          "anerkannt_cent": offen["anerkannt_cent"], "automatisch": int(offen["automatisch"])}
                if vorher != werte:
                    self.db.execute(f"UPDATE erstattungen SET {', '.join(k + '=?' for k in werte)}, geaendert=? "
                                    "WHERE id=?", [*werte.values(), jetzt, offen["id"]])
                    self._log(x["behoerde"], "erstattung_" + status, x["aktenzeichen"], erstattung=offen["id"],
                              betrag_cent=betrag, automatisch=auto)
            else:
                cur = self.db.execute(
                    "INSERT INTO erstattungen (berechtigt,berechtigt_az,berechtigt_art,verpflichtet,verpflichtet_az,"
                    "rechtsgrundlage,status,positionen,pruefhinweise,anerkannt_cent,automatisch,angemeldet,geaendert) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (x["behoerde"], x["aktenzeichen"], d, y["behoerde"], y["aktenzeichen"], er.RECHTSGRUNDLAGE[d],
                     *werte.values(), jetzt, jetzt))
                self._log(x["behoerde"], "erstattung_" + status, x["aktenzeichen"], erstattung=cur.lastrowid,
                          betrag_cent=betrag, automatisch=auto)
        for e in bestehend:
            if e["status"] in er.BINDEND and erg["korrektur"].get(e["id"], []) != e["korrektur"]:
                self.db.execute("UPDATE erstattungen SET korrektur=? WHERE id=?",
                                (json.dumps(erg["korrektur"].get(e["id"], [])), e["id"]))

    # --- Lesen --------------------------------------------------------------------------------

    def einbehalten(self, behoerde: str, az: str) -> list[dict]:
        """Was das Fachverfahren vor der Auszahlung an den Bürger zurückhalten muss."""
        rows = self.db.execute("SELECT * FROM erstattungen WHERE verpflichtet=? AND verpflichtet_az=? AND "
                               "status<>'abgelehnt' ORDER BY id", (behoerde, az))
        return [{"monat": m, "betrag_cent": p["betrag"], "hoechstens_cent": p["hoechstens"], "an": e["berechtigt"],
                 "erstattung": e["id"], "status": e["status"]}
                for e in map(self._zu_erstattung, rows) for m, p in sorted(e["positionen"].items())]

    def abfragen(self, behoerde: str, az: str, stichtag: str | None = None, bearbeiter: str | None = None) -> dict:
        """Was läuft bei der anderen Stelle zu den Personen dieses Falls?

        Zweckbindung: nur über ein eigenes, gemeldetes Aktenzeichen. Jede Abfrage wird protokolliert,
        auch abgelehnte.
        """
        try:
            eigen = self._eigener_fall(behoerde, az)
        except Fehler:
            with self.db:
                self._log(behoerde, "abfrage_abgelehnt", az, bearbeiter)
            raise
        tag = dt.date.fromisoformat(_datum(stichtag, "stichtag") or dt.date.today().isoformat())
        monat, faelle, hinweise = tag.isoformat()[:7], [], []
        for p in self._partner(eigen):
            laeuft = p["status"] == "bewilligt" and p["von"] <= tag.isoformat() and (not p["bis"] or tag.isoformat() <= p["bis"])
            faelle.append({k: p[k] for k in ("behoerde", "aktenzeichen", "art", "status", "antrag_am", "bescheid_am",
                                             "von", "bis", "kontakt")}
                          | {"name": self.name(p["behoerde"]), "laeuft": laeuft,
                             "anspruch_aktuell_cent": p["monate"].get(monat, er.LEER)["anspruch"],
                             "gemeinsame_personen": len(set(p["haushalt"]) & set(eigen["haushalt"]))})
            if p["status"] == "beantragt" and eigen["art"] == er.JC:
                hinweise.append(f"Wohngeld ist seit {p['antrag_am'] or '?'} beantragt ({self.name(p['behoerde'])}). "
                                "Bürgergeld kann bis zur Entscheidung gezahlt werden. Der Erstattungsanspruch wird "
                                "automatisch angemeldet (§§ 104, 111 SGB X).")
            elif p["status"] == "beantragt":
                hinweise.append(f"Bürgergeld ist seit {p['antrag_am'] or '?'} beantragt ({self.name(p['behoerde'])}). "
                                "Bei Bewilligung entfällt das Wohngeld (§ 7 WoGG). Bereits gezahltes Wohngeld wird "
                                "automatisch zur Erstattung angemeldet (§ 103 SGB X).")
        with self.db:
            self._log(behoerde, "abfragen", az, bearbeiter, treffer=len(faelle))
        return {"stichtag": tag.isoformat(), "faelle": faelle, "hinweise": hinweise,
                "aufgaben": self.arbeitskorb(behoerde, az, protokollieren=False)}

    def arbeitskorb(self, behoerde: str, az: str | None = None, protokollieren: bool = True,
                    bearbeiter: str | None = None) -> list[dict]:
        """Alle offenen Aufgaben der Behörde, dringende zuerst. Erledigt sich durch neue Meldungen von selbst."""
        sql, args = "SELECT * FROM faelle WHERE behoerde=?", [behoerde]
        if az is not None:
            sql, args = sql + " AND aktenzeichen=?", args + [az]
        aufgaben = []
        for fall in map(self._zu_fall, self.db.execute(sql, args).fetchall()):
            for p in self._partner(fall):
                jc, wg = (fall, p) if fall["art"] == er.JC else (p, fall)
                aufgaben += [a for a in er.aufgaben_paar(jc, wg, self._erstattungen_paar(jc, wg), self.name)
                             if a["behoerde"] == behoerde]
        sql, args = "SELECT * FROM erstattungen WHERE verpflichtet=? AND status IN (?,?,?,?,?)", \
            [behoerde, *er.OFFEN, "anerkannt", "teilweise_anerkannt"]
        if az is not None:
            sql, args = sql + " AND verpflichtet_az=?", args + [az]
        for e in map(self._zu_erstattung, self.db.execute(sql, args).fetchall()):
            aufgaben += er.aufgaben_erstattung(e, self.name)
        sql = "SELECT * FROM erstattungen WHERE verpflichtet=? AND status='erstattet' AND korrektur<>'[]'"
        for e in map(self._zu_erstattung, self.db.execute(sql, (behoerde,)).fetchall()):
            if az is None or e["verpflichtet_az"] == az:
                aufgaben += er.aufgaben_erstattung(e, self.name)
        for a in aufgaben:
            a["partner_name"] = self.name(a["partner"]) if a["partner"] else None
        if protokollieren:
            with self.db:
                self._log(behoerde, "arbeitskorb", az, bearbeiter, aufgaben=len(aufgaben))
        return sorted(aufgaben, key=lambda a: (a["prioritaet"], a["aktenzeichen"]))

    def erstattung(self, behoerde: str, nr: int) -> dict:
        row = self.db.execute("SELECT * FROM erstattungen WHERE id=? AND (berechtigt=? OR verpflichtet=?)",
                              (nr, behoerde, behoerde)).fetchone()
        if not row:
            raise Fehler("Erstattung nicht gefunden", 404)
        return self._aussen(self._zu_erstattung(row))

    def erstattungen(self, behoerde: str, richtung: str = "eingehend", status: str | None = None) -> list[dict]:
        """eingehend = Forderungen an mich, ausgehend = meine Forderungen."""
        spalte = {"eingehend": "verpflichtet", "ausgehend": "berechtigt"}.get(richtung)
        if not spalte:
            raise Fehler("'richtung' muss eingehend oder ausgehend sein")
        sql, args = f"SELECT * FROM erstattungen WHERE {spalte}=?", [behoerde]
        if status:
            sql, args = sql + " AND status=?", args + [status]
        return [self._aussen(self._zu_erstattung(r)) for r in self.db.execute(sql + " ORDER BY id DESC", args)]

    # --- Entscheiden --------------------------------------------------------------------------

    def entscheiden(self, behoerde: str, nr: int, daten: dict, bearbeiter: str | None = None) -> dict:
        e = self.erstattung(behoerde, nr)
        if e["verpflichtet"] != behoerde:
            raise Fehler("Nur die erstattungspflichtige Stelle entscheidet", 403)
        if e["status"] not in ("beziffert", "pruefung"):
            raise Fehler(f"Erstattung ist im Status '{e['status']}' und kann nicht entschieden werden", 409)
        art, begruendung = daten.get("entscheidung"), str(daten.get("begruendung") or "").strip()[:1000]
        pos = e["positionen"]
        if art == "anerkennen":
            status = "anerkannt"
        elif art in ("teilweise", "ablehnen"):
            if not begruendung:
                raise Fehler("Teilanerkennung und Ablehnung brauchen eine 'begruendung'")
            if art == "teilweise":
                try:
                    pos = er.kuerzen(pos, _cent(daten.get("betrag_cent"), "betrag_cent"))
                except ValueError as fehler:
                    raise Fehler(str(fehler)) from None
            status = "teilweise_anerkannt" if art == "teilweise" else "abgelehnt"
        else:
            raise Fehler("'entscheidung' muss anerkennen, teilweise oder ablehnen sein")
        with self.db:
            self.db.execute("UPDATE erstattungen SET status=?, positionen=?, anerkannt_cent=?, begruendung=?, "
                            "gefordert_cent=?, geaendert=? WHERE id=?",
                            (status, json.dumps(pos, sort_keys=True), 0 if status == "abgelehnt" else er.summe(pos),
                             begruendung or None, er.summe(e["positionen"]), _jetzt(), nr))
            self._log(behoerde, "erstattung_" + status, e["verpflichtet_az"], bearbeiter, erstattung=nr)
        return self.erstattung(behoerde, nr)

    def als_erstattet(self, behoerde: str, nr: int, bearbeiter: str | None = None) -> dict:
        e = self.erstattung(behoerde, nr)
        if e["verpflichtet"] != behoerde:
            raise Fehler("Nur die erstattungspflichtige Stelle meldet die Zahlung", 403)
        if e["status"] not in ("anerkannt", "teilweise_anerkannt"):
            raise Fehler(f"Erstattung ist im Status '{e['status']}', erst anerkennen", 409)
        with self.db:
            self.db.execute("UPDATE erstattungen SET status='erstattet', geaendert=? WHERE id=?", (_jetzt(), nr))
            self._log(behoerde, "erstattung_erstattet", e["verpflichtet_az"], bearbeiter, erstattung=nr)
        return self.erstattung(behoerde, nr)

    # --- Pilotbetrieb ---------------------------------------------------------------------------

    def kennzahlen(self, behoerde: str) -> dict:
        """Zahlen für die Auswertung des Pilotbetriebs, aus Sicht einer Behörde."""
        def je_status(spalte):
            rows = self.db.execute(f"SELECT status, count(*) n, coalesce(sum(anerkannt_cent),0) s FROM erstattungen "
                                   f"WHERE {spalte}=? GROUP BY status", (behoerde,))
            return {r["status"]: {"anzahl": r["n"], "anerkannt_cent": r["s"]} for r in rows}

        def tage(spalte):
            r = self.db.execute(
                f"SELECT avg(julianday(geaendert) - julianday(angemeldet)) d, count(*) n FROM erstattungen "
                f"WHERE {spalte}=? AND status='erstattet'", (behoerde,)).fetchone()
            return round(r["d"], 1) if r["d"] is not None else None

        auto = self.db.execute("SELECT count(*) FROM erstattungen WHERE verpflichtet=? AND automatisch=1",
                               (behoerde,)).fetchone()[0]
        entschieden = self.db.execute(
            "SELECT count(*) FROM erstattungen WHERE verpflichtet=? AND status IN ('anerkannt','teilweise_anerkannt',"
            "'erstattet','abgelehnt')", (behoerde,)).fetchone()[0]
        aufgaben = {}
        for a in self.arbeitskorb(behoerde, protokollieren=False):
            aufgaben[a["typ"]] = aufgaben.get(a["typ"], 0) + 1
        seit = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat(timespec="seconds")
        abfragen = self.db.execute("SELECT count(*) FROM protokoll WHERE behoerde=? AND aktion='abfragen' AND zeit>=?",
                                   (behoerde, seit)).fetchone()[0]
        return {
            "faelle": self.db.execute("SELECT count(*) FROM faelle WHERE behoerde=?", (behoerde,)).fetchone()[0],
            "forderungen_an_uns": je_status("verpflichtet"), "unsere_forderungen": je_status("berechtigt"),
            "automatisch_anerkannt": auto, "entschieden": entschieden,
            "tage_bis_erstattung": {"an_uns": tage("verpflichtet"), "unsere": tage("berechtigt")},
            "offene_aufgaben": aufgaben, "abfragen_30_tage": abfragen,
        }

    def feedback(self, behoerde: str, text: str, seite: str | None = None, bearbeiter: str | None = None) -> dict:
        text = str(text or "").strip()
        if not 3 <= len(text) <= 2000:
            raise Fehler("Feedback muss 3 bis 2000 Zeichen lang sein")
        with self.db:
            self.db.execute("INSERT INTO feedback VALUES (?,?,?,?,?)",
                            (_jetzt(), behoerde, bearbeiter, str(seite or "")[:40] or None, text))
        return {"danke": True}

    def feedback_liste(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM feedback ORDER BY zeit DESC")]

    def sicherung(self, ziel: str) -> None:
        """Konsistente Kopie im laufenden Betrieb (sqlite-Backup-API)."""
        with sqlite3.connect(ziel) as kopie:
            self.db.backup(kopie)
        kopie.close()

    # --- Datenschutz --------------------------------------------------------------------------

    def protokoll(self, behoerde: str, limit: int = 500) -> list[dict]:
        """Eigene Protokolleinträge, z. B. für Datenschutzbeauftragte und Auskunft nach Art. 15 DSGVO."""
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM protokoll WHERE behoerde=? ORDER BY rowid DESC LIMIT ?", (behoerde, limit))]

    def aufraeumen(self, stichtag: str | None = None, faelle_monate: int = 24, erstattungen_monate: int = 48,
                   protokoll_monate: int = 24) -> dict:
        """Löscht nach Fristen: abgeschlossene Erstattungen (Verjährung § 113 SGB X: 4 Jahre),
        Fälle ohne offene Erstattung, Protokolle. Fristen bitte mit dem Datenschutz abstimmen."""
        tag = dt.date.fromisoformat(stichtag) if stichtag else dt.date.today()
        g_e, g_f, g_p = (_monate_zurueck(tag, n) for n in (erstattungen_monate, faelle_monate, protokoll_monate))
        with self.db:
            n_e = self.db.execute("DELETE FROM erstattungen WHERE status IN ('erstattet','abgelehnt') AND geaendert<?",
                                  (g_e,)).rowcount
            n_f = self.db.execute(
                "DELETE FROM faelle WHERE geaendert<? AND coalesce(bis, von, antrag_am, '0000')<? AND NOT EXISTS "
                "(SELECT 1 FROM erstattungen e WHERE (e.berechtigt=faelle.behoerde AND e.berechtigt_az=faelle.aktenzeichen) "
                "OR (e.verpflichtet=faelle.behoerde AND e.verpflichtet_az=faelle.aktenzeichen))", (g_f, g_f)).rowcount
            self.db.execute("DELETE FROM mitglieder WHERE NOT EXISTS (SELECT 1 FROM faelle f WHERE "
                            "f.behoerde=mitglieder.behoerde AND f.aktenzeichen=mitglieder.aktenzeichen)")
            n_p = self.db.execute("DELETE FROM protokoll WHERE zeit<?", (g_p,)).rowcount
        return {"erstattungen": n_e, "faelle": n_f, "protokoll": n_p}
