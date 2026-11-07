import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from leistungsabgleich import Register, pseudonym
from leistungsabgleich import demo as beispiel
from leistungsabgleich.api import make_handler, schluessel_hash
from leistungsabgleich.erstattung import euro, kuerzen, zeitraum
from leistungsabgleich.register import Fehler

K = b"test-schluessel"
P = pseudonym(K, "Müller", "Anna", "1985-03-14")
KIND = pseudonym(K, "Müller", "Ben", "2015-01-01")
monate = beispiel.monate


def reg(auto_jc=None, auto_wg=None):
    return Register(behoerden={
        "jc": {"art": "jobcenter", "name": "Jobcenter", "auto_anerkennung_bis_cent": auto_jc},
        "wg": {"art": "wohngeld", "name": "Wohngeldstelle", "auto_anerkennung_bis_cent": auto_wg}})


def wg_fall(r, **kw):
    daten = {"aktenzeichen": "WG-1", "person": P, "status": "bewilligt", "von": "2026-06-01", "bis": "2027-05-31",
             "bescheid_am": "2026-05-20", "monate": monate("2026-06", "2027-05", 31200, gezahlt_bis="2026-11")}
    return r.melden("wg", "wohngeld", daten | kw)


def jc_fall(r, **kw):
    daten = {"aktenzeichen": "BG-1", "person": P, "status": "bewilligt", "von": "2026-11-01", "bis": "2027-04-30",
             "bescheid_am": "2026-11-06", "monate": monate("2026-11", "2027-04", 89000)}
    return r.melden("jc", "jobcenter", daten | kw)


def typen(r, behoerde):
    return sorted(a["typ"] for a in r.arbeitskorb(behoerde, protokollieren=False))


# --- Grundlagen -------------------------------------------------------------------------------

def test_pseudonym_robust_gegen_schreibweisen():
    assert P == pseudonym(K, " MUELLER", "anna", "1985-03-14")
    assert pseudonym(K, "Groß", "Anna-Lena", "1990-01-01") == pseudonym(K, "Gross", "Anna Lena", "1990-01-01")
    assert P != pseudonym(K, "Müller", "Anna", "1985-03-15")
    assert P != pseudonym(b"anderer", "Müller", "Anna", "1985-03-14")


def test_formatierung():
    assert euro(123456) == "1.234,56 €" and euro(None) == "–"
    assert zeitraum(["2026-11", "2026-12", "2027-01", "2027-03"]) == "11/2026–01/2027, 03/2027"


def test_kuerzen_von_hinten():
    pos = {m: {"betrag": 30000, "hoechstens": 50000} for m in ("2026-09", "2026-10", "2026-11")}
    neu = kuerzen(pos, 70000)
    assert [neu[m]["betrag"] for m in sorted(neu)] == [30000, 30000, 10000]
    with pytest.raises(ValueError):
        kuerzen(pos, 90000)


@pytest.mark.parametrize("falsch", [
    {"person": "Anna Müller"}, {"status": "läuft"}, {"von": None}, {"bis": "2026-01-01"},
    {"monate": [{"monat": "2026-13", "anspruch_cent": 1}]},
    {"monate": [{"monat": "2026-11", "anspruch_cent": 12.5}]},
    {"monate": [{"monat": "2026-11"}, {"monat": "2026-11"}]},
    {"haushalt": ["kein-pseudonym"]},
])
def test_ungueltige_meldungen(falsch):
    with pytest.raises(Fehler):
        jc_fall(reg(), **falsch)


# --- Richtung 1: Wohngeld gezahlt, Bürgergeld rückwirkend → Wohngeldstelle bekommt Erstattung -------

