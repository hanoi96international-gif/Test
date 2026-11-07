"""Kommandozeile für den Leistungsabgleich (Beta).

Ausprobieren
  leistungsabgleich demo                         Ablauf Schritt für Schritt im Terminal
  leistungsabgleich serve --demo                 Weboberfläche mit Beispielfällen (http://127.0.0.1:8080)
Betrieb
  leistungsabgleich serve --db abgleich.db --konfig behoerden.json [--zertifikat cert.pem --zertifikat-schluessel key.pem]
  leistungsabgleich schluessel --rolle sachbearbeitung   API-Schlüssel und Konfigurationszeile erzeugen
  leistungsabgleich pruefen --konfig behoerden.json      Konfiguration prüfen
  leistungsabgleich wartung --db abgleich.db --sicherungen /pfad   Sicherung + Löschfristen (nächtlich)
  leistungsabgleich sicherung --db abgleich.db ziel.db
  leistungsabgleich aufraeumen --db abgleich.db
  leistungsabgleich feedback --db abgleich.db            Rückmeldungen der Beta-Nutzer anzeigen
Melden ohne Fachverfahrensanbindung (läuft bei der Behörde, Namen verlassen den Rechner nicht)
  ABGLEICH_SCHLUESSEL=… ABGLEICH_API_KEY=… leistungsabgleich melden faelle.csv --url https://… [--probelauf]
  leistungsabgleich pseudonym Müller Anna 1985-03-14

behoerden.json, siehe deploy/behoerden.beispiel.json. Gespeichert werden nur Hashwerte der API-Schlüssel.
auto_anerkennung_bis_cent: Erstattungen bis zu diesem Betrag ohne Prüfhinweis erkennt das System für
diese Behörde automatisch an. Weglassen = immer von Hand.
"""

import argparse
import datetime as dt
import json
import os
import pathlib
import secrets
import ssl
import sys
from http.server import ThreadingHTTPServer

from . import __version__
from . import demo as beispiel
from .api import ROLLEN, make_handler, schluessel_hash
from .erstattung import euro
from .meldeclient import CsvFehler, lesen, senden
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


def konfig_laden(pfad):
    """behoerden.json lesen und prüfen. Rückgabe: (behoerden, {hash: (id, rolle)})."""
    try:
        with open(pfad, encoding="utf-8") as f:
            behoerden = json.load(f).get("behoerden", {})
    except (OSError, ValueError, AttributeError) as e:
        raise SystemExit(f"Konfiguration {pfad} nicht lesbar: {e}") from None
    if not behoerden:
        raise SystemExit(f"Keine Behörden in {pfad}")
    schluessel, fehler = {}, []
    for bid, b in behoerden.items():
        if b.get("art") not in ("jobcenter", "wohngeld"):
            fehler.append(f"{bid}: art muss jobcenter oder wohngeld sein")
        grenze = b.get("auto_anerkennung_bis_cent")
        if grenze is not None and (not isinstance(grenze, int) or grenze < 0):
            fehler.append(f"{bid}: auto_anerkennung_bis_cent muss eine ganze Zahl ≥ 0 sein")
        eintraege = list(b.get("schluessel", []))
        if b.get("schluessel_sha256"):  # Format der Version 2.0
            eintraege.append({"sha256": b["schluessel_sha256"], "rolle": "alle"})
        if not eintraege:
            fehler.append(f"{bid}: kein Schlüssel eingetragen")
        for e in eintraege:
            h, rolle = str(e.get("sha256", "")).lower(), e.get("rolle")
            if len(h) != 64 or rolle not in ROLLEN:
                fehler.append(f"{bid}: Schlüssel braucht sha256 (64 Zeichen) und rolle {'/'.join(ROLLEN)}")
            elif h in schluessel:
                fehler.append(f"{bid}: Schlüssel ist doppelt vergeben")
            else:
                schluessel[h] = (bid, rolle)
    if fehler:
        raise SystemExit("Konfigurationsfehler:\n  " + "\n  ".join(fehler))
    return behoerden, schluessel


