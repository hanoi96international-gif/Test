from bounty_radar.__main__ import parse_amount, report, score


def _item(**kw):
    item = {"html_url": "https://github.com/a/b/issues/1", "title": "Fix crash",
            "repository_url": "https://api.github.com/repos/a/b", "labels": [],
            "body": "", "comments": 0, "assignee": None, "updated_at": "2026-10-10T00:00:00Z",
            "created_at": "2026-10-01T00:00:00Z"}
    item.update(kw)
    return item


def test_betraege_erkennen():
    assert parse_amount("## 💎 $1,500 bounty") == 1500
    assert parse_amount("Reward: $2k for this") == 2000
    assert parse_amount("Bounty 300 USD") == 300
    assert parse_amount("Issue 1234 without money") == 0


def test_konkurrenz_senkt_score():
    frei = score(_item(labels=[{"name": "$500"}]))
    voll = score(_item(labels=[{"name": "$500"}], comments=9))
    vergeben = score(_item(labels=[{"name": "$500"}], assignee={"login": "x"}))
    assert frei["amount"] == 500 and frei["repo"] == "a/b"
    assert frei["score"] > voll["score"] > 0
    assert vergeben["taken"] and vergeben["score"] < frei["score"]


def test_bericht():
    text = report([score(_item(title="Fix | crash", body="$200"))], 50, ["python"])
    assert "**200 $**" in text and "Fix / crash" in text
    assert "Diesmal nichts" in report([], 50, [])


def test_koeder_repos_werden_gefiltert():
    from bounty_radar.__main__ import trustworthy
    alt = "2020-01-01T00:00:00Z"
    gut = {"stargazers_count": 500, "created_at": alt}
    assert trustworthy({"amount": 300}, gut)
    assert not trustworthy({"amount": 9000}, gut)  # Fantasiebetrag bei kleinem Projekt
    assert trustworthy({"amount": 9000}, {"stargazers_count": 20000, "created_at": alt})
    assert not trustworthy({"amount": 300}, {"stargazers_count": 3, "created_at": alt})
    assert not trustworthy({"amount": 300}, {"stargazers_count": 500, "created_at": "2026-10-01T00:00:00Z"})
    assert not trustworthy({"amount": 300}, {**gut, "fork": True})
    assert not trustworthy({"amount": 300}, {})


def test_algora_betrag_aus_bot_kommentar(monkeypatch):
    import bounty_radar.__main__ as radar
    monkeypatch.setattr(radar, "_get", lambda url, token: [
        {"user": {"login": "someone"}, "body": "I'd do it for $9999"},
        {"user": {"login": "algora-pbc[bot]"}, "body": "## 💎 $250 bounty • Acme"},
    ])
    assert radar.algora_amount(score(_item()), "") == 250


def test_details(monkeypatch):
    import bounty_radar.__main__ as radar
    def fake_get(url, token):
        if "search/issues" in url:
            return {"items": [{"html_url": "https://github.com/a/b/pull/7"}]}
        return [{"user": {"login": "x"}, "created_at": "2999-01-01T00:00:00Z", "body": "/attempt #1"},
                {"user": {"login": "y"}, "created_at": "2000-01-01T00:00:00Z", "body": "/attempt #1"}]
    monkeypatch.setattr(radar, "_get", fake_get)
    d = radar.details(score(_item()), {"pushed_at": "2026-10-01T00:00:00Z", "language": "Go"}, "")
    assert d["recent_attempts"] == 1
    assert d["open_prs_mentioning_issue"] == ["https://github.com/a/b/pull/7"]
    assert d["repo_language"] == "Go" and len(d["last_comments"]) == 2


def test_frische_bounties_zuerst():
    import datetime as dt
    heute = dt.date.today().isoformat() + "T00:00:00Z"
    frisch = score(_item(labels=[{"name": "$300"}], created_at=heute))
    alt = score(_item(labels=[{"name": "$300"}], created_at="2020-01-01T00:00:00Z"))
    assert frisch["age_days"] == 0 and frisch["score"] == 4 * alt["score"]
