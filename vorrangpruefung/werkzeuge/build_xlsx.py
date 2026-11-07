"""Erzeugt die Excel-Fassung der Vorrangprüfung Wolfsburg (nur Formeln, keine festen Ergebnisse)."""
import sys, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter as L

OUT = sys.argv[1] if len(sys.argv) > 1 else "Vorrangpruefung_Wolfsburg.xlsx"
wb = Workbook()
F = "Arial"
f_norm = Font(name=F, size=10)
f_bold = Font(name=F, size=10, bold=True)
f_h1 = Font(name=F, size=16, bold=True, color="0D3B4A")
f_h2 = Font(name=F, size=12, bold=True, color="0D3B4A")
f_in = Font(name=F, size=10, color="0000FF")
f_link = Font(name=F, size=10, color="008000")
f_small = Font(name=F, size=9, color="587078")
fill_in = PatternFill("solid", fgColor="FFF2CC")
fill_head = PatternFill("solid", fgColor="DBEEF2")
fill_res = PatternFill("solid", fgColor="E0F3E8")
thin = Side(style="thin", color="D3DDE3")
box = Border(left=thin, right=thin, top=thin, bottom=thin)
EUR = '#,##0.00 "€";-#,##0.00 "€";"–"'
EUR0 = '#,##0 "€";-#,##0 "€";"–"'
PCT = '0.0%'

def name(n, ref):
    wb.defined_names[n] = DefinedName(n, attr_text=ref)

def absref(ws, cell):
    c = ws[cell]
    return f"'{ws.title}'!${c.column_letter}${c.row}"

def rng(ws, c1, c2):
    a, b = ws[c1], ws[c2]
    return f"'{ws.title}'!${a.column_letter}${a.row}:${b.column_letter}${b.row}"

# ---------------------------------------------------------------- Parameter
P = wb.active; P.title = "Parameter"
P["A1"] = "Parameter und Quellen (Rechtsstand 07.11.2026)"; P["A1"].font = f_h1
P["A2"] = "Blaue Werte sind Annahmen bzw. Rechtswerte und dürfen bei Rechtsänderungen angepasst werden. Alle Formeln verweisen auf diese Zellen."; P["A2"].font = f_small
for col, w in zip("ABCD", (52, 14, 10, 90)): P.column_dimensions[col].width = w
pr = [4]
def ph(title):
    r = pr[0]; P.cell(r, 1, title).font = f_h2; pr[0] += 1
def pv(label, nm, val, unit="", src="", fmt=None):
    r = pr[0]
    P.cell(r, 1, label).font = f_norm
    c = P.cell(r, 2, val); c.font = f_in
    if fmt: c.number_format = fmt
    P.cell(r, 3, unit).font = f_small
    P.cell(r, 4, src).font = f_small
    name(nm, absref(P, c.coordinate)); pr[0] += 1
def ptab(label, nm, vals, unit="", src="", fmt=None, labels=None):
    r0 = pr[0]
    P.cell(r0, 1, label).font = f_bold; P.cell(r0, 4, src).font = f_small; pr[0] += 1
    first = pr[0]
    for i, v in enumerate(vals):
        r = pr[0]
        P.cell(r, 1, ("   " + labels[i]) if labels else f"   {i+1}").font = f_norm
        c = P.cell(r, 2, v); c.font = f_in
        if fmt: c.number_format = fmt
        P.cell(r, 3, unit).font = f_small
        pr[0] += 1
    name(nm, f"'Parameter'!$B${first}:$B${pr[0]-1}")

ph("Datum")
pv("Rechenjahr", "p_Jahr", "=YEAR(TODAY())", "", "Aktuelles Datum (Regelaltersgrenze, Karenzzeit)")
pv("Rechenmonat", "p_Monat", "=MONTH(TODAY())", "")
ph("Regelbedarfe 2026 (Anlage zu § 28 SGB XII, § 20 SGB II)")
for i, v in enumerate((563, 506, 451, 471, 390, 357), 1):
    pv(f"Regelbedarfsstufe {i}", f"p_RBS{i}", v, "€", "Anlage zu § 28 SGB XII, gültig ab 01.01.2026" if i == 1 else "", EUR)
pv("Kindergeld je Kind", "p_KG", 259, "€", "§ 66 Abs. 1 EStG", EUR)
ph("Freibeträge Erwerbstätige (§ 11b SGB II)")
pv("Grundfreibetrag", "p_FB_Grund", 100, "€", "§ 11b Abs. 2 SGB II", EUR)
pv("Stufe 1 bis", "p_FB_G1", 520, "€", "§ 11b Abs. 3 Nr. 1", EUR)
pv("Quote Stufe 1", "p_FB_Q1", 0.2, "", "", PCT)
pv("Stufe 2 bis", "p_FB_G2", 1000, "€", "§ 11b Abs. 3 Nr. 2", EUR)
pv("Quote Stufe 2", "p_FB_Q2", 0.3, "", "", PCT)
pv("Obergrenze ohne Kind", "p_FB_G3O", 1200, "€", "§ 11b Abs. 3 Nr. 3", EUR)
pv("Obergrenze mit Kind", "p_FB_G3M", 1500, "€", "§ 11b Abs. 3 Satz 2", EUR)
pv("Quote Stufe 3", "p_FB_Q3", 0.1, "", "", PCT)
pv("Versicherungspauschale (ohne Erwerb)", "p_Pausch", 30, "€", "§ 6 Bürgergeld-V", EUR)
pv("Minijob-Grenze (Freibetrag Azubis/Schüler)", "p_Minijob", 603, "€", "§ 8 Abs. 1a SGB IV; § 11b Abs. 2b SGB II", EUR)
ph("Mehrbedarfe (§ 21 SGB II, §§ 23, 30 SGB XII)")
pv("Schwangerschaft", "p_MB_Schw", 0.17, "", "§ 21 Abs. 2 SGB II (nach der 12. Woche)", PCT)
pv("Merkzeichen G (nicht erwerbsfähig)", "p_MB_G", 0.17, "", "§ 23 Nr. 4 SGB II, § 30 Abs. 1 SGB XII", PCT)
pv("Warmwasser dezentral Erwachsene / 18–24", "p_WW_Erw", 0.023, "", "§ 21 Abs. 7 SGB II", '0.0%')
pv("Warmwasser 14–17", "p_WW_14", 0.014, "", "", '0.0%')
pv("Warmwasser 6–13", "p_WW_6", 0.012, "", "", '0.0%')
pv("Warmwasser 0–5", "p_WW_0", 0.008, "", "", '0.0%')
pv("Schwangerschaft: Mehrbedarf ab Woche", "p_SSW_MB", 13, "", "§ 21 Abs. 2 SGB II")
pv("Schwangerschaft: Kind zählt bei Mietobergrenze ab Woche", "p_SSW_MOG", 12, "", "Vorgabe Jobcenter Wolfsburg (vom Nutzer genannt)")
ph("SGB XII und Grundrente")
pv("SGB XII: Absetzbetrag Erwerbseinkommen", "p_XII_Q", 0.3, "", "§ 82 Abs. 3 SGB XII", PCT)
pv("SGB XII: Höchstbetrag in % RBS 1", "p_XII_Cap", 0.5, "", "§ 82 Abs. 3 SGB XII", PCT)
pv("Grundrente: Sockel", "p_GR_Base", 100, "€", "§ 11b Abs. 2a SGB II i. V. m. § 82a SGB XII; § 17a WoGG", EUR)
pv("Grundrente: Anteil darüber", "p_GR_Q", 0.3, "", "", PCT)
pv("Grundrente: Höchstbetrag in % RBS 1", "p_GR_Cap", 0.5, "", "", PCT)
ph("Mietobergrenzen Wolfsburg (Grundmiete inkl. Betriebskosten)")
ptab("Mietobergrenze nach Personen", "p_MOG", [484.00, 592.20, 706.50, 825.35, 1026.00, 1134.00, 1242.00, 1350.00, 1458.00, 1566.00, 1675.00, 1782.00],
     "€", "Jobcenter Wolfsburg, „Mietgrenzen ab 01.04.2026“ (abgerufen 07.11.2026)", EUR, [f"{i} Person(en)" for i in range(1, 13)])
