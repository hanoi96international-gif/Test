"""Erstattungslogik zwischen Jobcenter und Wohngeldstelle, als reine Funktionen ohne Speicher.

Grundregel je Kalendermonat, in dem beide Stellen einen Anspruch festgestellt haben:
Wer schon an den Bürger gezahlt hat, bekommt seine Leistung aus dem noch nicht ausgezahlten
Betrag der anderen Stelle erstattet, höchstens in dessen Höhe (§ 104 Abs. 3 SGB X).

* Jobcenter hat gezahlt, Wohngeld wird rückwirkend bewilligt
  → Jobcenter ist erstattungsberechtigt (§ 104 SGB X i. V. m. § 40a SGB II).
* Wohngeld wurde gezahlt, Bürgergeld wird rückwirkend bewilligt
  → Wohngeldstelle ist erstattungsberechtigt (§ 103 SGB X, Wohngeld entfällt nach § 7 WoGG).

Ist die andere Leistung erst beantragt, wird der Anspruch dem Grunde nach angemeldet
(Fristwahrung nach § 111 SGB X) und später automatisch beziffert.
"""

JC, WG = "jobcenter", "wohngeld"
ARTEN = {JC: "Jobcenter (SGB II)", WG: "Wohngeldstelle (WoGG)"}
RECHTSGRUNDLAGE = {
    JC: "§ 104 SGB X i. V. m. § 40a SGB II",
    WG: "§ 103 SGB X (Wohngeldanspruch nachträglich entfallen, § 7 Abs. 1 WoGG)",
}
OFFEN = ("angemeldet", "beziffert", "pruefung")          # wird bei jeder Meldung neu berechnet
BINDEND = ("anerkannt", "teilweise_anerkannt", "erstattet")
ENTSCHIEDEN = BINDEND + ("abgelehnt",)                     # Monate werden nicht erneut gefordert

LEER = {"anspruch": 0, "gezahlt": 0}


def andere(art: str) -> str:
    return WG if art == JC else JC


def euro(cent: int | None) -> str:
    if cent is None:
        return "–"
    text = f"{cent / 100:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"{text} €"


def zeitraum(monate) -> str:
    """['2026-11', '2026-12', '2027-02'] → '11/2026–12/2026, 02/2027'"""
    def nr(m):
        return int(m[:4]) * 12 + int(m[5:7]) - 1

    def fmt(m):
        return f"{m[5:7]}/{m[:4]}"

    ms = sorted(set(monate))
    teile, start = [], 0
    for i in range(1, len(ms) + 1):
        if i == len(ms) or nr(ms[i]) != nr(ms[i - 1]) + 1:
            a, b = ms[start], ms[i - 1]
            teile.append(fmt(a) if a == b else f"{fmt(a)}–{fmt(b)}")
            start = i
    return ", ".join(teile)


def summe(positionen: dict) -> int:
    return sum(p["betrag"] or 0 for p in positionen.values())


def _m(fall, monat):
    return fall["monate"].get(monat, LEER)


def auswerten(faelle: dict, erstattungen: list[dict]) -> dict:
    """Berechnet, was in welcher Richtung zu erstatten ist.

    faelle: {JC: fall, WG: fall}; erstattungen: bestehende Erstattungen dieses Fallpaars.
    Rückgabe: soll {richtung: {monat: {betrag, hoechstens}}}, unklar, doppelbezug, korrektur {id: [monate]}.
    """
    entschieden = {JC: set(), WG: set()}
    for e in erstattungen:
        if e["status"] in ENTSCHIEDEN:
            entschieden[e["berechtigt_art"]] |= set(e["positionen"])

    soll, unklar, doppel = {JC: {}, WG: {}}, [], []
    for m in sorted(set(faelle[JC]["monate"]) | set(faelle[WG]["monate"])):
        kandidat = {}
        for d in (JC, WG):
            x, y = faelle[d], faelle[andere(d)]
            gezahlt = _m(x, m)["gezahlt"]
            if gezahlt <= 0 or m in entschieden[d]:
                continue
            if not y["monate"]:  # andere Leistung noch nicht beschieden
                if y["status"] == "beantragt" and y.get("antrag_am") and m >= y["antrag_am"][:7]:
                    kandidat[d] = {"betrag": None, "hoechstens": gezahlt}
                continue
            ym = _m(y, m)
            betrag = min(gezahlt, ym["anspruch"] - ym["gezahlt"])
            if betrag > 0:
                kandidat[d] = {"betrag": betrag, "hoechstens": gezahlt}
        for d, pos in kandidat.items():
            soll[d][m] = pos
        if len(kandidat) == 2:
            unklar.append(m)
        abgedeckt = m in entschieden[JC] or m in entschieden[WG]
        if not kandidat and not abgedeckt and _m(faelle[JC], m)["gezahlt"] > 0 and _m(faelle[WG], m)["gezahlt"] > 0:
            doppel.append(m)

    # Anerkannt, aber die verpflichtete Stelle hat trotzdem mehr an den Bürger ausgezahlt als übrig war
    korrektur = {}
    for e in erstattungen:
        if e["status"] in BINDEND:
            y = faelle[andere(e["berechtigt_art"])]
            falsch = [m for m, p in e["positionen"].items()
                      if p["betrag"] and _m(y, m)["anspruch"] - _m(y, m)["gezahlt"] < p["betrag"]]
            if falsch:
                korrektur[e["id"]] = falsch
    return {"soll": soll, "unklar": unklar, "doppelbezug": doppel, "korrektur": korrektur}


