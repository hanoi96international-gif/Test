"""JSON-Schnittstelle und Kommandozeile für den Leistungsabgleich.

Starten:   python -m leistungsabgleich serve --db abgleich.db --behoerden behoerden.json
Demo:      python -m leistungsabgleich demo
Pseudonym: python -m leistungsabgleich pseudonym Müller Anna 1985-03-14   (Schlüssel aus ABGLEICH_SCHLUESSEL)

behoerden.json ordnet jedem API-Schlüssel eine Behörde zu:
  {"<langer-zufallswert>": {"id": "jc-musterstadt", "art": "jobcenter"},
   "<anderer-wert>":       {"id": "wg-musterstadt", "art": "wohngeld"}}
Der Dienst spricht nur HTTP. Im Betrieb gehört davor ein TLS-Proxy im Behördennetz (z. B. DOI/NdB).

Endpunkte (alle mit Header  Authorization: Bearer <API-Schlüssel>):
  PUT  /faelle                          Fall melden oder aktualisieren
  GET  /faelle/<aktenzeichen>/abgleich  Was läuft zur selben Person bei der anderen Stelle?  [?stichtag=JJJJ-MM-TT]
  POST /erstattungsansprueche           Erstattungsanspruch anmelden
  GET  /erstattungsansprueche           Eingang/Ausgang  [?richtung=eingehend|ausgehend&status=...]
  GET  /erstattungsansprueche/<nr>      Einzelner Anspruch
  POST /erstattungsansprueche/<nr>/antwort  Anerkennen, ablehnen, beziffern, erledigen
  GET  /protokoll                       Eigene Zugriffe
"""

import argparse
import datetime as dt
import hmac
import json
import os
import secrets
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .register import Fehler, Register, pseudonym

MAX_BODY = 64 * 1024


def make_handler(register: Register, behoerden: dict):
    sperre = threading.Lock()  # sqlite-Verbindung wird von allen Threads geteilt

    class Handler(BaseHTTPRequestHandler):
        server_version = "Leistungsabgleich/1.0"

        def log_message(self, fmt, *args):  # keine Pseudonyme o. Ä. ins Server-Log
            sys.stderr.write(f"{self.command} {urllib.parse.urlsplit(self.path).path} -> {args[1] if len(args) > 1 else ''}\n")

        def _antwort(self, code, daten):
            body = json.dumps(daten, ensure_ascii=False, indent=2).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _behoerde(self):
            kopf = self.headers.get("Authorization", "")
            if kopf.startswith("Bearer "):
                gegeben = kopf[7:].strip()
                for schluessel, b in behoerden.items():
                    if hmac.compare_digest(schluessel, gegeben):
                        return b
            raise Fehler("Nicht angemeldet", 401)

        def _json(self):
            laenge = int(self.headers.get("Content-Length") or 0)
            if laenge > MAX_BODY:
                raise Fehler("Anfrage zu groß", 413)
            try:
                daten = json.loads(self.rfile.read(laenge) or b"{}")
            except json.JSONDecodeError:
                raise Fehler("Ungültiges JSON") from None
            if not isinstance(daten, dict):
                raise Fehler("JSON-Objekt erwartet")
            return daten

        def _route(self):
            b = self._behoerde()
            url = urllib.parse.urlsplit(self.path)
            teile = [urllib.parse.unquote(t) for t in url.path.strip("/").split("/") if t]
            q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
            m, bid = self.command, b["id"]
            with sperre:
                if m == "PUT" and teile == ["faelle"]:
                    return 200, register.melden(bid, b["art"], self._json())
                if m == "GET" and len(teile) == 3 and teile[0] == "faelle" and teile[2] == "abgleich":
                    return 200, register.abfragen(bid, teile[1], q.get("stichtag"))
                if teile[:1] == ["erstattungsansprueche"]:
                    if m == "POST" and len(teile) == 1:
                        return 201, register.anspruch_anmelden(bid, self._json())
                    if m == "GET" and len(teile) == 1:
                        return 200, register.ansprueche(bid, q.get("richtung", "eingehend"), q.get("status"))
                    if len(teile) >= 2 and teile[1].isdigit():
                        if m == "GET" and len(teile) == 2:
                            return 200, register.anspruch(bid, int(teile[1]))
                        if m == "POST" and teile[2:] == ["antwort"]:
                            return 200, register.anspruch_beantworten(bid, int(teile[1]), self._json())
                if m == "GET" and teile == ["protokoll"]:
                    return 200, register.protokoll(bid)
            raise Fehler("Unbekannter Endpunkt", 404)

        def _bearbeiten(self):
            try:
                self._antwort(*self._route())
            except Fehler as e:
                self._antwort(e.code, {"fehler": str(e)})
            except Exception:  # noqa: BLE001 - keine Interna nach außen geben
                self._antwort(500, {"fehler": "Interner Fehler"})
                raise

        do_GET = do_POST = do_PUT = _bearbeiten

    return Handler