def test_buergergeld_rueckwirkend_wohngeldstelle_muss_nur_aufheben():
    r = reg(auto_jc=200000)
    wg_fall(r)
    antwort = jc_fall(r)
    # Jobcenter-Fachverfahren erfährt sofort: November 312 € an die Wohngeldstelle, nicht an den Bürger
    assert antwort["einbehalten"] == [{"monat": "2026-11", "betrag_cent": 31200, "hoechstens_cent": 31200, "an": "wg",
                                       "erstattung": 1, "status": "anerkannt"}]
    e = r.erstattung("wg", 1)
    assert e["berechtigt"] == "wg" and e["automatisch"] and e["rechtsgrundlage"].startswith("§ 103 SGB X")
    assert typen(r, "jc") == ["erstattung_zahlen"]
    aufheben = r.arbeitskorb("wg", protokollieren=False)
    assert [a["typ"] for a in aufheben] == ["aufheben"] and aufheben[0]["zeitraum"] == "11/2026–04/2027"
    assert "Keine Rückforderung" in aufheben[0]["text"]

    # Sachbearbeitung hebt auf: Wohngeld ab November 0 €, Aufgabe verschwindet, Erstattung bleibt
    wg_fall(r, status="eingestellt", bis="2026-10-31",
            monate=monate("2026-06", "2026-10", 31200, gezahlt_bis="2026-10")
            + [{"monat": "2026-11", "anspruch_cent": 0, "gezahlt_cent": 31200}])
    assert typen(r, "wg") == [] and r.erstattung("wg", 1)["status"] == "anerkannt"
    assert r.als_erstattet("jc", 1)["status"] == "erstattet"
    assert typen(r, "jc") == []


def test_ohne_freigrenze_wird_von_hand_anerkannt():
    r = reg()
    wg_fall(r)
    jc_fall(r)
    assert r.erstattung("jc", 1)["status"] == "beziffert"
    assert "erstattung_pruefen" in typen(r, "jc")
    with pytest.raises(Fehler) as e:
        r.entscheiden("wg", 1, {"entscheidung": "anerkennen"})  # Berechtigte darf nicht selbst anerkennen
    assert e.value.code == 403
    assert r.entscheiden("jc", 1, {"entscheidung": "anerkennen"})["anerkannt_cent"] == 31200
    with pytest.raises(Fehler):
        r.entscheiden("jc", 1, {"entscheidung": "anerkennen"})  # schon entschieden


def test_freigrenze_wird_beachtet():
    r = reg(auto_jc=10000)  # 100 € Freigrenze, Forderung 312 €
    wg_fall(r)
    jc_fall(r)
    assert r.erstattung("jc", 1)["status"] == "beziffert"


# --- Richtung 2: Jobcenter zahlt, Wohngeld beantragt und später rückwirkend bewilligt ------------

def test_anmeldung_dem_grunde_nach_dann_automatische_bezifferung():
    r = reg()
    jc_fall(r, aktenzeichen="BG-2", von="2026-07-01", bescheid_am="2026-07-10",
            monate=monate("2026-07", "2026-12", 65000, gezahlt_bis="2026-11"))
    r.melden("wg", "wohngeld", {"aktenzeichen": "WG-2", "person": P, "status": "beantragt", "antrag_am": "2026-08-12"})
    e = r.erstattung("jc", 1)
    assert e["status"] == "angemeldet" and e["zeitraum"] == "08/2026–11/2026"  # erst ab Antragsmonat
    assert all(p["betrag"] is None for p in e["positionen"].values()) and e["hoechstens_cent"] == 4 * 65000
    assert typen(r, "wg") == ["einbehalten"]
    with pytest.raises(Fehler):
        r.entscheiden("wg", 1, {"entscheidung": "anerkennen"})  # noch nicht beziffert

    antwort = r.melden("wg", "wohngeld", {
        "aktenzeichen": "WG-2", "person": P, "status": "bewilligt", "antrag_am": "2026-08-12", "bescheid_am": "2026-11-09",
        "von": "2026-08-01", "bis": "2027-07-31", "monate": monate("2026-08", "2027-07", 28000)})
    e = r.erstattung("jc", 1)  # dieselbe Erstattung, jetzt beziffert: je Monat min(650 €, 280 €)
    assert e["status"] == "beziffert" and e["summe_cent"] == 4 * 28000
    assert [x["betrag_cent"] for x in antwort["einbehalten"]] == [28000] * 4
    assert e["rechtsgrundlage"].startswith("§ 104 SGB X")
    # Dezember: beide bewilligt, Wohngeldbescheid ist jünger → Jobcenter passt an
    aufg = [a for a in r.arbeitskorb("jc", protokollieren=False) if a["typ"] == "aufheben"]
    assert len(aufg) == 1 and aufg[0]["zeitraum"] == "12/2026"
    assert typen(r, "wg") == ["erstattung_pruefen"]