pv("je weitere Person", "p_MOG_Plus", 108, "€", "Jobcenter Wolfsburg", EUR)
pv("Karenzzeit: Deckel (Faktor)", "p_KarenzF", 1.5, "", "§ 22 Abs. 1 Satz 6 SGB II, § 35 Abs. 1 Satz 7 SGB XII")
pv("Umgang temporär: Anteil der Differenz", "p_UmgTemp", 0.5, "", "Vorgabe Jobcenter Wolfsburg (vom Nutzer genannt)", PCT)
ph("Wohngeld (WoGG, Mietenstufe IV)")
ptab("Höchstbeträge Mietstufe IV", "p_HB", [511, 619, 737, 858, 982], "€", "Anlage 1 WoGG; Wolfsburg = Mietenstufe IV (Anlage WoGV)", EUR, [f"{i} Person(en)" for i in range(1, 6)])
pv("Höchstbetrag je weitere Person", "p_HB_Plus", 119, "€", "Anlage 1 WoGG", EUR)
ptab("Klimakomponente", "p_KL", [19.20, 24.80, 29.60, 34.40, 39.20], "€", "§ 12 Abs. 7 WoGG", EUR, [f"{i} Person(en)" for i in range(1, 6)])
pv("Klimakomponente je weitere Person", "p_KL_Plus", 4.80, "€", "", EUR)
ptab("Heizkostenentlastung (CO2)", "p_HKE", [14.40, 18.60, 22.20, 25.80, 29.40], "€", "§ 12 Abs. 6 WoGG", EUR, [f"{i} Person(en)" for i in range(1, 6)])
pv("Heizkostenentlastung je weitere Person", "p_HKE_Plus", 3.60, "€", "", EUR)
ptab("Dauerhafte Heizkostenkomponente", "p_HKK", [96, 124, 148, 172, 196], "€", "§ 12 Abs. 6 WoGG", EUR, [f"{i} Person(en)" for i in range(1, 6)])
pv("Heizkostenkomponente je weitere Person", "p_HKK_Plus", 24, "€", "", EUR)
ptab("Wert a", "p_a", [4e-2, 3e-2, 2e-2, 1e-2, 0, -1e-2, -2e-2, -3e-2, -4e-2, -6e-2, -9e-2, -1.2e-1], "", "Anlage 2 WoGG", '0.000E+00')
ptab("Wert b", "p_b", [4.797e-4, 3.571e-4, 2.917e-4, 2.163e-4, 1.907e-4, 1.722e-4, 1.592e-4, 1.583e-4, 1.376e-4, 1.249e-4, 1.141e-4, 1.107e-4], "", "Anlage 2 WoGG", '0.000E+00')
ptab("Wert c", "p_c", [4.080e-5, 3.040e-5, 2.450e-5, 1.760e-5, 1.720e-5, 1.660e-5, 1.650e-5, 1.650e-5, 1.660e-5, 1.660e-5, 1.960e-5, 2.210e-5], "", "Anlage 2 WoGG", '0.000E+00')
ptab("Mindestwert M", "p_Mmin", [54, 67, 79, 92, 103, 103, 115, 128, 140, 152, 187, 298], "€", "Anlage 3 Nr. 1 WoGG", EUR)
ptab("Mindestwert Y", "p_Ymin", [396, 679, 906, 1132, 1358, 1585, 1811, 2037, 2264, 2490, 2717, 2943], "€", "Anlage 3 Nr. 1 WoGG", EUR)
pv("Werbungskosten-Pauschbetrag Arbeit", "p_WG_WK", 1230, "€/Jahr", "§ 9a EStG", EUR)
pv("Werbungskosten-Pauschbetrag Rente", "p_WG_RWK", 102, "€/Jahr", "§ 9a EStG", EUR)
pv("Pauschalabzug Rente (KV/PV)", "p_WG_RPa", 0.1, "", "§ 16 WoGG", PCT)
pv("Freibetrag Alleinerziehende (einmal je Haushalt)", "p_WG_AEFrei", 1320, "€/Jahr", "§ 17 Nr. 3 WoGG", EUR)
pv("Freibetrag GdB 100 / Pflege", "p_WG_SB", 1800, "€/Jahr", "§ 17 Nr. 1 WoGG", EUR)
pv("Freibetrag Erwerbseinkommen Kind", "p_WG_KindFrei", 1200, "€/Jahr", "§ 17 Nr. 4 WoGG", EUR)
pv("Abzug gezahlter Unterhalt höchstens", "p_WG_UhMax", 3000, "€/Jahr", "§ 18 WoGG", EUR)
pv("Mindestbetrag Wohngeld", "p_WG_Min", 10, "€", "§ 21 Nr. 1 WoGG", EUR)
pv("Umgangskind Haushaltsmitglied ab Übernachtungen/Jahr", "p_WG_UmgN", 122, "", "§ 5 Abs. 4 WoGG (mind. ⅓ der Betreuung)")
ph("Kinderzuschlag (§ 6a BKGG)")
pv("Höchstbetrag je Kind (inkl. Sofortzuschlag)", "p_KiZ_Max", 297, "€", "§ 6a Abs. 2 BKGG", EUR)
pv("Mindesteinkommen Paar", "p_KiZ_MinP", 900, "€", "§ 6a Abs. 1 Nr. 2 BKGG", EUR)
pv("Mindesteinkommen alleinerziehend", "p_KiZ_MinAE", 600, "€", "§ 6a Abs. 1 Nr. 2 BKGG", EUR)
pv("Minderungsquote", "p_KiZ_Q", 0.45, "", "§ 6a Abs. 3 und 6 BKGG", PCT)
pv("Erweiterter Zugang: höchstens fehlender Betrag", "p_KiZ_1a", 100, "€", "§ 6a Abs. 1a BKGG", EUR)
ptab("Wohnanteil Eltern – alleinerziehend", "p_KiZAE", [77, 63, 53, 46, 40, 36, 33, 30, 27, 25], "%", "DA-KiZ Stand 20.02.2026, C.3.1.2", None, [f"{i} Kind(er)" for i in range(1, 11)])
ptab("Wohnanteil Eltern – Paar", "p_KiZP", [83, 71, 62, 55, 50, 45, 41, 38, 35, 33], "%", "DA-KiZ Stand 20.02.2026, C.3.1.2", None, [f"{i} Kind(er)" for i in range(1, 11)])
ph("Kranken-/Pflegeversicherung und Rundfunkbeitrag 2026")
pv("Mindestbemessungsgrundlage", "p_SVMind", 1318.33, "€", "§ 240 Abs. 4 SGB V: 3.955 € / 90 × 30 (SVBezGrV 2026)", EUR)
pv("KV ermäßigt (ohne Krankengeld)", "p_KV", 0.14, "", "§ 243 SGB V", PCT)
pv("Zusatzbeitrag (Durchschnitt)", "p_ZB", 0.029, "", "Durchschnittlicher Zusatzbeitrag 2026 (Beitragstabellen der Kassen)", PCT)
pv("Pflegeversicherung", "p_PV", 0.036, "", "§ 55 SGB XI", PCT)
pv("PV-Abschlag je Kind ab 2. Kind", "p_PVAb", 0.0025, "", "§ 55 Abs. 3 SGB XI", '0.00%')
pv("PV-Zuschlag Kinderlose", "p_PVKl", 0.006, "", "§ 55 Abs. 3 SGB XI", PCT)
pv("Rundfunkbeitrag", "p_GEZ", 18.36, "€", "RBStV; Befreiung bei SGB II/XII", EUR)
ph("Vermögensgrenzen")
pv("SGB II je Person bis 29 Jahre", "p_VII1", 5000, "€", "§ 12 Abs. 2 SGB II (übertragbar)", EUR)
pv("SGB II je Person ab 30 Jahre", "p_VII2", 10000, "€", "", EUR)
pv("SGB II je Person ab 40 Jahre", "p_VII3", 12500, "€", "", EUR)
pv("SGB II je Person ab 50 Jahre", "p_VII4", 20000, "€", "", EUR)
pv("SGB XII je Erwachsenem", "p_VXIIAd", 10000, "€", "§ 90 SGB XII i. V. m. § 1 VO", EUR)
pv("SGB XII je unterhaltener Person", "p_VXIIKid", 500, "€", "", EUR)
pv("Wohngeld 1. Person", "p_VWG", 60000, "€", "WoGVwV 21.37 (§ 21 Nr. 3 WoGG)", EUR)
pv("Wohngeld je weitere Person", "p_VWGPlus", 30000, "€", "", EUR)
pv("Kinderzuschlag 1. Person", "p_VKiZ", 40000, "€", "§ 6a Abs. 3 BKGG", EUR)
pv("Kinderzuschlag je weitere Person", "p_VKiZPlus", 15000, "€", "", EUR)

# ---------------------------------------------------------------- Eingabe
E = wb.create_sheet("Eingabe", 0)
E.column_dimensions["A"].width = 3
E.column_dimensions["B"].width = 74
for c in "CDEFG": E.column_dimensions[c].width = 22
E["B1"] = "Vorrangprüfung Wolfsburg – Eingabe"; E["B1"].font = f_h1
E["B2"] = "Nur die gelben Felder ausfüllen (Auswahllisten nutzen). Vorbelegt ist ein erfundenes Beispiel. Das Ergebnis steht im Blatt „Ergebnis“."; E["B2"].font = f_small
dvs = {}
def dv(listtext):
    if listtext not in dvs:
        d = DataValidation(type="list", formula1='"' + listtext + '"', allow_blank=True)
        E.add_data_validation(d); dvs[listtext] = d
    return dvs[listtext]
er = [4]
def eh(title):
    E.cell(er[0], 2, title).font = f_h2; er[0] += 1
def ein(label, nm, val, lst=None, fmt=None, note=None, col=3):
    r = er[0]
    E.cell(r, 2, label).font = f_norm
    c = E.cell(r, col, val); c.font = f_in; c.fill = fill_in; c.border = box
    if fmt: c.number_format = fmt
    if lst: dv(lst).add(c)
    if note: c.comment = Comment(note, "Vorrangprüfung")
    name(nm, absref(E, c.coordinate)); er[0] += 1
JN = "ja,nein"
eh("1 · Haushalt")
ein("Haushaltsform", "e_Typ", "Paar", "Paar,Alleinerziehend,Single")
ein("Verheiratet / eingetragene Lebenspartnerschaft (nur Paar)", "e_Verh", "nein", JN)
ein("Einkommen bleibt voraussichtlich mindestens 3 Monate gleich (§ 12a SGB II)", "e_Stabil", "ja", JN)
ein("Vermögen des Haushalts", "e_Verm", 2000, None, EUR, "Erspartes, Wertpapiere usw. Selbst genutzte angemessene Wohnung und angemessenes Auto zählen nicht.")
ein("Sonderfall: Leistungen nach AsylbLG", "e_Asyl", "nein", JN)
ein("Sonderfall: EU-Bürger nur zur Arbeitsuche / erste 3 Monate", "e_EU", "nein", JN)
ein("Sonderfall: Ausbildung/Studium mit BAföG-/BAB-Anspruch", "e_Azubi", "nein", JN)
ein("Sonderfall: > 6 Monate in stationärer Einrichtung", "e_Stat", "nein", JN)
er[0] += 1
eh("2 · Erwachsene")
r = er[0]
E.cell(r, 2, "Angabe").font = f_bold; E.cell(r, 3, "Person 1").font = f_bold; E.cell(r, 4, "Person 2 (nur Paar)").font = f_bold
for c in (2, 3, 4): E.cell(r, c).fill = fill_head
er[0] += 1
EFL = "erwerbsfähig,dauerhaft voll erwerbsgemindert,vorübergehend voll erwerbsgemindert,vorzeitige Altersrente"
KVL = "automatisch,über Job,familienversichert,über Rente (KVdR),über ALG I/Leistung,freiwillig"
adult_rows = [
    ("Geburtsjahr", "GJ", (1988, 1990), None, '0', None),
    ("Erwerbsfähigkeit", "EF", ("erwerbsfähig", "erwerbsfähig"), EFL, None, "erwerbsfähig = mindestens 3 Stunden täglich arbeitsfähig (§ 8 SGB II)"),
    ("Schwangerschaftswoche (leer = nicht schwanger)", "SSW", (None, None), None, '0', None),
    ("Schwerbehindertenausweis mit Merkzeichen G", "MerkG", ("nein", "nein"), JN, None, None),
    ("GdB 100 oder pflegebedürftig zu Hause", "SB", ("nein", "nein"), JN, None, None),
    ("Krankenversicherung ohne Grundsicherung", "KV", ("automatisch", "automatisch"), KVL, None, "automatisch: Job über Minijob-Grenze = pflichtversichert; Ehepartner = familienversichert; sonst freiwillig"),
    ("Arbeit brutto / Monat", "JB", (1700, 0), None, EUR, None),
    ("Arbeit netto / Monat", "JN", (1330, 0), None, EUR, None),
    ("Kinderzuschlag: Ø brutto letzte 6 Monate (optional)", "AvB", (None, None), None, EUR, "§ 6a Abs. 8 BKGG; leer = aktuelles Einkommen"),
    ("Kinderzuschlag: Ø netto letzte 6 Monate (optional)", "AvN", (None, None), None, EUR, None),
    ("Selbstständigkeit: Gewinn / Monat (Einnahmen − Betriebsausgaben)", "SG", (None, None), None, EUR, "§ 3 Bürgergeld-V"),
    ("Selbstständigkeit: Steuern auf den Gewinn / Monat", "SGSt", (None, None), None, EUR, None),
    ("Rente brutto / Monat", "RB", (None, None), None, EUR, None),
    ("Rente Zahlbetrag / Monat", "RN", (None, None), None, EUR, None),
    ("Mind. 33 Jahre Grundrentenzeiten", "GRZ", ("nein", "nein"), JN, None, None),
    ("Weitere Einnahmen (ALG I, Krankengeld) / Monat", "SO", (None, None), None, EUR, None),
    ("Gezahlter Unterhalt (tituliert) / Monat", "UHP", (None, None), None, EUR, "§ 11b Abs. 1 Nr. 7 SGB II, § 18 WoGG"),
]
for lab, key, vals, lst, fmt, note in adult_rows:
    r = er[0]
    E.cell(r, 2, lab).font = f_norm
    for i, v in enumerate(vals):
        c = E.cell(r, 3 + i, v); c.font = f_in; c.fill = fill_in; c.border = box
        if fmt: c.number_format = fmt
        if lst: dv(lst).add(c)
        if note and i == 0: c.comment = Comment(note, "Vorrangprüfung")
        name(f"e_{key}_{i+1}", absref(E, c.coordinate))
    er[0] += 1
pa_r = er[0]
ein("Abzüge Arbeit beim Wohngeld (§ 16 WoGG: je 10 % für Steuern, KV/PV, RV)", "e_PA", 0.3, "0.3,0.2,0.1,0", PCT)
er[0] += 1
eh("3 · Kinder im Haushalt (unter 25 Jahre; leere Zeile = kein Kind)")
r = er[0]
for c, t in zip(range(2, 8), ("Kind", "Alter", "Unterhalt / UVG / Monat", "Eigenes Einkommen", "brutto / Monat", "netto / Monat")):
    E.cell(r, c, t).font = f_bold; E.cell(r, c).fill = fill_head
er[0] += 1
KET = "keins,Ausbildung/Schule/Freiwilligendienst,Ferienjob (Schüler),sonstige Arbeit"
kid_first = er[0]
kid_ex = [(4, 0, "keins"), (9, 0, "keins")] + [(None, None, "keins")] * 4
for k in range(6):
    r = er[0]
    E.cell(r, 2, f"Kind {k+1}").font = f_norm
    a, u, t = kid_ex[k]
    for col, v, fmt, lst in ((3, a, '0', None), (4, u, EUR, None), (5, t, None, KET), (6, None, EUR, None), (7, None, EUR, None)):
        c = E.cell(r, col, v); c.font = f_in; c.fill = fill_in; c.border = box
        if fmt: c.number_format = fmt
        if lst: dv(lst).add(c)
    er[0] += 1
