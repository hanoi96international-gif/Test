import json, sys, subprocess, os
from openpyxl import load_workbook
TPL, CASES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
RECALC = "/root/.claude/skills/synced/43b4e7d8-f401-4f8a-a16e-8afe4b3f8008_83be4826-e6d1-4dd5-86cc-cf61d8264c29/xlsx/scripts/recalc.py"
EF = {"ja":"erwerbsfähig","dau":"dauerhaft voll erwerbsgemindert","zeit":"vorübergehend voll erwerbsgemindert","ar":"vorzeitige Altersrente"}
KV = {"auto":"automatisch","job":"über Job","fam":"familienversichert","rente":"über Rente (KVdR)","leist":"über ALG I/Leistung","frei":"freiwillig"}
ET = {"none":"keins","azubi":"Ausbildung/Schule/Freiwilligendienst","ferien":"Ferienjob (Schüler)","job":"sonstige Arbeit"}
TYP = {"paar":"Paar","ae":"Alleinerziehend","solo":"Single"}
KDZ = {"normal":"Regelfall","karenz":"Karenzzeit","senk":"Kostensenkung läuft"}
JN = lambda b: "ja" if b else "nein"
def cell(wb, n):
    sh, ref = list(wb.defined_names[n].destinations)[0]; return wb[sh][ref.replace("$","")]
res = []
for c in json.load(open(CASES)):
    S = c["S"]; wb = load_workbook(TPL)
    def setv(n, v): cell(wb, n).value = v
    setv("e_Typ", TYP[S["typ"]]); setv("e_Verh", JN(S.get("verh"))); setv("e_Stabil", "ja"); setv("e_Verm", S.get("verm", 0))
    for k in ("Asyl","EU","Azubi","Stat"): setv("e_"+k, "nein")
    for i in (1, 2):
        a = (S.get("ad") or [{}, {}])[i-1] or {}
        setv(f"e_GJ_{i}", a.get("gj") or None); setv(f"e_EF_{i}", EF[a.get("ef","ja")]); setv(f"e_SSW_{i}", a.get("ssw") or None)
        setv(f"e_MerkG_{i}", JN(a.get("merkG"))); setv(f"e_SB_{i}", JN(a.get("sb"))); setv(f"e_KV_{i}", KV[a.get("kv","auto")]); setv(f"e_GRZ_{i}", JN(a.get("grz")))
        for k, n in (("jb","JB"),("jn","JN"),("avB","AvB"),("avN","AvN"),("sg","SG"),("sgSt","SGSt"),("rb","RB"),("rn","RN"),("so","SO"),("uhP","UHP")):
            setv(f"e_{n}_{i}", a.get(k) or None)
    setv("e_PA", float(S.get("pa", 0.3)))
    setv("e_Stabil", "ja")
    ws = wb["Eingabe"]
    for k in range(6):
        r = 37 + k; kd = (S.get("kids") or [])
        if k < len(kd):
            x = kd[k]; ws.cell(r,3).value = x["age"]; ws.cell(r,4).value = x.get("uh",0); ws.cell(r,5).value = ET[x.get("et","none")]; ws.cell(r,6).value = x.get("eb") or None; ws.cell(r,7).value = x.get("en") or None
        else:
            for col in (3,4,6,7): ws.cell(r,col).value = None
            ws.cell(r,5).value = "keins"
    setv("e_UmgAnz", S.get("umgCnt",0)); setv("e_UmgAlter", S.get("umgAge",8)); setv("e_UmgArt", "Wechselmodell" if S.get("umgArt")=="wechsel" else "temporär"); setv("e_UmgNacht", S.get("umgNights",0)); setv("e_Ext", S.get("ext25",0))
    setv("e_Miete", S.get("mi",0)); setv("e_Heiz", S.get("hz",0)); setv("e_HeizG", S.get("hzG")); setv("e_WW", JN(S.get("ww"))); setv("e_MOG", S.get("mog"))
    setv("e_KdU", KDZ[S.get("kdz","normal")]); setv("e_MPB", JN(S.get("mpb")))
    fn = f"xl_case.xlsx"; wb.save(fn)
    out = json.loads(subprocess.run(["python3", RECALC, fn, "90"], capture_output=True, text=True).stdout)
    wv = load_workbook(fn, data_only=True)
    g = lambda n: cell(wv, n).value
    st = [g("c_st1")] + ([g("c_st2"), g("c_st3")] if g("c_fam") == 1 else [])
    res.append({"id": c["id"], "errors": out.get("total_errors"), "head": wv["Ergebnis"]["B4"].value, "s0": g("c_s0"), "kv": g("c_KV"), "wg": g("c_WG"), "kiz": g("c_KiZ") if g("c_fam")==1 else 0, "kw": g("c_KW"), "st": st, "bud": [g("c_bSGB"), g("c_bVor")]})
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
print("Excel fertig", len(res))
