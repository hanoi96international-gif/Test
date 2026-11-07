"""Kommandozeile für den Leistungsabgleich.

  python -m leistungsabgleich demo                    Ablauf Schritt für Schritt im Terminal
  python -m leistungsabgleich serve --demo            Weboberfläche mit Beispielfällen (http://127.0.0.1:8080)
  python -m leistungsabgleich serve --db abgleich.db --konfig behoerden.json [--zertifikat cert.pem --zertifikat-schluessel key.pem]
  python -m leistungsabgleich schluessel              Neuen API-Schlüssel und seinen Hash für die Konfiguration erzeugen
  python -m leistungsabgleich pseudonym Müller Anna 1985-03-14   (gemeinsamer Schlüssel in ABGLEICH_SCHLUESSEL)
  python -m leistungsabgleich aufraeumen --db abgleich.db        Löschfristen anwenden

behoerden.json (es werden nur Hashwerte der API-Schlüssel gespeichert):
  {"behoerden": {
     "jc-musterstadt": {"art": "jobcenter", "name": "Jobcenter Musterstadt",
                        "schluessel_sha256": "…", "auto_anerkennung_bis_cent": 200000},
     "wg-musterstadt": {"art": "wohngeld", "name": "Wohngeldstelle Musterstadt", "schluessel_sha256": "…"}}}
auto_anerkennung_bis_cent: Erstattungen bis zu diesem Betrag ohne Prüfhinweis erkennt das System für
diese Behörde automatisch an. Weglassen = immer von Hand.
"""

import argparse
import json
import os
import secrets
import ssl
import sys
from http.server import ThreadingHTTPServer

from . import demo as beispiel
from .api import make_handler, schluessel_hash
from .erstattung import euro
from .register import Register, pseudonym


def _korb(reg, bid):
    for a in reg.arbeitskorb(bid, protokollieren=False):
        print(f"  • [{a['titel']}] {a['aktenzeichen']}: {a['text']}")


def demo():
    reg = Register(behoerden=beispiel.BEHOERDEN)
    jc, wg = beispiel.JC, beispiel.WG
    print("Stand Anfang November 2026, drei Fälle. Aus Sicht der Wohngeldstelle:\n")
    beispiel.fuellen(reg)
    _korb(reg, wg)
    print("\nAus Sicht des Jobcenters:\n")
    _korb(reg, jc)

    print("\n— Herr Schmidt: Die Wohngeldstelle bewilligt am 09.11. rückwirkend ab August 280 €/Monat —\n")
    erg = reg.melden(wg, "wohngeld", {
        "aktenzeichen": "WG-2026-1102", "person": beispiel.SCHMIDT, "status": "bewilligt", "antrag_am": "2026-08-12",
        "bescheid_am": "2026-11-09", "von": "2026-08-01", "bis": "2027-07-31",
        "monate": beispiel.monate("2026-08", "2027-07", 28000)})
    print("  Antwort an das Wohngeld-Fachverfahren, noch vor der Auszahlung:")
    for e in erg["einbehalten"]:
        print(f"    {e['monat']}: {euro(e['betrag_cent'])} an {reg.name(e['an'])} statt an den Bürger ({e['status']})")
    print("\n  Jobcenter-Arbeitskorb jetzt:")
    _korb(reg, jc)

    nr = next(e["id"] for e in reg.erstattungen(wg) if e["verpflichtet_az"] == "WG-2026-1102")
    reg.als_erstattet(wg, nr)
    print(f"\n  Die Wohngeldstelle überweist und markiert Nr. {nr} als erstattet. Kein Brief, keine Rückfrage.")

    print("\n— Frau Müller: Die Wohngeldstelle hebt auf, d. h. Wohngeld ab November 0 € —\n")
    reg.melden(wg, "wohngeld", {
        "aktenzeichen": "WG-2026-0815", "person": beispiel.MUELLER, "status": "eingestellt", "antrag_am": "2026-05-04",
        "bescheid_am": "2026-11-10", "von": "2026-06-01", "bis": "2026-10-31",
        "monate": beispiel.monate("2026-06", "2026-10", 31200, gezahlt_bis="2026-10")
        + [{"monat": "2026-11", "anspruch_cent": 0, "gezahlt_cent": 31200}]})
    offen = [a for a in reg.arbeitskorb(wg, protokollieren=False) if a["aktenzeichen"] == "WG-2026-0815"]
    print(f"  Offene Aufgaben zu WG-2026-0815: {len(offen)}. Die Erstattung von 312 € läuft weiter.")
    print("\nZusammenfassung Erstattungen:")
    for b in (jc, wg):
        for e in reg.erstattungen(b, "ausgehend"):
            print(f"  Nr. {e['id']}: {e['berechtigt_name']} ← {e['verpflichtet_name']}, {e['zeitraum']}, "
                  f"{euro(e['summe_cent'])}, Status {e['status']}{' (automatisch)' if e['automatisch'] else ''}")


