"""HTTP/JSON-Schnittstelle und Weboberfläche.

Alle Endpunkte außer / brauchen den Header  Authorization: Bearer <API-Schlüssel der Behörde>.

  GET  /                                   Weboberfläche für die Sachbearbeitung
  GET  /ich                                Angemeldete Behörde
  PUT  /faelle                             Fall melden oder aktualisieren (vom Fachverfahren)
                                           → Antwort enthält, was vor der Auszahlung einzubehalten ist
  GET  /faelle/<aktenzeichen>/abgleich     Fälle der anderen Stelle zur selben Person  [?stichtag=JJJJ-MM-TT]
  GET  /arbeitskorb                        Offene Aufgaben (aufheben, prüfen, einbehalten, erstatten)
  GET  /erstattungen                       [?richtung=eingehend|ausgehend&status=...]
  GET  /erstattungen/<nr>
  POST /erstattungen/<nr>/entscheidung     {"entscheidung": "anerkennen"|"teilweise"|"ablehnen", ...}
  POST /erstattungen/<nr>/erstattet        Zahlung an die andere Stelle ist erfolgt
  GET  /protokoll                          Eigene Zugriffe
"""

import hashlib
import json
import pathlib
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler

from .register import Fehler, Register

MAX_BODY = 256 * 1024
UI = (pathlib.Path(__file__).with_name("ui.html")).read_bytes()
CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; "
       "img-src data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


def schluessel_hash(schluessel: str) -> str:
    return hashlib.sha256(schluessel.encode()).hexdigest()


def make_handler(register: Register, schluessel: dict, demo_schluessel: dict | None = None):
    """schluessel: {sha256(API-Schlüssel): behoerde_id}. Gespeichert werden nur Hashwerte."""
    sperre = threading.Lock()  # eine sqlite-Verbindung für alle Threads

    class Handler(BaseHTTPRequestHandler):
        server_version = "Leistungsabgleich/2.0"
        sys_version = ""

        def log_message(self, fmt, *args):  # nur Methode, Pfad ohne Query und Status ins Server-Log
            status = args[1] if len(args) > 1 else ""
            sys.stderr.write(f"{self.command} {urllib.parse.urlsplit(self.path).path} {status}\n")

        def _senden(self, code, body: bytes, typ: str):
            self.send_response(code)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", CSP)
            self.end_headers()
            self.wfile.write(body)

        def _json_senden(self, code, daten):
            self._senden(code, json.dumps(daten, ensure_ascii=False, indent=2).encode(), "application/json; charset=utf-8")

        def _behoerde(self):
            kopf = self.headers.get("Authorization", "")
            bid = schluessel.get(schluessel_hash(kopf[7:].strip())) if kopf.startswith("Bearer ") else None
            if not bid:
                raise Fehler("Nicht angemeldet oder Schlüssel ungültig", 401)
            return bid

        def _json(self):
            try:
                laenge = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise Fehler("Ungültige Content-Length") from None
            if laenge > MAX_BODY:
                raise Fehler("Anfrage zu groß", 413)
            try:
                daten = json.loads(self.rfile.read(laenge) or b"{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise Fehler("Ungültiges JSON") from None
            if not isinstance(daten, dict):
                raise Fehler("JSON-Objekt erwartet")
            return daten

        def _route(self):
            url = urllib.parse.urlsplit(self.path)
            teile = [urllib.parse.unquote(t) for t in url.path.strip("/").split("/") if t]
            m = self.command
            if m == "GET" and not teile:
                return self._senden(200, UI, "text/html; charset=utf-8")
            if m == "GET" and teile == ["demo"] and demo_schluessel:
                return self._json_senden(200, demo_schluessel)
            bid = self._behoerde()
            art = register.behoerden[bid]["art"]
            q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
            with sperre:
                if m == "GET" and teile == ["ich"]:
                    erg = {"id": bid, "art": art, "name": register.name(bid)}
                elif m == "PUT" and teile == ["faelle"]:
                    erg = register.melden(bid, art, self._json())
                elif m == "GET" and len(teile) == 3 and teile[0] == "faelle" and teile[2] == "abgleich":
                    erg = register.abfragen(bid, teile[1], q.get("stichtag"))
                elif m == "GET" and teile == ["arbeitskorb"]:
                    erg = register.arbeitskorb(bid)
                elif m == "GET" and teile == ["erstattungen"]:
                    erg = register.erstattungen(bid, q.get("richtung", "eingehend"), q.get("status"))
                elif len(teile) >= 2 and teile[0] == "erstattungen" and teile[1].isdigit():
                    nr = int(teile[1])
                    if m == "GET" and len(teile) == 2:
                        erg = register.erstattung(bid, nr)
                    elif m == "POST" and teile[2:] == ["entscheidung"]:
                        erg = register.entscheiden(bid, nr, self._json())
                    elif m == "POST" and teile[2:] == ["erstattet"]:
                        erg = register.als_erstattet(bid, nr)
                    else:
                        raise Fehler("Unbekannter Endpunkt", 404)
                elif m == "GET" and teile == ["protokoll"]:
                    erg = register.protokoll(bid)
                else:
                    raise Fehler("Unbekannter Endpunkt", 404)
            return self._json_senden(200, erg)

        def _bearbeiten(self):
            try:
                self._route()
            except Fehler as e:
                self._json_senden(e.code, {"fehler": str(e)})
            except Exception:  # noqa: BLE001 - keine Interna nach außen
                self._json_senden(500, {"fehler": "Interner Fehler"})
                raise

        do_GET = do_POST = do_PUT = _bearbeiten

    return Handler