def test_wohngeld_abgelehnt_anmeldung_entfaellt():
    r = reg()
    jc_fall(r, monate=monate("2026-11", "2027-04", 89000, gezahlt_bis="2026-11"))
    r.melden("wg", "wohngeld", {"aktenzeichen": "WG-2", "person": P, "status": "beantragt", "antrag_am": "2026-11-01"})
    assert r.erstattungen("jc", "ausgehend")[0]["status"] == "angemeldet"
    r.melden("wg", "wohngeld", {"aktenzeichen": "WG-2", "person": P, "status": "abgelehnt", "antrag_am": "2026-11-01"})
    assert r.erstattungen("jc", "ausgehend") == []
    assert typen(r, "wg") == []


# --- Sonderfälle gehen an den Menschen ------------------------------------------------------------

def test_abweichender_haushalt_braucht_pruefung_trotz_freigrenze():
    r = reg(auto_jc=10 ** 9)
    wg_fall(r, haushalt=[KIND])
    jc_fall(r)
    e = r.erstattung("jc", 1)
    assert e["status"] == "pruefung" and "nicht deckungsgleich" in e["pruefhinweise"][0]


def test_haushaltsmitglied_verbindet_faelle():
    r = reg()
    wg_fall(r, person=KIND, haushalt=[P])  # Antrag beim Wohngeld vom anderen Haushaltsmitglied
    jc_fall(r, haushalt=[KIND])
    assert len(r.erstattungen("wg", "ausgehend")) == 1


def test_doppelbezug_wird_gemeldet():
    r = reg()
    wg_fall(r)
    jc_fall(r, monate=monate("2026-11", "2027-04", 89000, gezahlt_bis="2026-11"))  # beide haben November ausgezahlt
    assert r.erstattungen("wg", "ausgehend") == [] and r.erstattungen("jc", "ausgehend") == []
    assert "doppelbezug" in typen(r, "wg") and "doppelbezug" in typen(r, "jc")


def test_auszahlung_trotz_anerkannter_erstattung_wird_erkannt():
    r = reg(auto_jc=200000)
    wg_fall(r)
    jc_fall(r)
    jc_fall(r, monate=monate("2026-11", "2027-04", 89000, gezahlt_bis="2026-11"))  # 890 € statt 578 € ausgezahlt
    assert r.erstattung("jc", 1)["korrektur"] == ["2026-11"]
    assert "korrektur" in typen(r, "jc")
    jc_fall(r, monate=[{"monat": "2026-11", "anspruch_cent": 89000, "gezahlt_cent": 57800}]
            + monate("2026-12", "2027-04", 89000))  # richtig: Rest 578 € an den Bürger
    assert r.erstattung("jc", 1)["korrektur"] == []


def test_abgelehnte_monate_werden_nicht_erneut_gefordert():
    r = reg()
    wg_fall(r)
    jc_fall(r)
    with pytest.raises(Fehler):
        r.entscheiden("jc", 1, {"entscheidung": "ablehnen"})  # ohne Begründung
    r.entscheiden("jc", 1, {"entscheidung": "ablehnen", "begruendung": "Wohngeld war bereits als Einkommen angerechnet"})
    jc_fall(r, kontakt="neu")  # erneute Meldung
    assert [e["status"] for e in r.erstattungen("wg", "ausgehend")] == ["abgelehnt"]


def test_teilanerkennung():
    r = reg()
    wg_fall(r)
    jc_fall(r)
    e = r.entscheiden("jc", 1, {"entscheidung": "teilweise", "betrag_cent": 20000, "begruendung": "Teilmonat"})
    assert e["status"] == "teilweise_anerkannt" and e["anerkannt_cent"] == 20000 and e["gefordert_cent"] == 31200