KR = list(range(kid_first, kid_first + 6))
er[0] += 1
eh("4 · Weitere Kinder und Personen")
ein("Umgangskinder (leben zeitweise hier, Anzahl)", "e_UmgAnz", 0, None, '0')
ein("Alter des Umgangskindes", "e_UmgAlter", 8, None, '0')
ein("Art des Umgangs", "e_UmgArt", "temporär", "temporär,Wechselmodell", None, "Wolfsburg: Wechselmodell = volle Anerkennung; temporär = Mietobergrenze + halbe Differenz zur nächsten Größe")
ein("Übernachtungen hier pro Jahr (je Kind)", "e_UmgNacht", 0, None, '0')
ein("Weitere Personen mit eigenem Leistungsbezug oder Untermieter", "e_Ext", 0, None, '0', "z. B. Kind ab 25 mit eigenem Bürgergeld; Kopfteil (§ 22 SGB II) bzw. Mischhaushalt (§ 11 Abs. 3 WoGG)")
er[0] += 1
eh("5 · Wohnung")
ein("Miete ohne Heizung (Bruttokaltmiete) / Monat", "e_Miete", 780, None, EUR)
ein("Heizkosten / Monat", "e_Heiz", 110, None, EUR)
ein("Grenze angemessene Heizkosten (optional)", "e_HeizG", None, None, EUR, "Laut Heizspiegel bzw. Jobcenter; leer = tatsächliche Heizkosten")
ein("Warmwasser dezentral (Durchlauferhitzer/Boiler)", "e_WW", "nein", JN)
ein("Mietobergrenze manuell (optional, sonst Tabelle)", "e_MOG", None, None, EUR)
ein("Stand der Prüfung der Unterkunftskosten", "e_KdU", "Regelfall", "automatisch (Karenz-Rechner),Regelfall,Karenzzeit,Kostensenkung läuft")
ein("Miete über Mietpreisbremse / qm-Obergrenze (dann keine Karenzzeit)", "e_MPB", "nein", JN, None, "§ 22 Abs. 1 Satz 8 SGB II, § 35 Abs. 1 Satz 9 SGB XII")
er[0] += 1
eh("6 · Karenzzeit-Rechner (für „automatisch“)")
ein("Beginn des aktuellen Leistungsbezugs (1. des Monats)", "e_KZStart", None, None, 'MM.YYYY')
ein("Ende eines früheren Leistungsbezugs (falls vorhanden)", "e_KZPrev", None, None, 'MM.YYYY')
ein("Volle Monate ohne Leistung seit Beginn", "e_KZGap", 0, None, '0')
ein("Schon verbrauchte Karenzmonate aus früherem Bezug", "e_KZUsed", None, None, '0')
E.freeze_panes = "C4"

# ---------------------------------------------------------------- Berechnung
B = wb.create_sheet("Berechnung")
B.column_dimensions["A"].width = 3
B.column_dimensions["B"].width = 62
for c in range(3, 40): B.column_dimensions[L(c)].width = 14
B["B1"] = "Berechnung (nicht ändern – alles Formeln)"; B["B1"].font = f_h1
br = [3]
def bh(title):
    B.cell(br[0], 2, title).font = f_h2; br[0] += 1
def bc(label, nm, formula, fmt=EUR, law=""):
    r = br[0]
    B.cell(r, 2, label).font = f_norm
    c = B.cell(r, 3, formula); c.font = f_norm
    if fmt: c.number_format = fmt
    if law: B.cell(r, 4, law).font = f_small
    if nm: name(nm, absref(B, c.coordinate))
    br[0] += 1
    return c.coordinate
def bp(label, key, tmpl, fmt=EUR, law=""):
    """Zeile je Person: Spalte C = Person 1, D = Person 2; {i} = Person, {j} = andere Person"""
    r = br[0]
    B.cell(r, 2, label).font = f_norm
    for i in (1, 2):
        c = B.cell(r, 2 + i, "=" + tmpl.format(i=i, j=3 - i)); c.font = f_norm
        if fmt: c.number_format = fmt
        name(f"c_{key}_{i}", absref(B, c.coordinate))
    if law: B.cell(r, 5, law).font = f_small
    br[0] += 1

def FB(x, mk):
    return (f"IF({x}<=0,0,MIN({x},p_FB_Grund)+p_FB_Q1*MAX(0,MIN({x}-p_FB_Grund,p_FB_G1-p_FB_Grund))"
            f"+p_FB_Q2*MAX(0,MIN({x}-p_FB_G1,p_FB_G2-p_FB_G1))+p_FB_Q3*MAX(0,MIN({x}-p_FB_G2,IF({mk},p_FB_G3M,p_FB_G3O)-p_FB_G2)))")
def BYN(tab, plus, n):
    return f"IF({n}<=ROWS({tab}),INDEX({tab},MAX(1,{n})),INDEX({tab},ROWS({tab}))+({n}-ROWS({tab}))*{plus})"
def RBK(a):
    return f'IF({a}>=18,IF(c_SYS="XII",p_RBS1,p_RBS3),IF({a}>=14,p_RBS4,IF({a}>=6,p_RBS5,p_RBS6)))'

# --- Kinder-Tabelle zuerst anlegen (Position fix), Formeln später referenzieren
KT0 = 260  # Kopfzeile Kindertabelle
kcols = ["Nr", "aktiv", "Alter", "Regelbedarf", "MB Warmwasser", "Bedarf (RB+KdU+WW)", "Unterhalt/UVG", "Freibetrag Erwerb", "Erwerb bereinigt",
         "Einkommen Kinderwohngeld", "Vermögensfreibetrag", "KiZ-Basis", "KiZ je Kind", "WG: Einkommen/Jahr", "WG: Freibetrag § 17 Nr. 4",
         "KWG Satz 1", "KWG Satz 2", "KWG Satz 3", "KWG Satz 4", "KWG Satz 5", "KWG Satz 6",
         "bleibt 1", "bleibt 2", "bleibt 3", "bleibt 4", "bleibt 5", "bleibt 6", "Kinderwohngeld"]
KCOL = {n: 2 + i for i, n in enumerate(kcols)}
def kc(nm): return L(KCOL[nm])
KR1 = KT0 + 1; KRN = KT0 + 6
def krng(nm): return f"${kc(nm)}${KR1}:${kc(nm)}${KRN}"

bh("A · Personen")
r = br[0]; B.cell(r, 3, "Person 1").font = f_bold; B.cell(r, 4, "Person 2").font = f_bold; br[0] += 1
bp("aktiv (1/0)", "on", 'IF({i}=1,1,IF(e_Typ="Paar",1,0))', '0')
bp("Alter in Monaten (Geburtstag zur Jahresmitte angenommen)", "AM", 'IF(N(e_GJ_{i})>0,(p_Jahr-e_GJ_{i})*12+(p_Monat-6),0)', '0')
bp("Regelaltersgrenze in Monaten", "RAGM", 'IF(N(e_GJ_{i})>0,IF(e_GJ_{i}<=1946,780,IF(e_GJ_{i}<=1958,780+(e_GJ_{i}-1946),IF(e_GJ_{i}<=1963,792+2*(e_GJ_{i}-1958),804))),0)', '0', "§ 7a SGB II, § 235 SGB VI")
bp("Regelaltersgrenze erreicht", "RAG", 'IF(N(e_GJ_{i})>0,IF(c_AM_{i}>=c_RAGM_{i},1,0),0)', '0')
bp("Alter (Jahre)", "Alter", 'IF(N(e_GJ_{i})>0,INT(c_AM_{i}/12),-1)', '0', "-1 = unbekannt")
bp("erwerbsfähig (SGB II)", "EF", 'IF(AND(c_on_{i}=1,c_RAG_{i}=0,e_EF_{i}="erwerbsfähig",OR(N(e_GJ_{i})=0,c_Alter_{i}>=15)),1,0)', '0', "§§ 7, 8 SGB II")
bp("Anspruch SGB XII Kap. 4 (RAG oder dauerhaft EM)", "XIIp", 'IF(AND(c_on_{i}=1,c_EF_{i}=0,OR(c_RAG_{i}=1,e_EF_{i}="dauerhaft voll erwerbsgemindert")),1,0)', '0', "§ 41 SGB XII")
bp("Alter nahe Regelaltersgrenze (genau prüfen)", "Edge", 'IF(N(e_GJ_{i})>0,IF(ABS(c_AM_{i}-c_RAGM_{i})<=6,1,0),0)', '0')

bh("B · Zuständigkeit")
bc("mindestens ein Erwachsener erwerbsfähig", "c_anyEF", "=MAX(c_EF_1,c_EF_2)", '0')
bc("alle Erwachsenen Regelaltersgrenze oder dauerhaft EM", "c_allXII", '=IF(AND(c_on_1=1,c_EF_1=0,OR(c_RAG_1=1,e_EF_1="dauerhaft voll erwerbsgemindert"),OR(c_on_2=0,AND(c_EF_2=0,OR(c_RAG_2=1,e_EF_2="dauerhaft voll erwerbsgemindert")))),1,0)', '0')
bc("Rechtskreis (II / XII4 / XII3 / none / asyl)", "c_Regime", '=IF(e_Asyl="ja","asyl",IF(c_anyEF=1,IF(e_EU="ja","none","II"),IF(c_allXII=1,"XII4","XII3")))', None, "§ 7 SGB II, §§ 19, 41 SGB XII")
bc("System (II / XII)", "c_SYS", '=IF(LEFT(c_Regime,3)="XII","XII","II")', None)
bc("gemischte Bedarfsgemeinschaft", "c_Mixed", '=IF(AND(c_Regime="II",OR(c_XIIp_1=1,c_XIIp_2=1)),1,0)', '0', "§ 5 Abs. 2 SGB II")
bc("Anzahl Erwachsene", "c_nAd", "=c_on_1+c_on_2", '0')
bc("Anzahl Kinder unter 25", "c_NK", f"=SUM(Berechnung!{krng('aktiv')})", '0')
bc("Personen der Bedarfsgemeinschaft", "c_n", "=c_nAd+c_NK", '0')
bc("Kinder 15–24 bei fehlender Erwerbsfähigkeit der Eltern", "c_Kid15", f'=IF(AND(c_anyEF=0,c_Regime<>"asyl",COUNTIFS(Berechnung!{krng("aktiv")},1,Berechnung!{krng("Alter")},">=15")>0),1,0)', '0')