def kuerzen(positionen: dict, betrag: int) -> dict:
    """Teilanerkennung: kürzt von den jüngsten Monaten her auf den anerkannten Gesamtbetrag."""
    if not 0 < betrag < summe(positionen):
        raise ValueError("Teilbetrag muss größer 0 und kleiner als die Forderung sein")
    zuviel, neu = summe(positionen) - betrag, {m: dict(p) for m, p in positionen.items()}
    for m in sorted(neu, reverse=True):
        weg = min(zuviel, neu[m]["betrag"] or 0)
        neu[m]["betrag"] -= weg
        zuviel -= weg
    return neu


def _aufgabe(fall, typ, titel, text, partner=None, erstattung=None, aktionen=(), prioritaet=3, monate=()):
    return {"behoerde": fall["behoerde"], "aktenzeichen": fall["aktenzeichen"], "typ": typ, "titel": titel,
            "text": text, "partner": partner["behoerde"] if partner else None,
            "partner_aktenzeichen": partner["aktenzeichen"] if partner else None,
            "erstattung": erstattung, "aktionen": list(aktionen), "prioritaet": prioritaet,
            "zeitraum": zeitraum(monate) if monate else None}


def aufgaben_paar(jc: dict, wg: dict, erstattungen: list[dict], name=lambda b: b) -> list[dict]:
    """Aufhebungen, Doppelbezug und Klärungsbedarf für ein Fallpaar, für beide Seiten."""
    faelle = {JC: jc, WG: wg}
    gueltig = [e for e in erstattungen if e["status"] != "abgelehnt"]
    abgedeckt, gedeckt_betrag = {JC: set(), WG: set()}, {JC: {}, WG: {}}
    for e in gueltig:
        d = e["berechtigt_art"]
        for m, p in e["positionen"].items():
            abgedeckt[d].add(m)
            gedeckt_betrag[d][m] = gedeckt_betrag[d].get(m, 0) + (p["betrag"] or 0)

    spaeter = None  # der jüngere Bescheid geht vor, der ältere wird aufgehoben
    if jc.get("bescheid_am") and wg.get("bescheid_am") and jc["bescheid_am"] != wg["bescheid_am"]:
        spaeter = JC if jc["bescheid_am"] > wg["bescheid_am"] else WG

    aufheben, klaeren = {JC: [], WG: []}, []
    for m in sorted(set(jc["monate"]) & set(wg["monate"])):
        if not (jc["monate"][m]["anspruch"] > 0 and wg["monate"][m]["anspruch"] > 0):
            continue
        if m in abgedeckt[JC]:
            continue  # Jobcenter hat geleistet, die Erstattung erfüllt den Wohngeldanspruch (§ 107 SGB X)
        if m in abgedeckt[WG]:
            aufheben[WG].append(m)
        elif spaeter:
            aufheben[andere(spaeter)].append(m)
        else:
            klaeren.append(m)

    out = []
    for d, ms in aufheben.items():
        if not ms:
            continue
        f, o = faelle[d], faelle[andere(d)]
        zr = zeitraum(ms)
        if d == WG:
            text = (f"Bürgergeld ist bewilligt ({name(o['behoerde'])}, {o['aktenzeichen']}). Wohngeldbescheid für "
                    f"{zr} aufheben bzw. Unwirksamkeit feststellen (§§ 7, 28 WoGG).")
        else:
            text = (f"Wohngeld ist bewilligt ({name(o['behoerde'])}, {o['aktenzeichen']}) und geht vor (§ 12a SGB II). "
                    f"Bewilligung für {zr} aufheben oder Wohngeld als Einkommen anrechnen (§ 48 SGB X).")
        gezahlt = sum(f["monate"][m]["gezahlt"] for m in ms)
        gedeckt = sum(gedeckt_betrag[d].get(m, 0) for m in ms)
        if gedeckt:
            text += f" Bereits gezahlte {euro(gedeckt)} erstattet {name(o['behoerde'])}."
        if gezahlt - gedeckt > 0:
            text += f" Beim Bürger zurückzufordern: {euro(gezahlt - gedeckt)} (§ 50 SGB X)."
        elif gezahlt:
            text += " Keine Rückforderung beim Bürger nötig."
        out.append(_aufgabe(f, "aufheben", "Bescheid aufheben", text, o, monate=ms, prioritaet=3))

    erg = auswerten(faelle, erstattungen)
    for d in (JC, WG):
        f, o = faelle[d], faelle[andere(d)]
        if klaeren:
            out.append(_aufgabe(f, "klaeren", "Vorrang klären", (
                f"Die Bewilligungen überschneiden sich in {zeitraum(klaeren)}. Mit {name(o['behoerde'])} abstimmen, "
                "welche Leistung vorgeht (§ 12a SGB II, § 7 WoGG). Tipp: Bescheiddatum mitmelden, dann entscheidet "
                "das System automatisch."), o, monate=klaeren))
        if erg["doppelbezug"]:
            out.append(_aufgabe(f, "doppelbezug", "Doppelbezug", (
                f"In {zeitraum(erg['doppelbezug'])} haben beide Stellen voll an den Bürger gezahlt. Eine Erstattung "
                "zwischen den Behörden ist nicht mehr möglich. Vorrang klären und Überzahlung zurückfordern "
                "(§ 50 SGB X)."), o, monate=erg["doppelbezug"], prioritaet=2))
    return out


