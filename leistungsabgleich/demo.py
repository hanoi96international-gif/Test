"""Beispielfälle für Vorführung und Tests. Alle Personen sind erfunden."""

from .register import Register, pseudonym

SCHLUESSEL = b"nur-fuer-die-demo"
JC, WG = "jc-musterstadt", "wg-musterstadt"
BEHOERDEN = {
    JC: {"art": "jobcenter", "name": "Jobcenter Musterstadt", "auto_anerkennung_bis_cent": 200000},
    WG: {"art": "wohngeld", "name": "Wohngeldstelle Musterstadt", "auto_anerkennung_bis_cent": 200000},
}


def p(nachname, vorname, geburtsdatum):
    return pseudonym(SCHLUESSEL, nachname, vorname, geburtsdatum)


def monate(von, bis, anspruch, gezahlt_bis=None, gezahlt=None):
    """Monatsliste von..bis (JJJJ-MM). Bis einschließlich gezahlt_bis gilt der Monat als ausgezahlt."""
    j, m = map(int, von.split("-"))
    out = []
    while f"{j:04d}-{m:02d}" <= bis:
        mon = f"{j:04d}-{m:02d}"
        bezahlt = gezahlt_bis is not None and mon <= gezahlt_bis
        out.append({"monat": mon, "anspruch_cent": anspruch,
                    "gezahlt_cent": (anspruch if gezahlt is None else gezahlt) if bezahlt else 0})
        j, m = (j + 1, 1) if m == 12 else (j, m + 1)
    return out


MUELLER = p("Müller", "Anna", "1985-03-14")
SCHMIDT = p("Schmidt", "Jonas", "1979-11-02")
YILMAZ, YILMAZ_FRAU = p("Yılmaz", "Emre", "1982-06-30"), p("Yılmaz", "Elif", "1984-01-12")
YILMAZ_KINDER = [p("Yılmaz", "Can", "2012-09-01"), p("Yılmaz", "Deniz", "2016-04-17")]
YILMAZ_OMA = p("Demir", "Ayşe", "1955-02-08")


def fuellen(reg: Register):
    """Drei typische Fälle im Stand Anfang November 2026."""
    # 1) Wohngeld läuft, Bürgergeld wird ab November bewilligt → Wohngeldstelle bekommt Erstattung, hebt nur auf
    reg.melden(WG, "wohngeld", {
        "aktenzeichen": "WG-2026-0815", "person": MUELLER, "status": "bewilligt", "antrag_am": "2026-05-04",
        "bescheid_am": "2026-05-20", "von": "2026-06-01", "bis": "2027-05-31", "kontakt": "Frau Kern, Zi. 104, -2231",
        "monate": monate("2026-06", "2027-05", 31200, gezahlt_bis="2026-11")})
    reg.melden(JC, "jobcenter", {
        "aktenzeichen": "BG-12345", "person": MUELLER, "status": "bewilligt", "antrag_am": "2026-11-03",
        "bescheid_am": "2026-11-06", "von": "2026-11-01", "bis": "2027-04-30", "kontakt": "Herr Ott, Team 3, -4410",
        "monate": monate("2026-11", "2027-04", 89000)})
    # 2) Jobcenter zahlt, Wohngeld ist beantragt → Anspruch dem Grunde nach angemeldet
    reg.melden(JC, "jobcenter", {
        "aktenzeichen": "BG-20777", "person": SCHMIDT, "status": "bewilligt", "antrag_am": "2026-07-01",
        "bescheid_am": "2026-07-10", "von": "2026-07-01", "bis": "2026-12-31", "kontakt": "Frau Aydin, Team 1, -4402",
        "monate": monate("2026-07", "2026-12", 65000, gezahlt_bis="2026-11")})
    reg.melden(WG, "wohngeld", {
        "aktenzeichen": "WG-2026-1102", "person": SCHMIDT, "status": "beantragt", "antrag_am": "2026-08-12",
        "kontakt": "Herr Brandt, Zi. 108, -2236"})
    # 3) Wohngeld rückwirkend bewilligt, Oma lebt mit im Haushalt → automatisch beziffert, aber zur Prüfung
    reg.melden(JC, "jobcenter", {
        "aktenzeichen": "BG-31415", "person": YILMAZ, "haushalt": [YILMAZ_FRAU, *YILMAZ_KINDER], "status": "bewilligt",
        "antrag_am": "2026-08-20", "bescheid_am": "2026-09-02", "von": "2026-09-01", "bis": "2027-02-28",
        "kontakt": "Herr Ott, Team 3, -4410", "monate": monate("2026-09", "2027-02", 140000, gezahlt_bis="2026-11")})
    reg.melden(WG, "wohngeld", {
        "aktenzeichen": "WG-2026-0990", "person": YILMAZ, "haushalt": [YILMAZ_FRAU, *YILMAZ_KINDER, YILMAZ_OMA],
        "status": "bewilligt", "antrag_am": "2026-09-01", "bescheid_am": "2026-11-05", "von": "2026-09-01",
        "bis": "2027-08-31", "kontakt": "Frau Kern, Zi. 104, -2231", "monate": monate("2026-09", "2027-08", 48000)})
    return reg