def wartung(db, ordner, behalten=14):
    """Tägliche Sicherung mit Datum im Namen, alte Sicherungen löschen, Löschfristen anwenden."""
    reg = Register(db)
    ziel = pathlib.Path(ordner)
    ziel.mkdir(parents=True, exist_ok=True)
    datei = ziel / f"abgleich-{dt.datetime.now():%Y-%m-%d-%H%M}.db"
    reg.sicherung(str(datei))
    os.chmod(datei, 0o600)
    alte = sorted(ziel.glob("abgleich-*.db"))[:-behalten] if behalten > 0 else []
    for a in alte:
        a.unlink()
    return {"sicherung": str(datei), "alte_geloescht": len(alte), "geloescht": reg.aufraeumen()}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="leistungsabgleich", description="Datenaustausch Jobcenter ↔ Wohngeldstelle")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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
    k = sub.add_parser("schluessel", help="API-Schlüssel erzeugen")
    k.add_argument("--rolle", choices=ROLLEN, default="sachbearbeitung")
    pr = sub.add_parser("pruefen", help="Konfiguration prüfen")
    pr.add_argument("--konfig", default="behoerden.json")
    ps = sub.add_parser("pseudonym", help="Pseudonym berechnen")
    ps.add_argument("nachname")
    ps.add_argument("vorname")
    ps.add_argument("geburtsdatum", help="JJJJ-MM-TT")
    a = sub.add_parser("aufraeumen", help="Löschfristen anwenden")
    a.add_argument("--db", default="abgleich.db")
    a.add_argument("--faelle-monate", type=int, default=24)
    a.add_argument("--erstattungen-monate", type=int, default=48)
    a.add_argument("--protokoll-monate", type=int, default=24)
    si = sub.add_parser("sicherung", help="Datenbank im laufenden Betrieb sichern")
    si.add_argument("--db", default="abgleich.db")
    si.add_argument("ziel")
    w = sub.add_parser("wartung", help="Sicherung + Löschfristen, für den nächtlichen Timer")
    w.add_argument("--db", default="abgleich.db")
    w.add_argument("--sicherungen", required=True, help="Ordner für Sicherungen")
    w.add_argument("--behalten", type=int, default=14, help="Anzahl Sicherungen, die bleiben")
    fb = sub.add_parser("feedback", help="Rückmeldungen anzeigen")
    fb.add_argument("--db", default="abgleich.db")
    me = sub.add_parser("melden", help="Fälle aus CSV melden (Pilot ohne Fachverfahrensanbindung)")
    me.add_argument("csv")
    me.add_argument("--url", default=os.environ.get("ABGLEICH_URL"))
    me.add_argument("--bearbeiter", help="Kürzel fürs Protokoll")
    me.add_argument("--ca", help="CA-Zertifikat der Behörde (PEM) für https")
    me.add_argument("--probelauf", action="store_true", help="nur prüfen und anzeigen, nichts senden")
    args = ap.parse_args(argv)

    if args.befehl == "demo":
        demo()
    elif args.befehl == "schluessel":
        k = secrets.token_urlsafe(32)
        print(f"API-Schlüssel (nur der Behörde geben, nicht speichern):\n  {k}\n"
              f"Eintrag für behoerden.json unter \"schluessel\":\n  "
              + json.dumps({"sha256": schluessel_hash(k), "rolle": args.rolle, "bezeichnung": "…"}))
    elif args.befehl == "pruefen":
        behoerden, schluessel = konfig_laden(args.konfig)
        for bid, b in behoerden.items():
            rollen = sorted(r for h, (i, r) in schluessel.items() if i == bid)
            print(f"  {bid}: {b.get('name', bid)} ({b['art']}), Schlüssel: {', '.join(rollen)}, "
                  f"automatisch anerkennen bis {euro(b.get('auto_anerkennung_bis_cent'))}")
        print("Konfiguration ist in Ordnung.")
    elif args.befehl == "pseudonym":
        key = os.environ.get("ABGLEICH_SCHLUESSEL")
        if not key:
            ap.error("Umgebungsvariable ABGLEICH_SCHLUESSEL fehlt (gemeinsamer Schlüssel der Behörden)")
        print(pseudonym(key.encode(), args.nachname, args.vorname, args.geburtsdatum))
    elif args.befehl == "aufraeumen":
        print(Register(args.db).aufraeumen(faelle_monate=args.faelle_monate,
                                           erstattungen_monate=args.erstattungen_monate,
                                           protokoll_monate=args.protokoll_monate))
    elif args.befehl == "sicherung":
        Register(args.db).sicherung(args.ziel)
        print(f"Gesichert nach {args.ziel}")
    elif args.befehl == "wartung":
        print(json.dumps(wartung(args.db, args.sicherungen, args.behalten), ensure_ascii=False))
    elif args.befehl == "feedback":
        for f in Register(args.db).feedback_liste():
            print(f"{f['zeit'][:16]}  {f['behoerde']}  {f['bearbeiter'] or '-'}  [{f['seite'] or '-'}]  {f['text']}")
    elif args.befehl == "melden":
        return _melden(ap, args)
    else:
        _serve(args)