def demo():
    """Spielt einen typischen Eilfall durch, ohne Server."""
    schluessel = b"nur-fuer-die-demo"
    reg = Register()
    p = pseudonym(schluessel, "Müller", "Anna", "1985-03-14")
    reg.melden("wg-musterstadt", "wohngeld", {"aktenzeichen": "WG-2026-0815", "person": p, "status": "bewilligt",
                                              "antrag_am": "2026-05-02", "von": "2026-06-01", "bis": "2027-05-31",
                                              "monatsbetrag": 312.0, "kontakt": "Wohngeldstelle, Zi. 104, -2231"})
    # Frau Müller wird arbeitslos und stellt am 3.11. Antrag beim Jobcenter (dort mit „Mueller“ erfasst)
    p_jc = pseudonym(schluessel, "Mueller", "Anna", "1985-03-14")
    reg.melden("jc-musterstadt", "jobcenter", {"aktenzeichen": "BG-12345", "person": p_jc, "status": "beantragt",
                                               "antrag_am": "2026-11-03"})
    print("Jobcenter fragt ab:")
    print(json.dumps(reg.abfragen("jc-musterstadt", "BG-12345", "2026-11-07"), ensure_ascii=False, indent=2))
    reg.melden("jc-musterstadt", "jobcenter", {"aktenzeichen": "BG-12345", "person": p_jc, "status": "bewilligt",
                                               "antrag_am": "2026-11-03", "von": "2026-11-01", "bis": "2027-04-30"})
    a = reg.anspruch_anmelden("jc-musterstadt", {"aktenzeichen": "BG-12345", "an_behoerde": "wg-musterstadt",
                                                 "an_aktenzeichen": "WG-2026-0815", "zeitraum_von": "2026-11-01",
                                                 "zeitraum_bis": "2026-11-30", "betrag": 312.0})
    print(f"\nErstattungsanspruch Nr. {a['id']} angemeldet. Eingang bei der Wohngeldstelle:")
    print(json.dumps(reg.ansprueche("wg-musterstadt"), ensure_ascii=False, indent=2))
    reg.anspruch_beantworten("wg-musterstadt", a["id"], {"status": "anerkannt", "antwort": "Wird mit Novemberzahlung verrechnet."})
    print("\nWohngeldstelle hat anerkannt:", reg.anspruch("jc-musterstadt", a["id"])["status"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="leistungsabgleich", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="befehl", required=True)
    s = sub.add_parser("serve", help="Schnittstelle starten")
    s.add_argument("--db", default="abgleich.db")
    s.add_argument("--behoerden", default="behoerden.json", help="API-Schlüssel → Behörde")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    sub.add_parser("demo", help="Beispielablauf zeigen")
    sub.add_parser("schluessel", help="Zufälligen API- oder Pseudonym-Schlüssel erzeugen")
    ps = sub.add_parser("pseudonym", help="Pseudonym einer Person berechnen")
    ps.add_argument("nachname")
    ps.add_argument("vorname")
    ps.add_argument("geburtsdatum", help="JJJJ-MM-TT")
    args = ap.parse_args(argv)

    if args.befehl == "demo":
        demo()
    elif args.befehl == "schluessel":
        print(secrets.token_urlsafe(32))
    elif args.befehl == "pseudonym":
        key = os.environ.get("ABGLEICH_SCHLUESSEL")
        if not key:
            ap.error("Umgebungsvariable ABGLEICH_SCHLUESSEL fehlt (gemeinsamer Schlüssel der Behörden)")
        print(pseudonym(key.encode(), args.nachname, args.vorname, args.geburtsdatum))
    else:
        with open(args.behoerden, encoding="utf-8") as f:
            behoerden = json.load(f)
        for b in behoerden.values():
            if b.get("art") not in ("jobcenter", "wohngeld") or not b.get("id"):
                ap.error(f"Ungültiger Eintrag in {args.behoerden}: {b}")
        server = ThreadingHTTPServer((args.host, args.port), make_handler(Register(args.db), behoerden))
        print(f"{dt.datetime.now():%H:%M} Leistungsabgleich läuft auf http://{args.host}:{args.port}", file=sys.stderr)
        server.serve_forever()


if __name__ == "__main__":
    main()
