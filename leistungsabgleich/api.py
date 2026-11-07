"""HTTP/JSON-Schnittstelle und Weboberfläche. Vollständige Beschreibung: GET /openapi.json

Anmeldung mit  Authorization: Bearer <API-Schlüssel>. Jeder Schlüssel hat eine Rolle:
  fachverfahren    darf Fälle melden (PUT /faelle)
  sachbearbeitung  darf abgleichen, Arbeitskorb, Erstattungen entscheiden, Kennzahlen, Protokoll
  alle             beides (z. B. für die Demo)
Wer abgleicht oder entscheidet, muss sein Kürzel im Header  X-Bearbeiter  mitschicken; es landet im Protokoll.
"""

import csv
import hashlib
import io
import json
import pathlib
import re
import sys
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler

from . import __version__
from .openapi import SPEC
from .register import Fehler, Register

MAX_BODY = 256 * 1024
UI = pathlib.Path(__file__).with_name("ui.html").read_bytes()
CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; "
       "img-src data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
BEARBEITER_RE = re.compile(r"[A-Za-z0-9._-]{2,40}")
ROLLEN = ("fachverfahren", "sachbearbeitung", "alle")
FEHLVERSUCHE, SPERRFENSTER = 10, 60  # höchstens 10 falsche Schlüssel pro Minute und Adresse


def schluessel_hash(schluessel: str) -> str:
    return hashlib.sha256(schluessel.encode()).hexdigest()


def _csv(erstattungen: list[dict]) -> bytes:
    def euro(c):
        return "" if c is None else f"{c / 100:.2f}".replace(".", ",")

    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow(["Nr", "Status", "Berechtigt", "Az. berechtigt", "Verpflichtet", "Az. verpflichtet", "Zeitraum",
                "Forderung EUR", "Anerkannt EUR", "Rechtsgrundlage", "Angemeldet", "Geändert", "Automatisch"])
    for e in erstattungen:
        w.writerow([e["id"], e["status"], e["berechtigt_name"], e["berechtigt_az"], e["verpflichtet_name"],
                    e["verpflichtet_az"], e["zeitraum"], euro(e["gefordert_cent"] or e["summe_cent"]),
                    euro(e["anerkannt_cent"]),
                    e["rechtsgrundlage"], e["angemeldet"][:10], e["geaendert"][:10], "ja" if e["automatisch"] else "nein"])
    return ("﻿" + puffer.getvalue()).encode()  # BOM, damit Excel Umlaute erkennt