bh("C · Bedarf")
bc("Regelbedarf je Erwachsenem", "c_rbA", '=IF(e_Typ="Paar",p_RBS2,p_RBS1)')
bc("alleinerziehend (Mehrbedarf, Freibetrag)", "c_AE", '=IF(OR(e_Typ="Alleinerziehend",AND(e_Typ="Single",c_NK>0)),1,0)', '0')
bc("minderjährige Kinder", "c_Minors", f'=COUNTIFS(Berechnung!{krng("aktiv")},1,Berechnung!{krng("Alter")},"<18")', '0')
bc("Kinder unter 7", "c_u7", f'=COUNTIFS(Berechnung!{krng("aktiv")},1,Berechnung!{krng("Alter")},"<7")', '0')
bc("Kinder unter 16", "c_u16", f'=COUNTIFS(Berechnung!{krng("aktiv")},1,Berechnung!{krng("Alter")},"<16")', '0')
bc("Mehrbedarf Alleinerziehende in %", "c_mbPct", '=IF(AND(c_AE=1,c_Minors>0),MAX(IF(OR(c_u7>=1,c_u16>=2),36,0),MIN(60,12*c_Minors)),0)', '0', "§ 21 Abs. 3 SGB II")
bc("Mehrbedarf Alleinerziehende", "c_mbAE", "=ROUND(p_RBS1*c_mbPct/100,2)", EUR)
bp("Obergrenze Mehrbedarfe (§ 21 Abs. 8)", "cap0", 'c_rbA-IF({i}=1,c_mbAE,0)')
bp("Mehrbedarf Schwangerschaft", "mbS", 'IF(AND(c_on_{i}=1,N(e_SSW_{i})>=p_SSW_MB),MAX(0,MIN(ROUND(c_rbA*p_MB_Schw,2),c_cap0_{i})),0)', EUR, "§ 21 Abs. 2 SGB II")
bp("Mehrbedarf Merkzeichen G", "mbG", 'IF(AND(c_on_{i}=1,e_MerkG_{i}="ja",c_EF_{i}=0),MAX(0,MIN(ROUND(c_rbA*p_MB_G,2),IF(c_SYS="XII",c_cap0_{i}-c_mbS_{i},c_rbA))),0)', EUR, "§ 23 Nr. 4 SGB II, § 30 SGB XII")
bc("Mehrbedarf Warmwasser Erwachsene", "c_wwAd", '=IF(e_WW="ja",ROUND(c_rbA*p_WW_Erw,2)*c_nAd,0)', EUR, "§ 21 Abs. 7 SGB II")
bc("Mehrbedarfe Erwachsene gesamt", "c_mbAdults", "=c_mbAE+c_mbS_1+c_mbS_2+c_mbG_1+c_mbG_2+c_wwAd")
bc("Regelbedarf Eltern", "c_rbEltern", "=c_rbA*c_nAd")
bc("Umgang: Tage im Monat", "c_umgDays", '=IF(e_UmgAnz>0,MIN(30,IF(N(e_UmgNacht)>0,e_UmgNacht/12,IF(e_UmgArt="Wechselmodell",15,0))),0)', '0.0')
bc("Umgang: Regelbedarf anteilig", "c_umgNeed", "=IF(e_UmgAnz>0,ROUND(e_UmgAnz*" + RBK("N(e_UmgAlter)") + "*c_umgDays/30,2),0)", EUR, "temporäre Bedarfsgemeinschaft")
bc("ungeborene Kinder (ab 12. SSW)", "c_unborn", "=IF(N(e_SSW_1)>=p_SSW_MOG,1,0)+IF(AND(c_on_2=1,N(e_SSW_2)>=p_SSW_MOG),1,0)", '0', "Vorgabe Wolfsburg")
bc("Personen für Mietobergrenze ohne Umgang", "c_nBase", "=c_n+N(e_Ext)+c_unborn", '0')
bc("Personen für Mietobergrenze mit Umgang", "c_nKdU", "=c_nBase+N(e_UmgAnz)", '0')
bc("Mietobergrenze ohne Umgang", "c_mogBase", "=" + BYN("p_MOG", "p_MOG_Plus", "c_nBase"))
bc("Mietobergrenze mit Umgang (voll)", "c_mogFull", "=" + BYN("p_MOG", "p_MOG_Plus", "c_nKdU"))
bc("Mietobergrenze (Tabelle)", "c_grenzeTab", '=IF(N(e_UmgAnz)=0,c_mogBase,IF(e_UmgArt="Wechselmodell",c_mogFull,ROUND(c_mogBase+(c_mogFull-c_mogBase)*p_UmgTemp,2)))', EUR, "Wolfsburg: Wechselmodell voll, temporär halbe Differenz")
bc("Mietobergrenze angewendet", "c_grenze", "=IF(N(e_MOG)>0,e_MOG,c_grenzeTab)")

bh("D · Karenzzeit (§ 22 Abs. 1 Sätze 2–5 SGB II, § 35 Abs. 1 SGB XII)")
bc("Beginn (Monatsindex)", "c_kzStart", '=IF(ISNUMBER(e_KZStart),YEAR(e_KZStart)*12+MONTH(e_KZStart)-1,-1)', '0')
bc("früheres Ende (Monatsindex)", "c_kzPrev", '=IF(ISNUMBER(e_KZPrev),YEAR(e_KZPrev)*12+MONTH(e_KZPrev)-1,-1)', '0')
bc("Monate ohne Leistung dazwischen", "c_kzPause", "=IF(AND(c_kzStart>=0,c_kzPrev>=0,c_kzPrev<c_kzStart),c_kzStart-c_kzPrev-1,-1)", '0')
bc("neue Karenzzeit (Pause ≥ 36 Monate oder kein früherer Bezug)", "c_kzNeu", "=IF(c_kzPause<0,1,IF(c_kzPause>=36,1,0))", '0', "§ 22 Abs. 1 Satz 5 SGB II")
bc("verbrauchte Monate", "c_kzUsed", "=IF(c_kzNeu=1,0,IF(ISNUMBER(e_KZUsed),MIN(12,MAX(0,e_KZUsed)),12))", '0')
bc("restliche Karenzmonate", "c_kzRest", "=12-c_kzUsed", '0')
bc("effektiver Beginn (frühestens 01/2023)", "c_kzEff", "=IF(c_kzStart>=0,MAX(c_kzStart,2023*12),-1)", '0')
bc("Ende (Monatsindex)", "c_kzEnd", "=IF(c_kzEff>=0,c_kzEff+c_kzRest+N(e_KZGap)-1,-1)", '0', "§ 22 Abs. 1 Satz 4 SGB II (Verlängerung)")
bc("heute (Monatsindex)", "c_kzNow", "=p_Jahr*12+p_Monat-1", '0')
bc("Karenzzeit läuft heute", "c_kzActive", "=IF(AND(c_kzEff>=0,c_kzRest>0,c_kzNow>=c_kzEff,c_kzNow<=c_kzEnd),1,0)", '0')
bc("Karenzzeit endet mit Ablauf", "c_kzEndDate", '=IF(AND(c_kzEnd>=0,c_kzRest>0),DATE(INT(c_kzEnd/12),MOD(c_kzEnd,12)+1,1),"")', 'MM.YYYY')
bc("Stand der Prüfung (angewendet)", "c_kdz", '=IF(e_KdU="automatisch (Karenz-Rechner)",IF(c_kzActive=1,"Karenzzeit","Regelfall"),e_KdU)', None)

bh("E · Unterkunft und Heizung")
bc("Karenzzeit wirksam (nicht bei Mietpreisbremse)", "c_kar", '=IF(AND(c_kdz="Karenzzeit",e_MPB<>"ja"),1,0)', '0', "§ 22 Abs. 1 Satz 8 SGB II")
bc("Kostensenkung läuft", "c_senk", '=IF(c_kdz="Kostensenkung läuft",1,0)', '0', "§ 22 Abs. 1 Satz 9 SGB II")
bc("Deckel Unterkunft", "c_mieteCap", "=IF(c_senk=1,1E+9,IF(c_kar=1,c_grenze*p_KarenzF,c_grenze))", EUR, "§ 22 Abs. 1 Satz 6 SGB II, § 35 Abs. 1 Satz 7 SGB XII")
bc("Miete anerkannt", "c_mieteAn", "=MIN(N(e_Miete),c_mieteCap)")
bc("Heizkosten anerkannt", "c_heatAn", "=IF(AND(N(e_HeizG)>0,c_senk=0),MIN(N(e_Heiz),e_HeizG),N(e_Heiz))", EUR, "Heizkosten in der Karenzzeit nicht geschützt")
bc("Kosten Unterkunft und Heizung gesamt", "c_kduTot", "=c_mieteAn+c_heatAn")
bc("Anteil der Bedarfsgemeinschaft (Kopfteil)", "c_shareBG", "=c_n/(c_n+N(e_Ext))", PCT)
bc("KdU der Bedarfsgemeinschaft", "c_kdu", "=c_kduTot*c_shareBG")
bc("KdU je Kopf", "c_kopf", "=c_kdu/c_n")

bh("F · Einkommen Erwachsene (SGB II / SGB XII)")
r = br[0]; B.cell(r, 3, "Person 1").font = f_bold; B.cell(r, 4, "Person 2").font = f_bold; br[0] += 1
bp("Gewinn nach Steuern", "sgN", "MAX(0,N(e_SG_{i})-N(e_SGSt_{i}))", EUR, "§ 3 Bürgergeld-V")
bp("Erwerbseinkommen brutto (Arbeit + Gewinn)", "erwB", "N(e_JB_{i})+N(e_SG_{i})")
bp("Freibetrag SGB II", "fbII", FB("c_erwB_{i}", "c_NK>0"), EUR, "§ 11b Abs. 2, 3 SGB II")
bp("Erwerb bereinigt SGB II", "jobII", "MAX(0,N(e_JN_{i})+c_sgN_{i}-c_fbII_{i})")
bp("Freibetrag SGB XII", "fbXII", "IF(c_erwB_{i}>0,MIN(p_XII_Q*c_erwB_{i},p_RBS1*p_XII_Cap),0)", EUR, "§ 82 Abs. 3 SGB XII")
bp("Erwerb bereinigt SGB XII", "jobXII", "MAX(0,N(e_JN_{i})+c_sgN_{i}-c_fbXII_{i})")
bp("KiZ: brutto (Ø 6 Monate, falls angegeben)", "kB", "IF(N(e_AvB_{i})>0,e_AvB_{i},N(e_JB_{i}))+N(e_SG_{i})", EUR, "§ 6a Abs. 8 BKGG")
bp("KiZ: netto (Ø 6 Monate, falls angegeben)", "kN", "IF(N(e_AvN_{i})>0,e_AvN_{i},N(e_JN_{i}))+c_sgN_{i}")
bp("KiZ: Erwerb bereinigt", "jobKiz", "MAX(0,c_kN_{i}-" + FB("c_kB_{i}", "c_NK>0") + ")")
bp("Grundrentenfreibetrag", "gf", 'IF(AND(e_GRZ_{i}="ja",N(e_RN_{i})>0),MIN(e_RN_{i},p_RBS1*p_GR_Cap,p_GR_Base+p_GR_Q*MAX(0,e_RN_{i}-p_GR_Base)),0)', EUR, "§ 11b Abs. 2a SGB II, § 82a SGB XII")
bp("Rente angerechnet", "rente", "MAX(0,N(e_RN_{i})-c_gf_{i})")
bp("Versicherungspauschale", "pausch", "IF(AND(c_erwB_{i}<=0,OR(N(e_RN_{i})>0,N(e_SO_{i})>0)),p_Pausch,0)", EUR, "§ 6 Bürgergeld-V")
bp("Einkommen bereinigt SGB II", "eII", "c_on_{i}*MAX(0,c_jobII_{i}+c_rente_{i}+N(e_SO_{i})-c_pausch_{i}-N(e_UHP_{i}))", EUR, "inkl. § 11b Abs. 1 Nr. 7")
bp("Einkommen bereinigt SGB XII", "eXII", "c_on_{i}*MAX(0,c_jobXII_{i}+c_rente_{i}+N(e_SO_{i}))")
bp("Person nach SGB XII bereinigen", "xii", 'IF(OR(c_SYS="XII",AND(c_Regime="II",c_XIIp_{i}=1)),1,0)', '0', "§ 5 Abs. 2 SGB II")
bp("Einkommen angerechnet", "e", "IF(c_xii_{i}=1,c_eXII_{i},c_eII_{i})")
bc("Einkommen der Eltern gesamt", "c_elternEink", "=c_e_1+c_e_2")
bc("Erwerbsabsetzbeträge gesamt (für § 6a Abs. 1a)", "c_fbIIsum", "=c_on_1*c_fbII_1+c_on_2*c_fbII_2")

