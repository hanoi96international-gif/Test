"""Bounty-Radar: findet bezahlte Programmieraufgaben (Bounties) auf GitHub und bewertet sie.

Aufruf:  python -m bounty_radar [--sprachen python,javascript] [--min-betrag 50] [--ausgabe BOUNTIES.md]
Ohne Token: 10 Suchanfragen/Minute. Mit GITHUB_TOKEN (in Actions automatisch) deutlich mehr.
"""

import argparse
import datetime as dt
import json
import os
import re
import time
import urllib.parse
import urllib.request

API = "https://api.github.com"

# Verschiedene Plattformen markieren Bounties unterschiedlich (Algora, IssueHunt, Opire, eigene Labels)
QUERIES = [
    'label:"💎 Bounty" state:open is:issue',
    'label:bounty state:open is:issue',
    'label:"Bounty" state:open is:issue',
    'label:"💰 Rewarded" state:open is:issue',
]

AMOUNT_RE = re.compile(r"(?:\$|USD\s?|US\$)\s?(\d{1,3}(?:[,.]\d{3})+|\d+)(?:\s?[kK]\b)?|(\d{1,3}(?:[,.]\d{3})+|\d+)\s?(?:\$|USD)")


def parse_amount(text: str) -> int:
    """Größter Dollarbetrag im Text, z. B. '$1,500' -> 1500, '$2k' -> 2000."""
    best = 0
    for m in AMOUNT_RE.finditer(text or ""):
        raw = m.group(1) or m.group(2)
        value = int(re.sub(r"[,.]", "", raw))
        if m.group(0).rstrip().lower().endswith("k"):
            value *= 1000
        if value < 100_000:  # größere Zahlen sind fast immer IDs o. Ä., keine Beträge
            best = max(best, value)
    return best


def _get(url, token):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "bounty-radar"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def search(token, days, pages=2):
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    seen = {}
    for q in QUERIES:
        for page in range(1, pages + 1):
            params = urllib.parse.urlencode({"q": f"{q} updated:>={since}", "sort": "updated",
                                             "order": "desc", "per_page": 50, "page": page})
            try:
                data = _get(f"{API}/search/issues?{params}", token)
            except Exception as exc:  # Rate-Limit oder Netzwerk: mit dem Rest weitermachen
                print(f"Warnung: Suche '{q}' Seite {page} fehlgeschlagen: {exc}")
                break
            for item in data.get("items", []):
                seen.setdefault(item["html_url"], item)
            if len(data.get("items", [])) < 50:
                break
            time.sleep(2 if token else 7)
    return list(seen.values())


def score(item):
    """Betrag geteilt durch Konkurrenz. Hohe Werte zuerst bearbeiten."""
    labels = " ".join(label["name"] for label in item.get("labels", []))
    amount = parse_amount(f"{item['title']} {labels} {item.get('body') or ''}")
    taken = bool(item.get("assignee"))
    competition = 1 + item.get("comments", 0) + (5 if taken else 0)
    repo = item["repository_url"].split("/repos/")[1]
    return {
        "url": item["html_url"], "title": item["title"].strip(), "repo": repo,
        "amount": amount, "comments": item.get("comments", 0), "taken": taken,
        "updated": item["updated_at"][:10], "labels": labels,
        "score": round(amount / competition, 1),
    }


def algora_amount(entry, token):
    """Algora schreibt den Betrag nicht ins Issue, sondern in einen Bot-Kommentar."""
    api_url = entry["url"].replace("https://github.com/", f"{API}/repos/") + "/comments?per_page=30"
    try:
        comments = _get(api_url, token)
    except Exception:
        return 0
    return max((parse_amount(c.get("body", "")) for c in comments
                if "algora" in c.get("user", {}).get("login", "").lower()), default=0)


def repo_info(repo, token, cache):
    if repo not in cache:
        try:
            cache[repo] = _get(f"{API}/repos/{repo}", token)
        except Exception:
            cache[repo] = {}
    return cache[repo]