def _melden(ap, args):
    key = os.environ.get("ABGLEICH_SCHLUESSEL")
    if not key:
        ap.error("Umgebungsvariable ABGLEICH_SCHLUESSEL fehlt (gemeinsamer Pseudonym-Schlüssel)")
    try:
        meldungen = lesen(pathlib.Path(args.csv).read_text(encoding="utf-8-sig"), key.encode())
    except (OSError, UnicodeDecodeError, CsvFehler) as e:
        sys.exit(f"Fehler in {args.csv}: {e}")
    if args.probelauf:
        print(json.dumps(meldungen, ensure_ascii=False, indent=2))
        print(f"{len(meldungen)} Fälle geprüft, nichts gesendet.", file=sys.stderr)
        return 0
    api_key = os.environ.get("ABGLEICH_API_KEY")
    if not (args.url and api_key):
        ap.error("--url (oder ABGLEICH_URL) und Umgebungsvariable ABGLEICH_API_KEY nötig")
    fehler = 0
    for e in senden(meldungen, args.url, api_key, args.bearbeiter, args.ca):
        if not e["ok"]:
            fehler += 1
            print(f"  ✗ {e['aktenzeichen']}: {e['fehler']}")
            continue
        print(f"  ✓ {e['aktenzeichen']}")
        for x in e["einbehalten"]:
            print(f"      einbehalten {x['monat']}: {euro(x['betrag_cent']) if x['betrag_cent'] is not None else 'bis ' + euro(x['hoechstens_cent'])} → {x['an']}")
        for a in e["aufgaben"]:
            print(f"      Aufgabe: {a['titel']}")
    print(f"{len(meldungen) - fehler} von {len(meldungen)} Fällen gemeldet.")
    return 1 if fehler else 0


def _serve(args):
    demo_keys = None
    if args.demo:
        behoerden = beispiel.BEHOERDEN
        demo_keys = {"Jobcenter Musterstadt": "demo-jobcenter", "Wohngeldstelle Musterstadt": "demo-wohngeld"}
        schluessel = {schluessel_hash("demo-jobcenter"): (beispiel.JC, "alle"),
                      schluessel_hash("demo-wohngeld"): (beispiel.WG, "alle")}
        reg = beispiel.fuellen(Register(behoerden=behoerden))
    else:
        behoerden, schluessel = konfig_laden(args.konfig)
        reg = Register(args.db, behoerden)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(reg, schluessel, demo_keys))
    server.daemon_threads = True
    schema = "http"
    if args.zertifikat:
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(args.zertifikat, args.zertifikat_schluessel)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        schema = "https"
    elif args.host not in ("127.0.0.1", "localhost", "::1") and not args.demo:
        print("WARNUNG: ohne --zertifikat unverschlüsselt erreichbar. Nur hinter einem TLS-Proxy betreiben.",
              file=sys.stderr)
    print(f"Leistungsabgleich {__version__} läuft auf {schema}://{args.host}:{server.server_port}"
          + ("  (Demo: Schlüssel demo-jobcenter / demo-wohngeld)" if args.demo else ""), file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