bh("G · Kranken- und Pflegeversicherung ohne Grundsicherung")
r = br[0]; B.cell(r, 3, "Person 1").font = f_bold; B.cell(r, 4, "Person 2").font = f_bold; br[0] += 1
bp("Grundstatus", "kvBase", 'IF(c_on_{i}=0,"-",IF(AND(N(e_SG_{i})>0,N(e_SG_{i})>=N(e_JB_{i})),"",IF(N(e_JB_{i})>p_Minijob,"job",IF(AND(N(e_RB_{i})>0,OR(c_RAG_{i}=1,e_EF_{i}<>"erwerbsfähig")),"rente",IF(N(e_SO_{i})>0,"leist","")))))', None)
bp("automatisch", "kvAuto", 'IF(c_kvBase_{i}="-","-",IF(c_kvBase_{i}<>"",c_kvBase_{i},IF(AND(e_Typ="Paar",e_Verh="ja",c_kvBase_{j}<>"",c_kvBase_{j}<>"-"),"fam","frei")))', None)
bp("Status", "kvSt", 'IF(c_on_{i}=0,"-",IF(e_KV_{i}="über Job","job",IF(e_KV_{i}="familienversichert","fam",IF(e_KV_{i}="über Rente (KVdR)","rente",IF(e_KV_{i}="über ALG I/Leistung","leist",IF(e_KV_{i}="freiwillig","frei",c_kvAuto_{i}))))))', None)
bc("PV-Satz", "c_pv", "=IF(c_NK=0,p_PV+p_PVKl,p_PV-IF(c_NK>=2,p_PVAb*(MIN(c_NK,5)-1),0))", '0.00%', "§ 55 SGB XI")
bc("Beitragssatz gesamt", "c_kvRate", "=p_KV+p_ZB+c_pv", '0.00%')
bp("Bemessungsgrundlage", "kvBas", "MAX(p_SVMind,N(e_JB_{i})+N(e_RB_{i})+N(e_SO_{i})+N(e_SG_{i}))", EUR, "§ 240 Abs. 4 SGB V")
bp("Beitrag freiwillig", "kvB", 'IF(c_kvSt_{i}="frei",ROUND(c_kvBas_{i}*c_kvRate,2),0)')
bc("KV/PV-Beiträge ohne Grundsicherung", "c_KV", "=c_kvB_1+c_kvB_2")

bh("H · Vermögen")
bp("Freibetrag SGB II nach Alter", "fbVA", 'IF(c_on_{i}=0,0,IF(c_Alter_{i}<0,p_VII2,IF(c_Alter_{i}>=50,p_VII4,IF(c_Alter_{i}>=40,p_VII3,IF(c_Alter_{i}>=30,p_VII2,p_VII1)))))', EUR, "§ 12 Abs. 2 SGB II")
bc("Vermögensgrenze Grundsicherung", "c_vSGB", f'=IF(c_SYS="XII",p_VXIIAd*c_nAd+p_VXIIKid*c_NK,c_fbVA_1+c_fbVA_2+SUM(Berechnung!{krng("Vermögensfreibetrag")}))', EUR, "§ 12 SGB II / § 90 SGB XII")
bc("Vermögensgrenze Wohngeld", "c_vWG", "=p_VWG+p_VWGPlus*(c_n-1)")
bc("Vermögensgrenze Kinderzuschlag", "c_vKiZ", "=p_VKiZ+p_VKiZPlus*(c_n-1)", EUR, "§ 6a Abs. 3 BKGG")
bc("Grundsicherung möglich (Rechtskreis und Vermögen)", "c_sgbAvail", '=IF(AND(OR(c_Regime="II",c_Regime="XII3",c_Regime="XII4"),N(e_Verm)<=c_vSGB),1,0)', '0')

bh("I · Gesamtbedarf")
bc("Bedarf gesamt", "c_need", f"=c_rbEltern+c_mbAdults+c_umgNeed+c_kdu+SUM(Berechnung!{krng('Regelbedarf')})+SUM(Berechnung!{krng('MB Warmwasser')})")

bh("J · Wohngeld für den Haushalt (WoGG)")
bc("Umgangskinder als Haushaltsmitglied", "c_umgWg", '=IF(N(e_UmgAnz)>0,IF(OR(e_UmgArt="Wechselmodell",N(e_UmgNacht)>=p_WG_UmgN),e_UmgAnz,IF(AND(e_UmgAnz>=2,N(e_UmgNacht)>0),1,0)),0)', '0', "§ 5 Abs. 4 WoGG")
bc("zu berücksichtigende Haushaltsmitglieder", "c_nW", "=c_n+c_umgWg", '0')
bc("Haushaltsmitglieder gesamt (Mischhaushalt)", "c_nT", "=c_nW+N(e_Ext)", '0', "§ 11 Abs. 3 WoGG")
bc("Höchstbetrag", "c_hb", "=" + BYN("p_HB", "p_HB_Plus", "c_nT"), EUR, "Anlage 1 WoGG")
bc("Klimakomponente", "c_kl", "=" + BYN("p_KL", "p_KL_Plus", "c_nT"), EUR, "§ 12 Abs. 7")
bc("Heizkostenentlastung", "c_hke", "=" + BYN("p_HKE", "p_HKE_Plus", "c_nT"), EUR, "§ 12 Abs. 6")
bc("Heizkostenkomponente", "c_hkk", "=" + BYN("p_HKK", "p_HKK_Plus", "c_nT"), EUR, "§ 12 Abs. 6")
bc("Miete bis Höchstbetrag + Klima", "c_mRent", "=MIN(N(e_Miete),c_hb+c_kl)", EUR, "§ 11 Abs. 1 WoGG")
bc("M (anteilig)", "c_M", "=(c_mRent+c_hke+c_hkk)*c_nW/c_nT")
r = br[0]; B.cell(r, 3, "Person 1").font = f_bold; B.cell(r, 4, "Person 2").font = f_bold; br[0] += 1
bp("Arbeit nach Werbungskosten und Abzug (Jahr)", "wJob", "c_on_{i}*IF(N(e_JB_{i})>0,(e_JB_{i}*12-MIN(e_JB_{i}*12,p_WG_WK))*(1-e_PA),0)", EUR, "§§ 14, 16 WoGG")
bp("Selbstständigkeit (Jahr)", "wSG", "c_on_{i}*IF(N(e_SG_{i})>0,e_SG_{i}*12*(1-(IF(N(e_SGSt_{i})>0,0.1,0)+0.1)),0)")
bp("Rente (Jahr)", "wRente", "c_on_{i}*IF(N(e_RB_{i})>0,(e_RB_{i}*12-MIN(e_RB_{i}*12,p_WG_RWK))*(1-p_WG_RPa),0)")
bp("weitere Einnahmen (Jahr)", "wSO", "c_on_{i}*N(e_SO_{i})*12")
bp("Freibetrag Grundrente (Jahr)", "wGrz", 'c_on_{i}*IF(AND(e_GRZ_{i}="ja",N(e_RB_{i})>0),12*MIN(e_RB_{i},p_RBS1*p_GR_Cap,p_GR_Base+p_GR_Q*MAX(0,e_RB_{i}-p_GR_Base)),0)', EUR, "§ 17a WoGG")
bp("Freibetrag GdB 100 / Pflege", "wSB", 'c_on_{i}*IF(e_SB_{i}="ja",p_WG_SB,0)', EUR, "§ 17 Nr. 1")
bp("Abzug Unterhaltszahlungen", "wUH", "c_on_{i}*MIN(N(e_UHP_{i})*12,p_WG_UhMax)", EUR, "§ 18 WoGG")
bc("Jahreseinkommen", "c_wJahr", f"=c_wJob_1+c_wJob_2+c_wSG_1+c_wSG_2+c_wRente_1+c_wRente_2+c_wSO_1+c_wSO_2+SUM(Berechnung!{krng('WG: Einkommen/Jahr')})")
bc("Freibeträge und Abzüge", "c_wFrei", f"=c_wGrz_1+c_wGrz_2+c_wSB_1+c_wSB_2+c_wUH_1+c_wUH_2+SUM(Berechnung!{krng('WG: Freibetrag § 17 Nr. 4')})+IF(AND(c_AE=1,c_Minors>0),p_WG_AEFrei,0)", EUR, "§ 17 Nr. 3 einmal je Haushalt")
bc("Y vor Mindestwert", "c_Yroh", "=MAX(0,c_wJahr-c_wFrei)/12")
bc("Tabellenzeile", "c_wIdx", "=MIN(MAX(c_nW,1),12)", '0')
bc("Y (mindestens Anlage 3)", "c_Y", "=MAX(c_Yroh,INDEX(p_Ymin,c_wIdx))", EUR, "Anlage 3 WoGG")
bc("M (mindestens Anlage 3)", "c_Mx", "=MAX(c_M,INDEX(p_Mmin,c_wIdx))")
bc("ungerundetes Wohngeld", "c_wRaw", "=1.15*(c_Mx-(INDEX(p_a,c_wIdx)+INDEX(p_b,c_wIdx)*c_Mx+INDEX(p_c,c_wIdx)*c_Y)*c_Y)", EUR, "§ 19 Abs. 1 WoGG")
bc("gerundet", "c_wg0", "=ROUND(MAX(0,MIN(c_wRaw,c_Mx)),0)")
bc("ab 13 Mitgliedern + 65 €", "c_wg1", "=IF(c_nW>12,MIN(c_wg0+65*(c_nW-12),c_Mx),c_wg0)", EUR, "§ 19 Abs. 3 WoGG")
bc("Wohngeld (Haushalt)", "c_WG", '=IF(OR(c_wg1<p_WG_Min,N(e_Verm)>c_vWG,c_Regime="asyl"),0,c_wg1)', EUR, "§ 21 WoGG")

bh("K · Kinderzuschlag (§ 6a BKGG)")
bc("Bruttoeinkommen der Eltern", "c_kizBrutto", "=c_on_1*(c_kB_1+N(e_RB_1)+N(e_SO_1))+c_on_2*(c_kB_2+N(e_RB_2)+N(e_SO_2))", EUR, "§ 6a Abs. 1 Nr. 2")
bc("Mindesteinkommen", "c_kizMinE", "=IF(c_AE=1,p_KiZ_MinAE,p_KiZ_MinP)")
bc("Voraussetzungen erfüllt", "c_kizOK", '=IF(AND(c_NK>0,c_Regime<>"asyl",N(e_Verm)<=c_vKiZ,c_kizBrutto>=c_kizMinE),1,0)', '0')
bc("Wohnanteil der Eltern", "c_anteil", "=IF(c_NK=0,0,IF(c_AE=1,INDEX(p_KiZAE,MIN(c_NK,10)),INDEX(p_KiZP,MIN(c_NK,10)))/100)", PCT, "§ 6a Abs. 5, DA-KiZ C.3.1.2")
bc("Gesamtbedarf der Eltern", "c_kizBed", "=c_rbEltern+c_mbAdults+c_anteil*c_kdu")
bc("Erwerbseinkommen bereinigt", "c_kErw", "=c_on_1*c_jobKiz_1+c_on_2*c_jobKiz_2")
bc("anderes Einkommen", "c_kOth", "=MAX(0,c_on_1*(c_rente_1-c_pausch_1+N(e_SO_1))+c_on_2*(c_rente_2-c_pausch_2+N(e_SO_2)))")
bc("Abzug KV/PV und gezahlter Unterhalt", "c_kDed", "=c_KV+c_on_1*N(e_UHP_1)+c_on_2*N(e_UHP_2)")
bc("anderes Einkommen nach Abzug", "c_kOth2", "=c_kOth-MIN(c_kOth,c_kDed)")
bc("Erwerbseinkommen nach Abzug", "c_kErw2", "=MAX(0,c_kErw-(c_kDed-MIN(c_kOth,c_kDed)))")
bc("anderes Einkommen über Bedarf (mindert 100 %)", "c_exOth", "=MAX(0,c_kOth2-c_kizBed)", EUR, "§ 6a Abs. 6 Satz 4")
bc("Erwerbseinkommen über Bedarf (mindert 45 %)", "c_exErw", "=MAX(0,c_kErw2-MAX(0,c_kizBed-c_kOth2))", EUR, "§ 6a Abs. 6 Sätze 2–3")
bc("Summe Höchstbeträge nach Kindeseinkommen", "c_baseSum", f"=SUM(Berechnung!{krng('KiZ-Basis')})", EUR, "§ 6a Abs. 3")
bc("Minderung", "c_minder", "=p_KiZ_Q*c_exErw+c_exOth")
bc("Kinderzuschlag gesamt", "c_KiZ", "=IF(c_kizOK=1,MAX(0,ROUNDDOWN(c_baseSum-c_minder,0)),0)")