def aufgaben_erstattung(e: dict, name=lambda b: b) -> list[dict]:
    """Aufgaben der erstattungspflichtigen Stelle zu einer Erstattung."""
    y = {"behoerde": e["verpflichtet"], "aktenzeichen": e["verpflichtet_az"]}
    x = {"behoerde": e["berechtigt"], "aktenzeichen": e["berechtigt_az"]}
    ms, nr, wer = list(e["positionen"]), e["id"], name(e["berechtigt"])
    out = []
    if e["status"] == "angemeldet":
        hoechstens = sum(p["hoechstens"] for p in e["positionen"].values())
        out.append(_aufgabe(y, "einbehalten", "Nachzahlung einbehalten", (
            f"{wer} hat für {zeitraum(ms)} geleistet und den Erstattungsanspruch Nr. {nr} dem Grunde nach angemeldet "
            f"(§ 111 SGB X). Bei Bewilligung bis zu {euro(hoechstens)} nicht an den Bürger auszahlen. "
            "Der Betrag wird nach der Bewilligung automatisch berechnet."), x, nr, monate=ms, prioritaet=1))
    elif e["status"] in ("beziffert", "pruefung"):
        text = (f"{wer} fordert {euro(summe(e['positionen']))} für {zeitraum(ms)} ({e['rechtsgrundlage']}). "
                "Der Betrag ist automatisch aus den gemeldeten Monatsbeträgen berechnet. Bis zur Entscheidung "
                "nicht an den Bürger auszahlen.")
        if e["pruefhinweise"]:
            text += " Bitte prüfen: " + " ".join(e["pruefhinweise"])
        out.append(_aufgabe(y, "erstattung_pruefen", "Erstattung prüfen", text, x, nr,
                            ("anerkennen", "teilweise", "ablehnen"), 2, ms))
    elif e["status"] in ("anerkannt", "teilweise_anerkannt"):
        wie = "automatisch anerkannt" if e["automatisch"] else "anerkannt"
        out.append(_aufgabe(y, "erstattung_zahlen", "Erstattung auszahlen", (
            f"{euro(e['anerkannt_cent'])} an {wer} erstatten (Nr. {nr}, {wie}), danach als erstattet markieren. "
            f"Diesen Betrag nicht an den Bürger auszahlen."), x, nr, ("erstattet",), 4, ms))
    if e.get("korrektur"):
        out.append(_aufgabe(y, "korrektur", "Auszahlung trotz Erstattung", (
            f"Für Erstattung Nr. {nr} wurde in {zeitraum(e['korrektur'])} mehr an den Bürger ausgezahlt als nach "
            "der Erstattung übrig war. Überzahlung prüfen und zurückfordern (§ 50 SGB X)."), x, nr,
            monate=e["korrektur"], prioritaet=1))
    return out
