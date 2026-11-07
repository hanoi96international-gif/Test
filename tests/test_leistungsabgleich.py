import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from leistungsabgleich import Register, pseudonym
from leistungsabgleich.__main__ import make_handler
from leistungsabgleich.register import Fehler

K = b"test-schluessel"
P = pseudonym(K, "Müller", "Anna", "1985-03-14")


def _wohngeld_laeuft(reg):
    reg.melden("wg", "wohngeld", {"aktenzeichen": "WG-1", "person": P, "status": "bewilligt",
                                  "von": "2026-06-01", "bis": "2027-05-31", "monatsbetrag": 312})


def test_pseudonym_robust_gegen_schreibweisen():
    assert P == pseudonym(K, " MUELLER", "anna", "1985-03-14")
    assert pseudonym(K, "Groß", "Anna-Lena", "1990-01-01") == pseudonym(K, "Gross", "Anna Lena", "1990-01-01")
    assert P != pseudonym(K, "Müller", "Anna", "1985-03-15")
    assert P != pseudonym(b"anderer", "Müller", "Anna", "1985-03-14")


def test_jobcenter_sieht_laufendes_wohngeld_mit_hinweis():
    reg = Register()
    _wohngeld_laeuft(reg)
    reg.melden("jc", "jobcenter", {"aktenzeichen": "BG-1", "person": P, "status": "beantragt"})
    erg = reg.abfragen("jc", "BG-1", "2026-11-07")
    assert [f["aktenzeichen"] for f in erg["faelle"]] == ["WG-1"]
    assert erg["faelle"][0]["laeuft"]
    assert "§ 7 Abs. 1 WoGG" in erg["hinweise"][0]
    assert not reg.abfragen("jc", "BG-1", "2027-06-01")["faelle"][0]["laeuft"]


def test_umgekehrt_wohngeldstelle_sieht_bürgergeldantrag():
    reg = Register()
    _wohngeld_laeuft(reg)
    reg.melden("jc", "jobcenter", {"aktenzeichen": "BG-1", "person": P, "status": "beantragt", "antrag_am": "2026-11-03"})
    erg = reg.abfragen("wg", "WG-1")
    assert erg["faelle"][0]["status"] == "beantragt"
    assert "2026-11-03" in erg["hinweise"][0]


def test_zweckbindung_nur_mit_eigenem_fall():
    reg = Register()
    _wohngeld_laeuft(reg)
    with pytest.raises(Fehler) as e:
        reg.abfragen("jc", "BG-1")
    assert e.value.code == 404
    reg.melden("jc", "jobcenter", {"aktenzeichen": "BG-9", "person": "0" * 64, "status": "beantragt"})
    assert reg.abfragen("jc", "BG-9")["faelle"] == []  # andere Person: nichts zu sehen
    assert [p["aktion"] for p in reg.protokoll("jc")] == ["abfragen", "melden", "abfrage_abgelehnt"]


def test_ungueltige_meldungen():
    reg = Register()
    for daten in ({"aktenzeichen": "A", "person": "Anna Müller", "status": "beantragt"},
                  {"aktenzeichen": "A", "person": P, "status": "läuft"},
                  {"aktenzeichen": "A", "person": P, "status": "bewilligt"},
                  {"aktenzeichen": "A", "person": P, "status": "bewilligt", "von": "2026-05-01", "bis": "2026-01-01"}):
        with pytest.raises(Fehler):
            reg.melden("jc", "jobcenter", daten)


def test_erstattungsanspruch_ablauf():
    reg = Register()
    _wohngeld_laeuft(reg)
    reg.melden("jc", "jobcenter", {"aktenzeichen": "BG-1", "person": P, "status": "bewilligt", "von": "2026-11-01"})
    a = reg.anspruch_anmelden("jc", {"aktenzeichen": "BG-1", "an_behoerde": "wg", "an_aktenzeichen": "WG-1",
                                     "zeitraum_von": "2026-11-01", "zeitraum_bis": "2026-11-30"})
    assert a["status"] == "angemeldet" and a["betrag"] is None and a["rechtsgrundlage"] == "§ 104 SGB X"
    assert reg.ansprueche("wg")[0]["id"] == a["id"]
    assert reg.anspruch_beantworten("jc", a["id"], {"status": "angemeldet", "betrag": 312})["betrag"] == 312
    with pytest.raises(Fehler):  # anmeldende Stelle darf nicht selbst anerkennen
        reg.anspruch_beantworten("jc", a["id"], {"status": "anerkannt"})
    with pytest.raises(Fehler):  # Ablehnung ohne Begründung
        reg.anspruch_beantworten("wg", a["id"], {"status": "abgelehnt"})
    assert reg.anspruch_beantworten("wg", a["id"], {"status": "anerkannt"})["status"] == "anerkannt"
    assert reg.anspruch_beantworten("jc", a["id"], {"status": "erledigt"})["status"] == "erledigt"
    with pytest.raises(Fehler):  # Dritte sehen den Anspruch nicht
        reg.anspruch("andere", a["id"])


def test_anspruch_nur_gegen_fall_derselben_person():
    reg = Register()
    reg.melden("wg", "wohngeld", {"aktenzeichen": "WG-2", "person": "1" * 64, "status": "beantragt"})
    reg.melden("jc", "jobcenter", {"aktenzeichen": "BG-1", "person": P, "status": "beantragt"})
    with pytest.raises(Fehler):
        reg.anspruch_anmelden("jc", {"aktenzeichen": "BG-1", "an_behoerde": "wg", "an_aktenzeichen": "WG-2",
                                     "zeitraum_von": "2026-11-01", "zeitraum_bis": "2026-11-30"})


@pytest.fixture
def server():
    behoerden = {"key-jc": {"id": "jc", "art": "jobcenter"}, "key-wg": {"id": "wg", "art": "wohngeld"}}
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Register(), behoerden))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def _http(url, methode="GET", key=None, daten=None):
    req = urllib.request.Request(url, method=methode, data=json.dumps(daten).encode() if daten else None,
                                 headers={"Authorization": f"Bearer {key}"} if key else {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_http_schnittstelle(server):
    assert _http(f"{server}/protokoll")[0] == 401
    assert _http(f"{server}/protokoll", key="falsch")[0] == 401
    code, _ = _http(f"{server}/faelle", "PUT", "key-wg",
                    {"aktenzeichen": "WG/1", "person": P, "status": "bewilligt", "von": "2026-06-01"})
    assert code == 200
    _http(f"{server}/faelle", "PUT", "key-jc", {"aktenzeichen": "BG-1", "person": P, "status": "beantragt"})
    code, erg = _http(f"{server}/faelle/BG-1/abgleich?stichtag=2026-11-07", key="key-jc")
    assert code == 200 and erg["faelle"][0]["aktenzeichen"] == "WG/1" and erg["faelle"][0]["laeuft"]
    code, a = _http(f"{server}/erstattungsansprueche", "POST", "key-jc",
                    {"aktenzeichen": "BG-1", "an_behoerde": "wg", "an_aktenzeichen": "WG/1",
                     "zeitraum_von": "2026-11-01", "zeitraum_bis": "2026-11-30", "betrag": 312})
    assert code == 201
    code, eingang = _http(f"{server}/erstattungsansprueche", key="key-wg")
    assert [x["id"] for x in eingang] == [a["id"]]
    code, x = _http(f"{server}/erstattungsansprueche/{a['id']}/antwort", "POST", "key-wg", {"status": "anerkannt"})
    assert code == 200 and x["status"] == "anerkannt"
    assert _http(f"{server}/gibtsnicht", key="key-jc")[0] == 404