bh("L · Kinderwohngeld (Kinder scheiden mit eigenem Einkommen aus der BG aus)")
bc("Prüfung möglich", "c_kwOk", '=IF(AND(c_Regime<>"asyl",c_Regime<>"none",N(e_Verm)<=c_vWG),1,0)', '0')
bc("Haushaltsmitglieder gesamt", "c_nTK", "=c_n+N(e_Ext)", '0')
bc("Miete + Heizkostenbeträge (vor Anteil)", "c_mAllK", "=MIN(N(e_Miete)," + BYN("p_HB", "p_HB_Plus", "c_nTK") + "+" + BYN("p_KL", "p_KL_Plus", "c_nTK") + ")+" + BYN("p_HKE", "p_HKE_Plus", "c_nTK") + "+" + BYN("p_HKK", "p_HKK_Plus", "c_nTK"))
r = br[0]
for j, t in enumerate(("Durchlauf", "Kinder", "M", "Y", "Wohngeld", "je Kind", "stabil")):
    B.cell(r, 2 + j, t).font = f_bold
br[0] += 1
kw_first = br[0]
for pnum in range(1, 7):
    rr = br[0]
    S = f"Berechnung!${kc('KWG Satz '+str(pnum))}${KR1}:${kc('KWG Satz '+str(pnum))}${KRN}"
    K = f"Berechnung!${kc('bleibt '+str(pnum))}${KR1}:${kc('bleibt '+str(pnum))}${KRN}"
    B.cell(rr, 2, pnum)
    B.cell(rr, 3, f"=SUM({S})")
    B.cell(rr, 4, f"=IF(C{rr}>0,MAX(c_mAllK*C{rr}/c_nTK,INDEX(p_Mmin,MIN(C{rr},12))),0)").number_format = EUR
    B.cell(rr, 5, f"=IF(C{rr}>0,MAX(SUMPRODUCT({S},Berechnung!{krng('Einkommen Kinderwohngeld')}),INDEX(p_Ymin,MIN(C{rr},12))),0)").number_format = EUR
    B.cell(rr, 6, f"=IF(C{rr}>0,IF(ROUND(MAX(0,MIN(1.15*(D{rr}-(INDEX(p_a,MIN(C{rr},12))+INDEX(p_b,MIN(C{rr},12))*D{rr}+INDEX(p_c,MIN(C{rr},12))*E{rr})*E{rr}),D{rr})),0)<p_WG_Min,0,ROUND(MAX(0,MIN(1.15*(D{rr}-(INDEX(p_a,MIN(C{rr},12))+INDEX(p_b,MIN(C{rr},12))*D{rr}+INDEX(p_c,MIN(C{rr},12))*E{rr})*E{rr}),D{rr})),0)),0)").number_format = EUR
    B.cell(rr, 7, f"=IF(C{rr}>0,F{rr}/C{rr},0)").number_format = EUR
    B.cell(rr, 8, f"=IF(AND(C{rr}>0,SUM({K})=C{rr}),1,0)")
    br[0] += 1
kw_last = br[0] - 1
name("c_kwPerRange", f"'Berechnung'!$G${kw_first}:$G${kw_last}")
bc("stabiler Durchlauf", "c_kwPass", f"=IFERROR(MATCH(1,Berechnung!$H${kw_first}:$H${kw_last},0),0)", '0')
bc("Kinderwohngeld gesamt", "c_KW", f"=IF(c_kwPass>0,INDEX(Berechnung!$F${kw_first}:$F${kw_last},c_kwPass),0)")

# --- Kindertabelle schreiben
B.cell(KT0 - 1, 2, "M · Kinder (je Zeile ein Kind)").font = f_h2
for nmc, col in KCOL.items():
    c = B.cell(KT0, col, nmc); c.font = f_bold; c.fill = fill_head; c.alignment = Alignment(wrap_text=True)
B.row_dimensions[KT0].height = 42
for k in range(6):
    rr = KT0 + 1 + k; er_ = KR[k]
    A = f"Eingabe!$C${er_}"; U = f"Eingabe!$D${er_}"; T = f"Eingabe!$E${er_}"; EB = f"N(Eingabe!$F${er_})"; EN = f"N(Eingabe!$G${er_})"
    on = f"{kc('aktiv')}{rr}"; age = f"{kc('Alter')}{rr}"
    def put(col, formula, fmt=EUR):
        c = B.cell(rr, KCOL[col], formula); c.font = f_norm
        if fmt: c.number_format = fmt
    put("Nr", k + 1, '0')
    put("aktiv", f"=IF(AND(ISNUMBER({A}),{A}>=0,{A}<25),1,0)", '0')
    put("Alter", f"=IF({on}=1,{A},99)", '0')
    put("Regelbedarf", f"=IF({on}=1," + RBK(age) + ",0)")
    put("MB Warmwasser", f'=IF(AND({on}=1,e_WW="ja"),ROUND({kc("Regelbedarf")}{rr}*IF({age}>=18,p_WW_Erw,IF({age}>=14,p_WW_14,IF({age}>=6,p_WW_6,p_WW_0))),2),0)')
    put("Bedarf (RB+KdU+WW)", f"=IF({on}=1,{kc('Regelbedarf')}{rr}+c_kopf+{kc('MB Warmwasser')}{rr},0)")
    put("Unterhalt/UVG", f"=IF({on}=1,N({U}),0)")
    noinc = f'OR({on}=0,{T}="keins",{T}="Ferienjob (Schüler)",{EN}<=0)'
    put("Freibetrag Erwerb", f'=IF({noinc},0,IF(AND({T}="Ausbildung/Schule/Freiwilligendienst",{age}<25),MIN({EB},p_Minijob)+p_FB_Q2*MAX(0,MIN({EB}-p_FB_G1,p_FB_G2-p_FB_G1))+p_FB_Q3*MAX(0,MIN({EB}-p_FB_G2,p_FB_G3O-p_FB_G2)),' + FB(EB, "FALSE") + "))")
    put("Erwerb bereinigt", f"=IF({noinc},0,MAX(0,{EN}-{kc('Freibetrag Erwerb')}{rr}))")
    hasE = f'AND({T}<>"keins",{EB}>0)'
    put("Einkommen Kinderwohngeld", f'=IF({on}=0,0,{kc("Unterhalt/UVG")}{rr}+IF({hasE},MAX(0,(({EB}*12-MIN({EB}*12,p_WG_WK))*IF({T}="Ferienjob (Schüler)",1,0.8)-MIN({EB}*12,p_WG_KindFrei))/12),0))')
    put("Vermögensfreibetrag", f"=IF({on}=1,IF({age}>=50,p_VII4,IF({age}>=40,p_VII3,IF({age}>=30,p_VII2,p_VII1))),0)")
    put("KiZ-Basis", f"=IF({on}=1,MAX(0,p_KiZ_Max-p_KiZ_Q*({kc('Unterhalt/UVG')}{rr}+{kc('Erwerb bereinigt')}{rr})),0)")
    put("KiZ je Kind", f"=IF(c_baseSum>0,c_KiZ*{kc('KiZ-Basis')}{rr}/c_baseSum,0)")
    put("WG: Einkommen/Jahr", f'=IF({on}=1,{kc("Unterhalt/UVG")}{rr}*12+IF({hasE},({EB}*12-MIN({EB}*12,p_WG_WK))*(1-IF({T}="Ferienjob (Schüler)",0,0.2)),0),0)')
    put("WG: Freibetrag § 17 Nr. 4", f"=IF(AND({on}=1,{hasE},{age}<25),MIN({EB}*12,p_WG_KindFrei),0)")
    for pnum in range(1, 7):
        S = f"{kc('KWG Satz '+str(pnum))}{rr}"
        if pnum == 1:
            put("KWG Satz 1", f"=IF(AND({on}=1,{kc('Einkommen Kinderwohngeld')}{rr}>0,c_kwOk=1),1,0)", '0')
        else:
            put(f"KWG Satz {pnum}", f"={kc('bleibt '+str(pnum-1))}{rr}", '0')
        per = f"Berechnung!$G${kw_first + pnum - 1}"
        put(f"bleibt {pnum}", f"=IF({S}=1,IF({kc('Unterhalt/UVG')}{rr}+{kc('Erwerb bereinigt')}{rr}+p_KG+{per}>={kc('Bedarf (RB+KdU+WW)')}{rr},1,0),0)", '0')
    sets = f"{kc('KWG Satz 1')}{rr}:{kc('KWG Satz 6')}{rr}"
    put("Kinderwohngeld", f"=IF(c_kwPass=0,0,IF(INDEX({sets},c_kwPass)=1,INDEX(c_kwPerRange,c_kwPass),0))")

# ---------------------------------------------------------------- Szenarien (§ 9 SGB II: Hilfebedürftigkeit der BG)
Z = wb.create_sheet("Szenarien")
Z.column_dimensions["A"].width = 3; Z.column_dimensions["B"].width = 34
Z["B1"] = "Szenarien: Lücke der Bedarfsgemeinschaft mit vorrangigen Leistungen (nicht ändern)"; Z["B1"].font = f_h1
Z["B2"] = "Kindergeld deckt zuerst den Bedarf des Kindes, der Rest zählt bei den Eltern (§ 11 Abs. 1 SGB II); Einkommen der Eltern über ihrem Bedarf deckt die Kinder (§ 9 Abs. 2 SGB II)."; Z["B2"].font = f_small
SC = [("Grundsicherung (inkl. Kinderwohngeld)", 0, 0, 1, 0), ("nur KV/PV-Kosten", 0, 0, 0, 1), ("Wohngeld", 1, 0, 0, 0), ("Wohngeld + KV/PV", 1, 0, 0, 1),
      ("Kinderzuschlag", 0, 1, 0, 0), ("Kinderzuschlag + KV/PV", 0, 1, 0, 1), ("Wohngeld + Kinderzuschlag", 1, 1, 0, 0), ("Wohngeld + Kinderzuschlag + KV/PV", 1, 1, 0, 1)]
hdr = ["Szenario", "Wohngeld", "Kinderzuschlag (1/0)", "Kinderwohngeld (1/0)", "KV/PV-Kosten", "Wohngeld je Kopf"]
for i, h in enumerate(hdr): Z.cell(4 + i, 2, h).font = f_bold
KZ0 = 12
Z.cell(KZ0 - 1, 2, "je Kind: eigenes Einkommen / Kindergeld bei Eltern / ungedeckt").font = f_bold
for k in range(6): Z.cell(KZ0 + k, 2, f"Kind {k+1}")
SUMR = KZ0 + 7
for i, t in enumerate(("Bedarf Eltern", "Einkommen Eltern", "Lücke der Bedarfsgemeinschaft")): Z.cell(SUMR + i, 2, t).font = f_bold
for s, (title, w, kz, kwg, kv) in enumerate(SC):
    c0 = 3 + s * 3
    for j in range(3): Z.column_dimensions[L(c0 + j)].width = 13
    Z.cell(3, c0, f"S{s+1}").font = f_bold
    Z.cell(4, c0, title).font = f_bold; Z.cell(4, c0).alignment = Alignment(wrap_text=True)
    Z.cell(5, c0, "=c_WG" if w else 0).number_format = EUR
    Z.cell(6, c0, kz); Z.cell(7, c0, kwg)
    Z.cell(8, c0, "=c_KV" if kv else 0).number_format = EUR
    Z.cell(9, c0, f"={L(c0)}5/c_n").number_format = EUR
    Z.cell(KZ0 - 1, c0, "eigen"); Z.cell(KZ0 - 1, c0 + 1, "KG Eltern"); Z.cell(KZ0 - 1, c0 + 2, "ungedeckt")
    for k in range(6):
        rr = KZ0 + k; br_ = KT0 + 1 + k
        on = f"Berechnung!${kc('aktiv')}${br_}"; age = f"Berechnung!${kc('Alter')}${br_}"; need = f"Berechnung!${kc('Bedarf (RB+KdU+WW)')}${br_}"
        own = f"{L(c0)}{rr}"
        Z.cell(rr, c0, f"=IF({on}=1,Berechnung!${kc('Unterhalt/UVG')}${br_}+Berechnung!${kc('Erwerb bereinigt')}${br_}+{L(c0)}$6*Berechnung!${kc('KiZ je Kind')}${br_}+{L(c0)}$7*Berechnung!${kc('Kinderwohngeld')}${br_}+{L(c0)}$9,0)").number_format = EUR
        x18 = f'AND(c_SYS="XII",{age}>=18)'
        Z.cell(rr, c0 + 1, f"=IF({on}=0,0,IF(OR({own}>={need},{x18}),p_KG,p_KG-MIN(p_KG,{need}-{own})))").number_format = EUR
        Z.cell(rr, c0 + 2, f"=IF({on}=0,0,IF({own}>={need},0,IF({x18},{need}-{own},{need}-{own}-MIN(p_KG,{need}-{own}))))").number_format = EUR
    Z.cell(SUMR, c0, f"=c_rbEltern+c_mbAdults+c_umgNeed+c_kopf*c_nAd+{L(c0)}8").number_format = EUR
    Z.cell(SUMR + 1, c0, f"=c_elternEink+SUM({L(c0+1)}{KZ0}:{L(c0+1)}{KZ0+5})+{L(c0)}9*c_nAd").number_format = EUR
    g = Z.cell(SUMR + 2, c0, f"=MAX(0,ROUND({L(c0)}{SUMR}-{L(c0)}{SUMR+1}+SUM({L(c0+2)}{KZ0}:{L(c0+2)}{KZ0+5}),2))"); g.number_format = EUR; g.font = f_bold
    name(f"z_gap{s+1}", absref(Z, g.coordinate))