# --- Datenschutz ----------------------------------------------------------------------------------

def test_zweckbindung_und_protokoll():
    r = reg()
    wg_fall(r)
    with pytest.raises(Fehler) as e:
        r.abfragen("jc", "BG-1")
    assert e.value.code == 404
    r.melden("jc", "jobcenter", {"aktenzeichen": "BG-9", "person": "0" * 64, "status": "beantragt"})
    assert r.abfragen("jc", "BG-9")["faelle"] == []  # andere Person: nichts zu sehen
    assert [p["aktion"] for p in r.protokoll("jc")] == ["abfragen", "melden", "abfrage_abgelehnt"]
    with pytest.raises(Fehler):
        r.erstattung("dritte", 1)


def test_abgleich_zeigt_laufende_leistung_und_hinweis():
    r = reg()
    wg_fall(r)
    r.melden("jc", "jobcenter", {"aktenzeichen": "BG-1", "person": P, "status": "beantragt", "antrag_am": "2026-11-03"})
    erg = r.abfragen("jc", "BG-1", "2026-11-07")
    f = erg["faelle"][0]
    assert f["laeuft"] and f["anspruch_aktuell_cent"] == 31200 and f["name"] == "Wohngeldstelle"
    erg = r.abfragen("wg", "WG-1", "2026-11-07")
    assert "Bürgergeld ist seit 2026-11-03 beantragt" in erg["hinweise"][0]


def test_aufraeumen_loescht_nur_abgeschlossenes():
    r = reg(auto_jc=200000)
    wg_fall(r)
    jc_fall(r)
    eintraege = len(r.protokoll("wg")) + len(r.protokoll("jc"))
    assert r.aufraeumen("2040-01-01") == {"erstattungen": 0, "faelle": 0, "protokoll": eintraege}
    r.als_erstattet("jc", 1)
    erg = r.aufraeumen("2040-01-01")
    assert erg["erstattungen"] == 1 and erg["faelle"] == 2
    assert r.db.execute("SELECT count(*) FROM mitglieder").fetchone()[0] == 0


def test_demo_daten():
    r = beispiel.fuellen(Register(behoerden=beispiel.BEHOERDEN))
    assert {e["status"] for e in r.erstattungen(beispiel.WG)} == {"angemeldet", "pruefung"}
    assert [e["status"] for e in r.erstattungen(beispiel.JC)] == ["anerkannt"]


# --- Beta: Betrieb, Migration, Kennzahlen, Feedback ------------------------------------------------

def test_migration_von_version_2_0(tmp_path):
    import sqlite3
    pfad = str(tmp_path / "alt.db")
    alt = sqlite3.connect(pfad)  # Schema der Version 2.0, ohne Bearbeiter-Spalte und Feedback
    alt.executescript("""CREATE TABLE faelle (behoerde TEXT, aktenzeichen TEXT, art TEXT, person TEXT, haushalt TEXT,
        status TEXT, antrag_am TEXT, bescheid_am TEXT, von TEXT, bis TEXT, monate TEXT, kontakt TEXT, geaendert TEXT,
        PRIMARY KEY (behoerde, aktenzeichen));
        CREATE TABLE mitglieder (behoerde TEXT, aktenzeichen TEXT, person TEXT, PRIMARY KEY (behoerde, aktenzeichen, person));
        CREATE TABLE erstattungen (id INTEGER PRIMARY KEY AUTOINCREMENT, berechtigt TEXT, berechtigt_az TEXT,
        berechtigt_art TEXT, verpflichtet TEXT, verpflichtet_az TEXT, rechtsgrundlage TEXT, status TEXT, positionen TEXT,
        pruefhinweise TEXT DEFAULT '[]', korrektur TEXT DEFAULT '[]', anerkannt_cent INTEGER, begruendung TEXT,
        automatisch INTEGER DEFAULT 0, angemeldet TEXT, geaendert TEXT);
        CREATE TABLE protokoll (zeit TEXT, behoerde TEXT, aktion TEXT, aktenzeichen TEXT, details TEXT);
        INSERT INTO protokoll VALUES ('2026-01-01', 'jc', 'melden', 'BG-0', '{}');""")
    alt.commit()
    alt.close()
    r = Register(pfad, reg().behoerden)
    assert r.db.execute("PRAGMA user_version").fetchone()[0] == 3
    assert r.protokoll("jc")[0]["bearbeiter"] is None
    wg_fall(r)
    jc_fall(r)
    r.abfragen("jc", "BG-1", bearbeiter="mkern")
    assert r.protokoll("jc")[0]["bearbeiter"] == "mkern"
    r.feedback("jc", "Klappt gut", "korb", "mkern")
    assert Register(pfad).feedback_liste()[0]["text"] == "Klappt gut"  # zweites Öffnen: keine erneute Migration