def _konfig(pfad):
    with open(pfad, encoding="utf-8") as f:
        behoerden = json.load(f).get("behoerden", {})
    schluessel = {}
    for bid, b in behoerden.items():
        if b.get("art") not in ("jobcenter", "wohngeld") or len(b.get("schluessel_sha256", "")) != 64:
            sys.exit(f"Ungültiger Eintrag '{bid}' in {pfad}: art und schluessel_sha256 nötig")
        schluessel[b["schluessel_sha256"].lower()] = bid
    return behoerden, schluessel


def main(argv=None):
    ap = argparse.ArgumentParser(prog="leistungsabgleich", description="Datenaustausch Jobcenter ↔ Wohngeldstelle")
    sub = ap.add_subparsers(dest="befehl", required=True)
    s = sub.add_parser("serve", help="Schnittstelle und Weboberfläche starten")
    s.add_argument("--db", default="abgleich.db")
    s.add_argument("--konfig", default="behoerden.json")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    s.add_argument("--zertifikat", help="TLS-Zertifikat (PEM)")
    s.add_argument("--zertifikat-schluessel", help="Privater TLS-Schlüssel (PEM)")
    s.add_argument("--demo", action="store_true", help="Beispielfälle im Speicher, feste Demo-Schlüssel")
    sub.add_parser("demo", help="Beispielablauf im Terminal")
    sub.add_parser("schluessel", help="API-Schlüssel erzeugen")
    ps = sub.add_parser("pseudonym", help="Pseudonym berechnen")
    ps.add_argument("nachname")
    ps.add_argument("vorname")
    ps.add_argument("geburtsdatum", help="JJJJ-MM-TT")
    a = sub.add_parser("aufraeumen", help="Löschfristen anwenden")
    a.add_argument("--db", default="abgleich.db")
    a.add_argument("--faelle-monate", type=int, default=24)
    a.add_argument("--erstattungen-monate", type=int, default=48)
    a.add_argument("--protokoll-monate", type=int, default=24)
    args = ap.parse_args(argv)

    if args.befehl == "demo":
        demo()
    elif args.befehl == "schluessel":
        k = secrets.token_urlsafe(32)
        print(f"API-Schlüssel (nur der Behörde geben):  {k}\nschluessel_sha256 für behoerden.json:   {schluessel_hash(k)}")
    elif args.befehl == "pseudonym":
        key = os.environ.get("ABGLEICH_SCHLUESSEL")
        if not key:
            ap.error("Umgebungsvariable ABGLEICH_SCHLUESSEL fehlt (gemeinsamer Schlüssel der Behörden)")
        print(pseudonym(key.encode(), args.nachname, args.vorname, args.geburtsdatum))
    elif args.befehl == "aufraeumen":
        print(Register(args.db).aufraeumen(faelle_monate=args.faelle_monate,
                                           erstattungen_monate=args.erstattungen_monate,
                                           protokoll_monate=args.protokoll_monate))
    else:
        demo_keys = None
        if args.demo:
            behoerden = beispiel.BEHOERDEN
            demo_keys = {"Jobcenter Musterstadt": "demo-jobcenter", "Wohngeldstelle Musterstadt": "demo-wohngeld"}
            schluessel = {schluessel_hash("demo-jobcenter"): beispiel.JC, schluessel_hash("demo-wohngeld"): beispiel.WG}
            reg = beispiel.fuellen(Register(behoerden=behoerden))
        else:
            behoerden, schluessel = _konfig(args.konfig)
            reg = Register(args.db, behoerden)
        server = ThreadingHTTPServer((args.host, args.port), make_handler(reg, schluessel, demo_keys))
        schema = "http"
        if args.zertifikat:
            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(args.zertifikat, args.zertifikat_schluessel)
            server.socket = ctx.wrap_socket(server.socket, server_side=True)
            schema = "https"
        print(f"Leistungsabgleich läuft auf {schema}://{args.host}:{server.server_port}"
              + ("  (Demo: Schlüssel demo-jobcenter / demo-wohngeld)" if args.demo else ""), file=sys.stderr)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