# ---------------------------------------------------------------- Varianten + Ergebnis-Logik (Berechnung, Abschnitt N)
br[0] = KT0 + 9
bh("N · Varianten und Ergebnis")
bc("Grundsicherungs-Lücke (mit Kinderwohngeld)", "c_s0", "=z_gap1")
bc("Lücke nur mit KV/PV-Kosten", "c_s0kv", "=z_gap2")
bc("Familie (Kinder vorhanden)", "c_fam", "=IF(c_NK>0,1,0)", '0')
for v, (gkv, gn, has) in {1: ("z_gap4", "z_gap3", "c_WG>0"), 2: ("z_gap6", "z_gap5", "AND(c_fam=1,c_KiZ>0)"), 3: ("z_gap8", "z_gap7", "AND(c_fam=1,OR(c_WG>0,c_KiZ>0))")}.items():
    bc(f"Variante {v}: Lücke mit KV/PV", f"c_g{v}", f"={gkv}")
    bc(f"Variante {v}: Lücke ohne KV/PV", f"c_gn{v}", f"={gn}")
    wahl = f'IF(AND({v}>=2,c_KiZ>0,c_g{v}<=p_KiZ_1a,c_fbIIsum>=100),"Wahlrecht","reicht nicht")' if v >= 2 else '"reicht nicht"'
    bc(f"Variante {v}: Status", f"c_st{v}", f'=IF(NOT({has}),"entfällt",IF(c_g{v}=0,"reicht",IF(c_gn{v}=0,"reicht mit KV/PV-Zuschuss",{wahl})))', None, "§ 12a SGB II, § 26 SGB II, § 6a Abs. 1a BKGG")
    bc(f"Variante {v}: Zuschuss KV/PV", f"c_zus{v}", f'=IF(c_st{v}="reicht mit KV/PV-Zuschuss",c_g{v},0)')
bc("beste Variante mit KV/PV-Zuschuss", "c_zBest", '=IF(OR(c_zus1>0,c_zus2>0,c_zus3>0),IF(AND(c_zus1>0,c_zus1=MIN(IF(c_zus1>0,c_zus1,1E9),IF(c_zus2>0,c_zus2,1E9),IF(c_zus3>0,c_zus3,1E9))),1,IF(AND(c_zus2>0,c_zus2=MIN(IF(c_zus2>0,c_zus2,1E9),IF(c_zus3>0,c_zus3,1E9))),2,3)),0)', '0')
bc("beste Variante mit Wahlrecht", "c_wBest", '=IF(AND(c_st2="Wahlrecht",OR(c_st3<>"Wahlrecht",c_g2<=c_g3)),2,IF(c_st3="Wahlrecht",3,0))', '0')
VN = '{"Wohngeld","Kinderzuschlag","Wohngeld + Kinderzuschlag"}'
def vname(x): return f'IF({x}=1,"Wohngeld",IF({x}=2,"Kinderzuschlag","Wohngeld + Kinderzuschlag"))'
bc("Ergebnis-Code", "c_code", '=IF(c_Regime="asyl","asyl",IF(c_sgbAvail=0,IF(c_Regime="none","eu","verm"),IF(c_s0=0,"none",IF(AND(c_st1="reicht",c_st2="reicht"),"each",IF(c_st1="reicht","wg",IF(c_st2="reicht","kiz",IF(c_st3="reicht","both",IF(c_zBest>0,"zus",IF(c_wBest>0,"wahl","sgb")))))))))', None)
bc("beste Variante (Nummer)", "c_best", '=IF(c_code="each",3,IF(c_code="wg",1,IF(c_code="kiz",2,IF(c_code="both",3,IF(c_code="zus",c_zBest,IF(c_code="wahl",c_wBest,0))))))', '0')
bc("Verweis wegen fehlender 3-Monats-Prognose ausgeschlossen", "c_unstab", '=IF(AND(c_SYS="II",e_Stabil="nein",OR(c_code="each",c_code="wg",c_code="kiz",c_code="both",c_code="zus")),1,0)', '0')
bc("Leistung beste/oberste Variante (für Budget)", "c_top", "=IF(c_fam=1,3,1)", '0')
bc("Zuschuss KV/PV in oberster Variante", "c_zusTop", "=IF(c_top=3,c_zus3,c_zus1)")
bc("verfügbares Einkommen (netto, Kindergeld, Unterhalt)", "c_basis", "=c_on_1*(N(e_JN_1)+c_sgN_1+N(e_RN_1)+N(e_SO_1))+c_on_2*(N(e_JN_2)+c_sgN_2+N(e_RN_2)+N(e_SO_2))+SUM(Berechnung!" + krng('Unterhalt/UVG') + ")+c_NK*p_KG+SUMPRODUCT(Berechnung!" + krng('aktiv') + ",--(Eingabe!$E$" + str(KR[0]) + ":$E$" + str(KR[-1]) + '<>"keins"),Eingabe!$G$' + str(KR[0]) + ":$G$" + str(KR[-1]) + ")")
bc("Budget mit Grundsicherung", "c_bSGB", "=c_basis+c_s0+c_KW")
bc("Budget mit vorrangigen Leistungen", "c_bVor", "=c_basis+c_WG+IF(c_fam=1,c_KiZ,0)-c_KV-p_GEZ+c_zusTop", EUR, "inkl. Rundfunkbeitrag (keine Befreiung)")

# ---------------------------------------------------------------- Ergebnis
R = wb.create_sheet("Ergebnis", 1)
R.column_dimensions["A"].width = 3; R.column_dimensions["B"].width = 58
for c, w in zip("CDEF", (20, 20, 30, 30)): R.column_dimensions[c].width = w
R["B1"] = "Vorrangprüfung Wolfsburg – Ergebnis"; R["B1"].font = f_h1
R["B2"] = "Stand (heute):"; R["B2"].font = f_small
R["C2"] = "=TODAY()"; R["C2"].number_format = "DD.MM.YYYY"; R["C2"].font = f_small
R["D2"] = "Rechtsstand 07.11.2026 · Prototyp, kein Bescheid"; R["D2"].font = f_small
SYSN = 'IF(c_SYS="XII","SGB XII","SGB II")'
head = ('=IF(c_unstab=1,"Kein Verweis: Einkommen nicht für 3 Monate gesichert",'
        'IF(c_code="asyl","Leistungen nach dem AsylbLG",IF(c_code="eu","Kein Anspruch auf SGB II (§ 7 Abs. 1 Satz 2 SGB II)",IF(c_code="verm","Kein Anspruch auf Grundsicherung wegen Vermögen",'
        'IF(c_code="none","Kein Anspruch auf Grundsicherung",IF(c_code="each","Wohngeld oder Kinderzuschlag reicht schon allein",IF(c_code="wg","Wohngeld reicht",IF(c_code="kiz","Kinderzuschlag reicht",'
        'IF(c_code="both","Nur zusammen: Wohngeld und Kinderzuschlag beantragen",IF(c_code="zus",' + vname("c_zBest") + '&" und Zuschuss zur KV/PV beantragen",'
        'IF(c_code="wahl","Wahlrecht: "&' + vname("c_wBest") + '&" statt "&' + SYSN + '&" möglich",' + SYSN + '&" bleibt")))))))))))')
law = 'IF(c_SYS="XII","§ 2 SGB XII","§ 12a SGB II")'
law = 'IF(c_SYS="XII","§ 2 SGB XII","§ 12a SGB II")'
TX = [
 ("unstab", '"Rechnerisch reicht "&' + vname("c_best") + '&". § 12a SGB II verlangt aber eine Überwindung der Hilfebedürftigkeit für mindestens 3 Monate am Stück."'),
 ("asyl", '"Kein Anspruch auf SGB II/XII und kein Wohngeld (§ 7 Abs. 1 WoGG). Einzelfall prüfen."'),
 ("eu", '"Wohngeld ("&FIXED(c_WG,2)&" €) und Kinderzuschlag ("&FIXED(c_KiZ,2)&" €) direkt prüfen; ggf. Überbrückungsleistungen nach § 23 SGB XII."'),
 ("verm", '"Vermögen "&FIXED(N(e_Verm),2)&" € über dem Freibetrag von "&FIXED(c_vSGB,2)&" €. Wohngeld ist bis "&FIXED(c_vWG,2)&" € Vermögen möglich: "&FIXED(c_WG,2)&" €."'),
 ("none", '"Das Einkommen deckt den Bedarf. Wohngeld ("&FIXED(c_WG,2)&" €)"&IF(c_fam=1," und Kinderzuschlag ("&FIXED(c_KiZ,2)&" €)","")&" direkt beantragen."'),
 ("each", '"Jede Leistung beendet für sich die Hilfebedürftigkeit; zusammen ergibt sich das meiste Geld. Verweis nach "&' + law + '&" zulässig."'),
 ("wg", '"Wohngeld beendet die Hilfebedürftigkeit. Verweis nach "&' + law + '&" zulässig."&IF(c_KiZ>0," Zusätzlich Kinderzuschlag beantragen.","")'),
 ("kiz", '"Kinderzuschlag beendet die Hilfebedürftigkeit. Verweis nach "&' + law + '&" zulässig."&IF(c_WG>0," Zusätzlich Wohngeld beantragen.","")'),
 ("both", '"Keine Leistung reicht allein, zusammen wird die Hilfebedürftigkeit überwunden. Verweis nach "&' + law + '&" zulässig."'),
 ("zus", '"Ohne Grundsicherung wäre der Haushalt nur wegen der KV/PV-Beiträge ("&FIXED(c_KV,2)&" €) hilfebedürftig. Zuschuss "&FIXED(CHOOSE(MAX(1,c_zBest),c_zus1,c_zus2,c_zus3),2)&" € nach "&IF(c_SYS="XII","§ 32 SGB XII","§ 26 SGB II")&"."'),
 ("wahl", '"Es fehlen höchstens 100 €. Nach § 6a Abs. 1a BKGG besteht trotzdem Anspruch auf Kinderzuschlag, wenn keine Grundsicherung beantragt wird. Kein Verweis – die Familie entscheidet."'),
 ("sgb", '"Auch mit vorrangigen Leistungen bleibt eine Lücke von "&FIXED(IF(c_fam=1,c_g3,c_g1),2)&" €. Kein Verweis nach "&' + law + '&"."'),
]
bh("O · Ergebnistexte")
for key, f in TX:
    bc("Text " + key, "t_" + key, "=" + f, None)