def test_sicherung_und_wartung(tmp_path):
    from leistungsabgleich.__main__ import wartung
    pfad = str(tmp_path / "abgleich.db")
    r = Register(pfad, reg(auto_jc=200000).behoerden)
    wg_fall(r)
    jc_fall(r)
    for _ in range(3):
        erg = wartung(pfad, tmp_path / "sicherungen", behalten=2)
    kopie = Register(erg["sicherung"])
    assert kopie.db.execute("SELECT count(*) FROM erstattungen").fetchone()[0] == 1
    assert len(list((tmp_path / "sicherungen").glob("*.db"))) <= 2


def test_kennzahlen_und_feedback():
    r = reg(auto_jc=200000)
    wg_fall(r)
    jc_fall(r)
    r.als_erstattet("jc", 1, "mkern")
    k = r.kennzahlen("jc")
    assert k["forderungen_an_uns"] == {"erstattet": {"anzahl": 1, "anerkannt_cent": 31200}}
    assert k["automatisch_anerkannt"] == 1 and k["entschieden"] == 1
    assert k["tage_bis_erstattung"]["an_uns"] == 0.0
    assert r.kennzahlen("wg")["offene_aufgaben"] == {"aufheben": 1}
    with pytest.raises(Fehler):
        r.feedback("jc", "")


def test_konfiguration(tmp_path):
    from leistungsabgleich.__main__ import konfig_laden
    pfad = tmp_path / "behoerden.json"
    h1, h2 = schluessel_hash("a"), schluessel_hash("b")
    pfad.write_text(json.dumps({"behoerden": {
        "jc": {"art": "jobcenter", "schluessel": [{"sha256": h1, "rolle": "fachverfahren"}]},
        "wg": {"art": "wohngeld", "schluessel_sha256": h2}}}))  # altes Format geht weiter
    _, schluessel = konfig_laden(str(pfad))
    assert schluessel == {h1: ("jc", "fachverfahren"), h2: ("wg", "alle")}
    pfad.write_text(json.dumps({"behoerden": {"jc": {"art": "jobcenter", "schluessel": [{"sha256": h1, "rolle": "chef"}]}}}))
    with pytest.raises(SystemExit):
        konfig_laden(str(pfad))


def test_beispielkonfiguration_ist_gueltig():
    from leistungsabgleich.__main__ import konfig_laden
    behoerden, schluessel = konfig_laden("deploy/behoerden.beispiel.json")
    assert {b["art"] for b in behoerden.values()} == {"jobcenter", "wohngeld"}


# --- Meldewerkzeug (CSV) --------------------------------------------------------------------------

CSV = """aktenzeichen;nachname;vorname;geburtsdatum;haushalt;status;antrag_am;bescheid_am;von;bis;kontakt;monat;anspruch;gezahlt
WG-1;Müller;Anna;14.03.1985;Müller,Ben,01.01.2015;bewilligt;04.05.2026;20.05.2026;01.06.2026;31.05.2027;Zi. 104;06/2026;312,00;312,00
WG-1;Müller;Anna;14.03.1985;Müller,Ben,01.01.2015;bewilligt;04.05.2026;20.05.2026;01.06.2026;31.05.2027;Zi. 104;2026-07;1.312,50;0
WG-2;Schmidt;Jonas;1979-11-02;;beantragt;12.08.2026;;;;;;;
"""