def trustworthy(entry, info, min_stars=100, min_age_days=180):
    """Filtert Köder-Bounties: neue, unbekannte Repos mit absurd hohen Beträgen zahlen praktisch nie."""
    if not info or info.get("fork") or info.get("archived"):
        return False
    created = dt.date.fromisoformat(info.get("created_at", "2100-01-01")[:10])
    if (dt.date.today() - created).days < min_age_days:
        return False
    stars = info.get("stargazers_count", 0)
    if stars < min_stars:
        return False
    # Fünfstellige Prämien gibt es nur bei großen, etablierten Projekten
    return entry["amount"] <= 3000 or stars >= 2000


def report(entries, min_amount, languages):
    today = dt.date.today().isoformat()
    lines = [
        f"# 🎯 Bounty-Radar ({today})",
        "",
        f"Bezahlte, offene Programmieraufgaben ab {min_amount} $"
        + (f" in {', '.join(languages)}" if languages else "") + ", sortiert nach *Betrag ÷ Konkurrenz*.",
        "Nur etablierte Projekte (≥ 100 Sterne, ≥ 6 Monate alt); Köder-Repos mit Fantasiebeträgen sind ausgefiltert.",
        "",
        "| # | Betrag | Konkurrenz | Aufgabe | Projekt | ⭐ |",
        "|---|---:|---|---|---|---:|",
    ]
    for i, e in enumerate(entries, 1):
        comp = "🔴 vergeben?" if e["taken"] else ("🟢 frei" if e["comments"] <= 3 else f"🟡 {e['comments']} Kommentare")
        title = e["title"].replace("|", "/")[:80]
        lines.append(f"| {i} | **{e['amount']} $** | {comp} | [{title}]({e['url']}) | `{e['repo']}` | {e.get('stars', '')} |")
    if not entries:
        lines.append("| – | – | – | Diesmal nichts Passendes gefunden. | – | – |")
    lines += [
        "",
        "## So holst du dir eine Bounty",
        "1. Issue komplett lesen: Bedingungen, Plattform (Algora/IssueHunt/Opire) und ob schon jemand dran ist.",
        "   Warnsignale: Betrag nur im Titel, keine Bezahlplattform, viele fast gleiche Issues, Forderung nach Wallet-Daten.",
        "2. Bei Algora im Issue `/attempt #<nummer>` kommentieren, damit andere sehen, dass du arbeitest.",
        "3. Projekt forken, Fix bauen (gern zusammen mit Claude Code), Tests laufen lassen.",
        "4. Pull Request mit `/claim #<nummer>` in der Beschreibung öffnen. Nach dem Merge wird ausgezahlt.",
    ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Findet bezahlte GitHub-Issues (Bounties).")
    ap.add_argument("--sprachen", default=os.environ.get("BOUNTY_SPRACHEN", ""),
                    help="Kommagetrennt, z. B. python,typescript (leer = alle)")
    ap.add_argument("--min-betrag", type=int, default=int(os.environ.get("BOUNTY_MIN_BETRAG", "50")))
    ap.add_argument("--tage", type=int, default=14, help="Nur Issues, die in den letzten N Tagen aktiv waren")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--ausgabe", default="BOUNTIES.md")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    languages = {s.strip().lower() for s in args.sprachen.split(",") if s.strip()}
    entries = [score(i) for i in search(token, args.tage)]
    for e in [e for e in entries if e["amount"] == 0 and "bounty" in e["labels"].lower()][:80]:
        e["amount"] = algora_amount(e, token)
        e["score"] = round(e["amount"] / (1 + e["comments"] + (5 if e["taken"] else 0)), 1)
    entries = [e for e in entries if e["amount"] >= args.min_betrag]
    entries.sort(key=lambda e: e["score"], reverse=True)
    cache, chosen, per_repo = {}, [], {}
    for e in entries:
        if len(chosen) == args.top:
            break
        if per_repo.get(e["repo"], 0) >= 3:  # ein Projekt soll die Liste nicht fluten
            continue
        info = repo_info(e["repo"], token, cache)
        if not trustworthy(e, info):
            continue
        if languages and (info.get("language") or "").lower() not in languages:
            continue
        e["stars"] = info.get("stargazers_count", 0)
        per_repo[e["repo"]] = per_repo.get(e["repo"], 0) + 1
        chosen.append(e)

    with open(args.ausgabe, "w", encoding="utf-8") as fh:
        fh.write(report(chosen, args.min_betrag, sorted(languages)))
    print(f"{len(chosen)} Bounties -> {args.ausgabe}")


if __name__ == "__main__":
    main()