def make_handler(register: Register, schluessel: dict, demo_schluessel: dict | None = None, log=sys.stderr):
    """schluessel: {sha256(API-Schlüssel): (behoerde_id, rolle)}. Gespeichert werden nur Hashwerte."""
    sperre = threading.Lock()   # eine sqlite-Verbindung für alle Threads
    fehl_sperre, fehlversuche = threading.Lock(), {}
    spec = json.dumps(SPEC, ensure_ascii=False, indent=2).encode()

    class Handler(BaseHTTPRequestHandler):
        server_version = f"Leistungsabgleich/{__version__}"
        sys_version = ""
        timeout = 30  # langsame Verbindungen nicht ewig offen halten
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass  # eigenes Log in _bearbeiten, ohne Aktenzeichen und Pseudonyme

        def _senden(self, code, body: bytes, typ: str, extra=None):
            self.send_response(code)
            for k, v in {"Content-Type": typ, "Content-Length": str(len(body)), "Cache-Control": "no-store",
                         "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                         "Content-Security-Policy": CSP, "X-Request-Id": self.anfrage_id, **(extra or {})}.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
            self.code = code

        def _json_senden(self, code, daten, extra=None):
            self._senden(code, json.dumps(daten, ensure_ascii=False, indent=2).encode(),
                         "application/json; charset=utf-8", extra)

        def _gesperrt(self):
            jetzt, ip = time.monotonic(), self.client_address[0]
            with fehl_sperre:
                liste = [t for t in fehlversuche.get(ip, []) if jetzt - t < SPERRFENSTER]
                fehlversuche[ip] = liste
                return len(liste) >= FEHLVERSUCHE

        def _fehlversuch(self):
            with fehl_sperre:
                fehlversuche.setdefault(self.client_address[0], []).append(time.monotonic())

        def _anmelden(self):
            if self._gesperrt():
                raise Fehler("Zu viele Fehlversuche, bitte eine Minute warten", 429)
            kopf = self.headers.get("Authorization", "")
            treffer = schluessel.get(schluessel_hash(kopf[7:].strip())) if kopf.startswith("Bearer ") else None
            if not treffer:
                self._fehlversuch()
                raise Fehler("Nicht angemeldet oder Schlüssel ungültig", 401)
            self.behoerde, self.rolle = treffer
            b = self.headers.get("X-Bearbeiter", "").strip()
            if b and not BEARBEITER_RE.fullmatch(b):
                raise Fehler("X-Bearbeiter: 2–40 Zeichen, nur Buchstaben, Ziffern, . _ -")
            self.bearbeiter = b or None

        def _darf(self, rolle, kuerzel=False):
            if self.rolle not in (rolle, "alle"):
                raise Fehler(f"Dieser Schlüssel hat die Rolle '{self.rolle}', nötig ist '{rolle}'", 403)
            if kuerzel and not self.bearbeiter:
                raise Fehler("Bitte Kürzel im Header X-Bearbeiter mitschicken (Protokollpflicht)", 400)

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

        def _route(self, teile, q):
            m = self.command
            if m == "GET" and not teile:
                return self._senden(200, UI, "text/html; charset=utf-8")
            if m == "GET" and teile == ["status"]:
                return self._json_senden(200, {"status": "ok", "version": __version__, "beta": True})
            if m == "GET" and teile == ["openapi.json"]:
                return self._senden(200, spec, "application/json; charset=utf-8")
            if m == "GET" and teile == ["demo"] and demo_schluessel:
                return self._json_senden(200, demo_schluessel)
            self._anmelden()
            bid, b, sb = self.behoerde, self.bearbeiter, "sachbearbeitung"
            art = register.behoerden[bid]["art"]
            with sperre:
                if m == "GET" and teile == ["ich"]:
                    erg = {"id": bid, "art": art, "name": register.name(bid), "rolle": self.rolle,
                           "bearbeiter": b, "version": __version__}
                elif m == "PUT" and teile == ["faelle"]:
                    self._darf("fachverfahren")
                    erg = register.melden(bid, art, self._json(), b)
                elif m == "GET" and len(teile) == 3 and teile[0] == "faelle" and teile[2] == "abgleich":
                    self._darf(sb, kuerzel=True)
                    erg = register.abfragen(bid, teile[1], q.get("stichtag"), b)
                elif m == "GET" and teile == ["arbeitskorb"]:
                    self._darf(sb)
                    erg = register.arbeitskorb(bid, bearbeiter=b)
                elif m == "GET" and teile == ["erstattungen"]:
                    self._darf(sb)
                    erg = register.erstattungen(bid, q.get("richtung", "eingehend"), q.get("status"))
                    if q.get("format") == "csv":
                        name = f"erstattungen-{q.get('richtung', 'eingehend')}.csv"
                        return self._senden(200, _csv(erg), "text/csv; charset=utf-8",
                                            {"Content-Disposition": f'attachment; filename="{name}"'})
                elif len(teile) >= 2 and teile[0] == "erstattungen" and teile[1].isdigit():
                    nr = int(teile[1])
                    if m == "GET" and len(teile) == 2:
                        self._darf(sb)
                        erg = register.erstattung(bid, nr)
                    elif m == "POST" and teile[2:] == ["entscheidung"]:
                        self._darf(sb, kuerzel=True)
                        erg = register.entscheiden(bid, nr, self._json(), b)
                    elif m == "POST" and teile[2:] == ["erstattet"]:
                        self._darf(sb, kuerzel=True)
                        erg = register.als_erstattet(bid, nr, b)
                    else:
                        raise Fehler("Unbekannter Endpunkt", 404)
                elif m == "GET" and teile == ["kennzahlen"]:
                    self._darf(sb)
                    erg = register.kennzahlen(bid)
                elif m == "GET" and teile == ["protokoll"]:
                    self._darf(sb)
                    erg = register.protokoll(bid)
                elif m == "POST" and teile == ["feedback"]:
                    d = self._json()
                    erg = register.feedback(bid, d.get("text"), d.get("seite"), b)
                else:
                    raise Fehler("Unbekannter Endpunkt", 404)
            return self._json_senden(200, erg)

        def _bearbeiten(self):
            start, self.code = time.monotonic(), 0
            self.anfrage_id, self.behoerde, self.rolle = uuid.uuid4().hex[:12], None, None
            url = urllib.parse.urlsplit(self.path)
            teile = [urllib.parse.unquote(t) for t in url.path.strip("/").split("/") if t]
            try:
                self._route(teile, {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()})
            except Fehler as e:
                self.close_connection = True  # evtl. ungelesener Anfrage-Körper darf die Verbindung nicht verwirren
                extra = {"Retry-After": str(SPERRFENSTER)} if e.code == 429 else None
                self._json_senden(e.code, {"fehler": str(e), "anfrage": self.anfrage_id}, extra)
            except Exception as e:  # noqa: BLE001 - keine Interna nach außen
                self._json_senden(500, {"fehler": "Interner Fehler", "anfrage": self.anfrage_id})
                print(json.dumps({"anfrage": self.anfrage_id, "ausnahme": repr(e)}), file=log, flush=True)
            # Pfad ohne Aktenzeichen und Query, damit keine Fallbezüge im Server-Log stehen
            pfad = "/" + "/".join("*" if i == 1 and teile[0] in ("faelle", "erstattungen") else t
                                  for i, t in enumerate(teile))
            print(json.dumps({"zeit": time.strftime("%Y-%m-%dT%H:%M:%S"), "anfrage": self.anfrage_id,
                              "methode": self.command, "pfad": pfad, "status": self.code, "behoerde": self.behoerde,
                              "ms": round((time.monotonic() - start) * 1000)}), file=log, flush=True)

        do_GET = do_POST = do_PUT = _bearbeiten

    return Handler