def test_csv_lesen():
    from leistungsabgleich.meldeclient import lesen
    m = lesen("\ufeff" + CSV, K)
    assert [x["aktenzeichen"] for x in m] == ["WG-1", "WG-2"]
    assert m[0]["person"] == P and m[0]["haushalt"] == [KIND]
    assert m[0]["von"] == "2026-06-01" and m[0]["monate"] == [
        {"monat": "2026-06", "anspruch_cent": 31200, "gezahlt_cent": 31200},
        {"monat": "2026-07", "anspruch_cent": 131250, "gezahlt_cent": 0}]
    assert m[1]["status"] == "beantragt" and m[1]["monate"] == []
    r = reg()
    for x in m:
        r.melden("wg", "wohngeld", x)  # Ergebnis ist eine gültige Meldung


@pytest.mark.parametrize("kaputt, meldung", [
    (CSV.replace("14.03.1985;Müller,Ben", "31.02.1985;Müller,Ben", 1), "Zeile 2"),
    (CSV.replace("312,00;312,00", "3,125;0"), "Nachkommastellen"),
    (CSV.replace(";2026-07;", ";13/2026;"), "Zeile 3"),
    (CSV.replace("Zi. 104;2026-07", "Zi. 105;2026-07"), "weichen von Zeile 2 ab"),
    (CSV.replace("beantragt", "läuft"), "status"),
    ("a;b\n1;2\n", "Spalten fehlen"),
])
def test_csv_fehler_mit_zeilennummer(kaputt, meldung):
    from leistungsabgleich.meldeclient import CsvFehler, lesen
    with pytest.raises(CsvFehler, match=meldung):
        lesen(kaputt, K)


# --- HTTP -----------------------------------------------------------------------------------------

