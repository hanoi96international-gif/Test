"""OpenAPI-Beschreibung der Schnittstelle für Hersteller der Fachverfahren (GET /openapi.json)."""

from . import __version__

_obj = {"type": "object"}
_fehler = {"description": "Fehler", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Fehler"}}}}
_bearbeiter = {"name": "X-Bearbeiter", "in": "header", "required": False, "schema": {"type": "string", "pattern": "^[A-Za-z0-9._-]{2,40}$"},
               "description": "Kürzel der handelnden Person. Pflicht bei Abgleich, Entscheidung und Erstattung."}
_nr = {"name": "nr", "in": "path", "required": True, "schema": {"type": "integer"}}


def _op(summary, rolle, antwort=None, body=None, params=(), tags=("Sachbearbeitung",)):
    op = {"summary": summary, "tags": list(tags), "description": f"Rolle: {rolle}",
          "parameters": [_bearbeiter, *params],
          "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": antwort or _obj}}},
                        "400": _fehler, "401": _fehler, "403": _fehler, "404": _fehler, "409": _fehler, "429": _fehler}}
    if body:
        op["requestBody"] = {"required": True, "content": {"application/json": {"schema": body}}}
    return op


def _ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "Leistungsabgleich Jobcenter ↔ Wohngeldstelle", "version": __version__,
             "description": "Beta. Beträge in Cent, Datumsangaben ISO 8601, Personen nur als HMAC-SHA256-Pseudonym."},
    "security": [{"apiKey": []}],
    "paths": {
        "/status": {"get": {"summary": "Betriebsbereitschaft (ohne Anmeldung)", "security": [], "tags": ["Betrieb"],
                            "responses": {"200": {"description": "OK"}}}},
        "/ich": {"get": _op("Angemeldete Behörde und Rolle", "alle", tags=("Betrieb",))},
        "/faelle": {"put": _op("Fall melden oder vollständig ersetzen", "fachverfahren", _ref("MeldeAntwort"),
                               _ref("Meldung"), tags=("Fachverfahren",))},
        "/faelle/{aktenzeichen}/abgleich": {"get": _op(
            "Fälle der anderen Stelle zu den Personen eines eigenen Falls", "sachbearbeitung",
            params=[{"name": "aktenzeichen", "in": "path", "required": True, "schema": {"type": "string"}},
                    {"name": "stichtag", "in": "query", "schema": {"type": "string", "format": "date"}}])},
        "/arbeitskorb": {"get": _op("Offene Aufgaben", "sachbearbeitung",
                                    {"type": "array", "items": _ref("Aufgabe")})},
        "/erstattungen": {"get": _op("Erstattungen (format=csv für Tabellenkalkulation)", "sachbearbeitung",
                                     {"type": "array", "items": _ref("Erstattung")}, params=[
                                         {"name": "richtung", "in": "query", "schema": {"enum": ["eingehend", "ausgehend"]}},
                                         {"name": "status", "in": "query", "schema": {"type": "string"}},
                                         {"name": "format", "in": "query", "schema": {"enum": ["json", "csv"]}}])},
        "/erstattungen/{nr}": {"get": _op("Eine Erstattung", "sachbearbeitung", _ref("Erstattung"), params=[_nr])},
        "/erstattungen/{nr}/entscheidung": {"post": _op(
            "Anerkennen, teilweise anerkennen oder ablehnen", "sachbearbeitung", _ref("Erstattung"), {
                "type": "object", "required": ["entscheidung"], "properties": {
                    "entscheidung": {"enum": ["anerkennen", "teilweise", "ablehnen"]},
                    "betrag_cent": {"type": "integer", "description": "nur bei teilweise"},
                    "begruendung": {"type": "string", "maxLength": 1000}}}, [_nr])},
        "/erstattungen/{nr}/erstattet": {"post": _op("Zahlung an die andere Stelle ist erfolgt", "sachbearbeitung",
                                                     _ref("Erstattung"), params=[_nr])},
        "/kennzahlen": {"get": _op("Kennzahlen für die Pilotauswertung", "sachbearbeitung")},
        "/protokoll": {"get": _op("Eigene Zugriffe", "sachbearbeitung")},
        "/feedback": {"post": _op("Rückmeldung zur Beta (ohne personenbezogene Daten)", "alle", body={
            "type": "object", "required": ["text"], "properties": {"text": {"type": "string", "maxLength": 2000},
                                                                   "seite": {"type": "string"}}}, tags=("Betrieb",))},
    },
    "components": {
        "securitySchemes": {"apiKey": {"type": "http", "scheme": "bearer"}},
        "schemas": {
            "Fehler": {"type": "object", "properties": {"fehler": {"type": "string"}}},
            "Monat": {"type": "object", "required": ["monat"], "properties": {
                "monat": {"type": "string", "pattern": r"^\d{4}-(0[1-9]|1[0-2])$"},
                "anspruch_cent": {"type": "integer", "minimum": 0, "description": "festgestellter Anspruch"},
                "gezahlt_cent": {"type": "integer", "minimum": 0, "description": "an den Bürger ausgezahlt"}}},
            "Meldung": {"type": "object", "required": ["aktenzeichen", "person", "status"], "properties": {
                "aktenzeichen": {"type": "string", "maxLength": 64},
                "person": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "haushalt": {"type": "array", "items": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
                "status": {"enum": ["beantragt", "bewilligt", "abgelehnt", "eingestellt"]},
                "antrag_am": {"type": "string", "format": "date"}, "bescheid_am": {"type": "string", "format": "date"},
                "von": {"type": "string", "format": "date"}, "bis": {"type": "string", "format": "date"},
                "kontakt": {"type": "string", "maxLength": 200},
                "monate": {"type": "array", "maxItems": 120, "items": _ref("Monat")}}},
            "MeldeAntwort": {"type": "object", "properties": {
                "aktenzeichen": {"type": "string"},
                "einbehalten": {"type": "array", "description": "vor Auszahlung an den Bürger zurückhalten",
                                "items": {"type": "object", "properties": {
                                    "monat": {"type": "string"}, "betrag_cent": {"type": "integer", "nullable": True},
                                    "hoechstens_cent": {"type": "integer"}, "an": {"type": "string"},
                                    "erstattung": {"type": "integer"}, "status": {"type": "string"}}}},
                "aufgaben": {"type": "array", "items": _ref("Aufgabe")}}},
            "Aufgabe": {"type": "object", "properties": {k: {"type": "string"} for k in (
                "typ", "titel", "text", "aktenzeichen", "partner", "partner_name", "partner_aktenzeichen", "zeitraum")}},
            "Erstattung": {"type": "object", "properties": {
                "id": {"type": "integer"}, "status": {"enum": ["angemeldet", "beziffert", "pruefung", "anerkannt",
                                                               "teilweise_anerkannt", "abgelehnt", "erstattet"]},
                "berechtigt": {"type": "string"}, "verpflichtet": {"type": "string"},
                "summe_cent": {"type": "integer"}, "anerkannt_cent": {"type": "integer", "nullable": True},
                "rechtsgrundlage": {"type": "string"}, "zeitraum": {"type": "string"}}},
        },
    },
}
