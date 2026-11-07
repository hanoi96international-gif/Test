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
    assert e["status"] == "teilweise_anerkannt" and e["anerkannt_cent"] == 20000


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


# --- HTTP -----------------------------------------------------------------------------------------

@pytest.fixture
def server():
    r = reg(auto_jc=200000)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
        r, {schluessel_hash("key-jc"): "jc", schluessel_hash("key-wg"): "wg"}))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def _http(url, methode="GET", key=None, daten=None, roh=False):
    req = urllib.request.Request(url, method=methode, data=json.dumps(daten).encode() if daten is not None else None,
                                 headers={"Authorization": f"Bearer {key}"} if key else {})
    try:
        with urllib.request.urlopen(req) as r:
            return (r.status, r.read().decode(), dict(r.headers)) if roh else (r.status, json.load(r))
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
    code, antwort = _http(f"{server}/faelle", "PUT", "key-jc", {
        "aktenzeichen": "BG-1", "person": P, "status": "bewilligt", "von": "2026-11-01", "bescheid_am": "2026-11-06",
        "monate": monate("2026-11", "2027-04", 89000)})
    assert code == 200 and antwort["einbehalten"][0]["betrag_cent"] == 31200
    code, erg = _http(f"{server}/faelle/WG%2F1/abgleich?stichtag=2026-11-07", key="key-wg")
    assert code == 200 and erg["faelle"][0]["aktenzeichen"] == "BG-1" and erg["aufgaben"][0]["typ"] == "aufheben"
    code, korb = _http(f"{server}/arbeitskorb", key="key-jc")
    assert [a["typ"] for a in korb] == ["erstattung_zahlen"]
    nr = korb[0]["erstattung"]
    assert _http(f"{server}/erstattungen/{nr}/erstattet", "POST", "key-wg")[0] == 403
    code, e = _http(f"{server}/erstattungen/{nr}/erstattet", "POST", "key-jc")
    assert code == 200 and e["status"] == "erstattet"
    assert _http(f"{server}/erstattungen?richtung=ausgehend", key="key-wg")[1][0]["status"] == "erstattet"
    assert _http(f"{server}/protokoll", key="key-jc")[1][0]["aktion"] == "erstattung_erstattet"
    assert _http(f"{server}/gibtsnicht", key="key-jc")[0] == 404


def test_http_fehlerhafte_anfragen(server):
    req = urllib.request.Request(f"{server}/faelle", method="PUT", data=b"{kaputt",
                                 headers={"Authorization": "Bearer key-jc"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400
    assert _http(f"{server}/faelle", "PUT", "key-jc", {"aktenzeichen": "x"})[0] == 400


def test_weboberflaeche(server):
    code, html, kopf = _http(f"{server}/", roh=True)
    assert code == 200 and "Arbeitskorb" in html
    assert "frame-ancestors 'none'" in kopf["Content-Security-Policy"]