@pytest.fixture
def server():
    r = reg(auto_jc=200000)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(r, {
        schluessel_hash("key-jc"): ("jc", "alle"), schluessel_hash("key-wg"): ("wg", "alle"),
        schluessel_hash("fv-jc"): ("jc", "fachverfahren"), schluessel_hash("sb-jc"): ("jc", "sachbearbeitung")},
        log=open("/dev/null", "w")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def _http(url, methode="GET", key=None, daten=None, roh=False, bearbeiter="test"):
    kopf = {"Authorization": f"Bearer {key}"} if key else {}
    if bearbeiter and key:
        kopf["X-Bearbeiter"] = bearbeiter
    req = urllib.request.Request(url, method=methode, data=json.dumps(daten).encode() if daten is not None else None,
                                 headers=kopf)
    try:
        with urllib.request.urlopen(req) as r:
            return (r.status, r.read().decode("utf-8-sig"), dict(r.headers)) if roh else (r.status, json.load(r))
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_http_ablauf(server):
    assert _http(f"{server}/arbeitskorb")[0] == 401
    assert _http(f"{server}/arbeitskorb", key="falsch")[0] == 401
    assert _http(f"{server}/ich", key="key-jc")[1]["art"] == "jobcenter"
    assert _http(f"{server}/demo")[0] == 401  # Demo-Schlüssel gibt es nur im Demo-Modus
    wg = {"aktenzeichen": "WG/1", "person": P, "status": "bewilligt", "von": "2026-06-01", "bescheid_am": "2026-05-20",
          "monate": monate("2026-06", "2027-05", 31200, gezahlt_bis="2026-11")}
    assert _http(f"{server}/faelle", "PUT", "key-wg", wg)[0] == 200
    code, antwort = _http(f"{server}/faelle", "PUT", "fv-jc", {
        "aktenzeichen": "BG-1", "person": P, "status": "bewilligt", "von": "2026-11-01", "bescheid_am": "2026-11-06",
        "monate": monate("2026-11", "2027-04", 89000)}, bearbeiter=None)
    assert code == 200 and antwort["einbehalten"][0]["betrag_cent"] == 31200
    code, erg = _http(f"{server}/faelle/WG%2F1/abgleich?stichtag=2026-11-07", key="key-wg")
    assert code == 200 and erg["faelle"][0]["aktenzeichen"] == "BG-1" and erg["aufgaben"][0]["typ"] == "aufheben"
    code, korb = _http(f"{server}/arbeitskorb", key="sb-jc")
    assert [a["typ"] for a in korb] == ["erstattung_zahlen"]
    nr = korb[0]["erstattung"]
    assert _http(f"{server}/erstattungen/{nr}/erstattet", "POST", "key-wg")[0] == 403
    assert _http(f"{server}/erstattungen/{nr}/erstattet", "POST", "sb-jc", bearbeiter=None)[0] == 400  # Kürzel fehlt
    code, e = _http(f"{server}/erstattungen/{nr}/erstattet", "POST", "sb-jc", bearbeiter="m.kern")
    assert code == 200 and e["status"] == "erstattet"
    assert _http(f"{server}/erstattungen?richtung=ausgehend", key="key-wg")[1][0]["status"] == "erstattet"
    prot = _http(f"{server}/protokoll", key="key-jc")[1]
    assert prot[0]["aktion"] == "erstattung_erstattet" and prot[0]["bearbeiter"] == "m.kern"
    code, k = _http(f"{server}/kennzahlen", key="sb-jc")
    assert code == 200 and k["forderungen_an_uns"]["erstattet"]["anzahl"] == 1
    code, text, kopf = _http(f"{server}/erstattungen?richtung=eingehend&format=csv", key="sb-jc", roh=True)
    assert code == 200 and "text/csv" in kopf["Content-Type"] and "312,00" in text.splitlines()[1]
    assert _http(f"{server}/feedback", "POST", "fv-jc", {"text": "Gute Sache"})[1] == {"danke": True}
    assert _http(f"{server}/gibtsnicht", key="key-jc")[0] == 404


def test_http_rollen(server):
    assert _http(f"{server}/arbeitskorb", key="fv-jc")[0] == 403  # Fachverfahren liest keine Aufgaben
    assert _http(f"{server}/faelle", "PUT", "sb-jc", {"aktenzeichen": "x"})[0] == 403  # Sachbearbeitung meldet nicht
    assert _http(f"{server}/faelle/BG-1/abgleich", key="sb-jc", bearbeiter=None)[0] == 400
    assert _http(f"{server}/ich", key="sb-jc", bearbeiter="nicht erlaubt!")[0] == 400


def test_http_status_und_openapi(server):
    assert _http(f"{server}/status")[1]["status"] == "ok"
    code, spec = _http(f"{server}/openapi.json")
    assert code == 200 and spec["openapi"].startswith("3.")
    for pfad in ("/faelle", "/faelle/{aktenzeichen}/abgleich", "/arbeitskorb", "/erstattungen",
                 "/erstattungen/{nr}/entscheidung", "/erstattungen/{nr}/erstattet", "/kennzahlen", "/protokoll",
                 "/feedback", "/status", "/ich"):
        assert pfad in spec["paths"]


def test_http_sperre_nach_fehlversuchen(server):
    for _ in range(10):
        assert _http(f"{server}/ich", key="geraten")[0] == 401
    assert _http(f"{server}/ich", key="key-jc")[0] == 429  # auch richtige Schlüssel warten


def test_http_fehlerhafte_anfragen(server):
    req = urllib.request.Request(f"{server}/faelle", method="PUT", data=b"{kaputt",
                                 headers={"Authorization": "Bearer key-jc"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400
    assert _http(f"{server}/faelle", "PUT", "key-jc", {"aktenzeichen": "x"})[0] == 400


def test_http_meldewerkzeug(server):
    from leistungsabgleich.meldeclient import lesen, senden
    erg = senden(lesen(CSV, K), server, "key-wg", "mkern")
    assert [e["ok"] for e in erg] == [True, True]
    assert senden(lesen(CSV, K), server, "falsch")[0] == {"aktenzeichen": "WG-1", "ok": False,
                                                          "fehler": "Nicht angemeldet oder Schlüssel ungültig"}


def test_weboberflaeche(server):
    code, html, kopf = _http(f"{server}/", roh=True)
    assert code == 200 and "Arbeitskorb" in html and "Beta" in html
    assert "frame-ancestors 'none'" in kopf["Content-Security-Policy"]