text = '=IF(c_unstab=1,t_unstab,IF(c_code="asyl",t_asyl,IF(c_code="eu",t_eu,IF(c_code="verm",t_verm,IF(c_code="none",t_none,IF(c_code="each",t_each,IF(c_code="wg",t_wg,IF(c_code="kiz",t_kiz,IF(c_code="both",t_both,IF(c_code="zus",t_zus,IF(c_code="wahl",t_wahl,t_sgb)))))))))))'
R["B4"] = head; R["B4"].font = Font(name=F, size=14, bold=True, color="1F8A4C"); R.merge_cells("B4:F4")
R["B5"] = text; R["B5"].font = f_norm; R["B5"].alignment = Alignment(wrap_text=True, vertical="top"); R.merge_cells("B5:F5"); R.row_dimensions[5].height = 48
R["B6"] = '="Zuständig: "&IF(c_Regime="II","SGB II (Bürgergeld / Grundsicherungsgeld)",IF(c_Regime="XII4","SGB XII – Grundsicherung im Alter und bei Erwerbsminderung",IF(c_Regime="XII3","SGB XII – Hilfe zum Lebensunterhalt",IF(c_Regime="asyl","Asylbewerberleistungsgesetz","kein Anspruch auf SGB II"))))'
R["B6"].font = f_bold
for c in ("B4", "B5", "B6"): R[c].fill = fill_res
R["B8"] = "Kennzahlen"; R["B8"].font = f_h2
kp = [("Grundsicherungs-Lücke", "=c_s0"), ("KV/PV-Kosten ohne Grundsicherung", "=c_KV"), ("Wohngeld", "=c_WG"), ("Kinderzuschlag", "=c_KiZ"),
      ("Kinderwohngeld (im Grundsicherungsbezug)", "=c_KW"), ("Gesamtbedarf", "=c_need"), ("Mietobergrenze angewendet", "=c_grenze")]
for i, (t, f) in enumerate(kp):
    R.cell(9 + i, 2, t).font = f_norm
    c = R.cell(9 + i, 3, f); c.number_format = EUR; c.font = f_link
R["B17"] = "Varianten"; R["B17"].font = f_h2
for j, t in enumerate(("Variante", "Leistung", "Lücke", "Status", "Zuschuss KV/PV")):
    c = R.cell(18, 2 + j, t); c.font = f_bold; c.fill = fill_head
rows = [("Nur Grundsicherung", "=c_KW", "=c_s0", '=IF(c_s0>0,"hilfebedürftig","nicht hilfebedürftig")', 0),
        ("Wohngeld allein", "=c_WG", "=c_g1", "=c_st1", "=c_zus1"),
        ("Kinderzuschlag allein", "=IF(c_fam=1,c_KiZ,0)", "=IF(c_fam=1,c_g2,0)", '=IF(c_fam=1,c_st2,"nur mit Kindern")', "=c_zus2"),
        ("Wohngeld + Kinderzuschlag", "=IF(c_fam=1,c_WG+c_KiZ,0)", "=IF(c_fam=1,c_g3,0)", '=IF(c_fam=1,c_st3,"nur mit Kindern")', "=c_zus3")]
for i, rw in enumerate(rows):
    for j, v in enumerate(rw):
        c = R.cell(19 + i, 2 + j, v); c.font = f_norm; c.border = box
        if j in (1, 2, 4): c.number_format = EUR
R["B24"] = "Was bleibt im Monat?"; R["B24"].font = f_h2
for i, (t, f) in enumerate((("Mit Grundsicherung", "=c_bSGB"), ("Mit Wohngeld/Kinderzuschlag (nach KV/PV und Rundfunkbeitrag)", "=c_bVor"), ("Unterschied", "=c_bVor-c_bSGB"))):
    R.cell(25 + i, 2, t).font = f_norm; c = R.cell(25 + i, 3, f); c.number_format = EUR; c.font = f_bold if i == 2 else f_link
R["B29"] = "Hinweise"; R["B29"].font = f_h2
hints = [
    '=IF(c_Mixed=1,"Gemischte Bedarfsgemeinschaft: Eine Person hat vorrangig Anspruch nach SGB XII, 4. Kapitel (§ 5 Abs. 2 SGB II); ihr Einkommen wird nach SGB XII bereinigt.","")',
    '=IF(c_Kid15=1,"Kein Erwachsener ist erwerbsfähig, aber ein Kind ist 15 oder älter – möglicherweise besteht eine SGB-II-Bedarfsgemeinschaft. Manuell prüfen.","")',
    '=IF(OR(c_Edge_1=1,AND(c_on_2=1,c_Edge_2=1)),"Alter liegt nahe der Regelaltersgrenze – mit genauem Geburtsdatum prüfen.","")',
    '=IF(e_Azubi="ja","Auszubildende/Studierende mit Förderanspruch: § 7 Abs. 5 SGB II, § 22 SGB XII, § 20 WoGG – manuell prüfen.","")',
    '=IF(e_Stat="ja","Stationäre Unterbringung über 6 Monate: kein SGB II (§ 7 Abs. 4 SGB II) – manuell prüfen.","")',
    '=IF(N(e_Verm)>c_vWG,"Wohngeld ausgeschlossen: Vermögen über "&FIXED(c_vWG,2)&" € (§ 21 Nr. 3 WoGG).","")',
    '=IF(AND(e_MPB="ja",c_kdz="Karenzzeit"),"Keine Karenzzeit: Miete über Mietpreisbremse bzw. qm-Obergrenze (§ 22 Abs. 1 Satz 8 SGB II).","")',
    '=IF(c_KW>0,"Kinderwohngeld: Mindestens ein Kind scheidet mit eigenem Einkommen und Kinderwohngeld aus der Bedarfsgemeinschaft aus – vorrangig zu beantragen (§ 12a SGB II).","")',
    '=IF(N(e_UmgAnz)>0,"Umgang: Mietobergrenze "&FIXED(c_grenzeTab,2)&" € ("&IF(e_UmgArt="Wechselmodell","volle Anerkennung","halbe Differenz")&"), Regelbedarf anteilig für "&FIXED(c_umgDays,0)&" Tage im Monat.","")',
    '=IF(c_unborn>0,"Schwangerschaft ab der 12. Woche: Das ungeborene Kind zählt bei der Mietobergrenze mit.","")',
    '=IF(c_fam=1,"Bildung und Teilhabe beeinflusst die Vorrangprüfung nicht (§ 6a Abs. 1 Nr. 3 BKGG) und wird mit Wohngeld/Kinderzuschlag ebenfalls gewährt (§ 6b BKGG).","")',
    '=IF(c_KV>0,"Ohne Grundsicherung fallen KV/PV-Beiträge an; Rundfunkbeitrag "&FIXED(p_GEZ,2)&" € (Befreiung nur bei SGB II/XII, Härtefall § 4 Abs. 6 RBStV).","Rundfunkbeitrag "&FIXED(p_GEZ,2)&" € ohne Grundsicherung (Härtefall § 4 Abs. 6 RBStV möglich).")',
    '=IF(c_kzEff>=0,"Karenzzeit: "&IF(c_kzNeu=1,"neue Karenzzeit","keine neue Karenzzeit (weniger als 36 Monate Pause)")&IF(c_kzRest>0,", läuft bis "&IF(MONTH(c_kzEndDate)<10,"0","")&MONTH(c_kzEndDate)&"."&YEAR(c_kzEndDate)&IF(c_kzActive=1," (heute aktiv)"," (heute nicht aktiv)"),", verbraucht")&". Neubeginn erst nach 3 Jahren ohne Leistungen (§ 22 Abs. 1 Satz 5 SGB II).","")',
]
# Hinweise im Blatt Berechnung sammeln und ohne Lücken anzeigen
bh("P · Hinweise (Rohliste)")
h0 = br[0]; hN = h0 + len(hints) - 1
for i, h in enumerate(hints):
    rr = h0 + i
    B.cell(rr, 2, f"Hinweis {i+1}").font = f_norm
    B.cell(rr, 3, h).font = f_norm
    B.cell(rr, 4, (f'=IF(C{rr}<>"",COUNTIF($D${h0}:D{rr-1},">0")+1,0)') if i else (f'=IF(C{rr}<>"",1,0)'))
br[0] = hN + 1
for i in range(len(hints)):
    c = R.cell(30 + i, 2, f'=IFERROR("• "&INDEX(Berechnung!$C${h0}:$C${hN},MATCH({i+1},Berechnung!$D${h0}:$D${hN},0)),"")')
    c.font = f_norm; c.alignment = Alignment(wrap_text=True, vertical="top"); R.merge_cells(start_row=30 + i, start_column=2, end_row=30 + i, end_column=6)
R.freeze_panes = "A4"

# ---------------------------------------------------------------- Anleitung
A = wb.create_sheet("Anleitung", 0)
A.column_dimensions["A"].width = 3; A.column_dimensions["B"].width = 110
lines = [
    ("Vorrangprüfung Wolfsburg (Excel-Fassung)", f_h1),
    ("Prototyp für einen Verbesserungsvorschlag – kein Bescheid. Rechtsstand 07.11.2026.", f_small),
    ("", f_norm),
    ("So geht's", f_h2),
    ("1. Blatt „Eingabe“: nur die gelben Felder ausfüllen. Bei den meisten Feldern gibt es eine Auswahlliste.", f_norm),
    ("2. Blatt „Ergebnis“: Ergebnis mit Paragraf, Kennzahlen, alle Varianten, Budgetvergleich und Hinweise.", f_norm),
    ("3. Blatt „Berechnung“: kompletter Rechenweg mit Paragrafen (nur Formeln, nicht ändern).", f_norm),
    ("4. Blatt „Parameter“: alle Rechtswerte mit Quelle. Bei Gesetzesänderungen nur hier anpassen.", f_norm),
    ("", f_norm),
    ("Was geprüft wird", f_h2),
    ("• Zuständigkeit (SGB II, SGB XII Kap. 3/4, AsylbLG) nach Erwerbsfähigkeit und Regelaltersgrenze", f_norm),
    ("• Grundsicherungsbedarf mit Mehrbedarfen, Kosten der Unterkunft (Mietobergrenzen Wolfsburg, Karenzzeit mit 150-%-Deckel, Umgang, Schwangerschaft)", f_norm),
    ("• Wohngeld nach § 19 WoGG (Mietenstufe IV) mit allen Freibeträgen, Mindestwerten und Mischhaushalt", f_norm),
    ("• Kinderzuschlag nach § 6a BKGG einschließlich erweitertem Zugang (Abs. 1a) und Kinderwohngeld", f_norm),
    ("• Kranken-/Pflegeversicherung ohne Grundsicherung und Zuschuss nach § 26 SGB II / § 32 SGB XII, Rundfunkbeitrag, Vermögensgrenzen", f_norm),
    ("• Selbstständigkeit, Rente mit Grundrente, gezahlter Unterhalt, Erwerbseinkommen von Kindern (Ausbildung, Ferienjob)", f_norm),
    ("", f_norm),
    ("Farben", f_h2),
    ("Gelb hinterlegt, blaue Schrift = Eingabe · Blaue Schrift im Blatt Parameter = Rechtswert/Annahme · Schwarz = Formel · Grün = Verweis auf ein anderes Blatt", f_norm),
    ("", f_norm),
    ("Bewusst nicht berechnet", f_h2),
    ("Bildung und Teilhabe (ohne Einfluss auf die Prüfung, § 6a Abs. 1 Nr. 3 BKGG), Reformen 2027 (noch nicht verkündet). Annahmen sind im Blatt Parameter gekennzeichnet.", f_norm),
]
for i, (t, f) in enumerate(lines, 1):
    c = A.cell(i, 2, t); c.font = f; c.alignment = Alignment(wrap_text=True)

for ws in wb.worksheets:
    for row in ws.iter_rows():
        for c in row:
            if c.font is None or c.font.name != F:
                c.font = Font(name=F, size=c.font.size if c.font else 10, bold=c.font.bold if c.font else False, color=c.font.color if c.font else None)
for ws in wb.worksheets:
    ws.page_setup.orientation = "landscape"; ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
wb.active = 2
wb.save(OUT)
print("gespeichert", OUT, "Kinder-Eingabezeilen", KR, "Kindertabelle ab", KT0)
