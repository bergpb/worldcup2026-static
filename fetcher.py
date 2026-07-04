#!/usr/bin/env python3
"""
WC 2026 data fetcher — sources from ESPN public API (no auth required).
Writes data.json and scorers.json to /data/ every 60s.

Output schema matches football-data.org so the frontend needs no changes.
"""

import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from collections import defaultdict

ESPN     = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
SCORES_URL = f"{ESPN}/scoreboard?dates=20260611-20260719&limit=120"
SUMMARY_URL = f"{ESPN}/summary?event="
DATA_OUT        = "/data/data.json"
SCORERS_OUT     = "/data/scorers.json"
DETAILS_OUT     = "/data/match-details.json"
WINNERS_OUT     = "/data/group-winners.json"
INTERVAL        = 30

# ESPN shortDisplayName → our display name (mirrors JS API_NAME_MAP)
_DISPLAY_MAP = {
    'Korea Republic': 'South Korea', 'United States': 'USA',
    'Bosnia-H.': 'Bosnia', 'Bosnia-Herzegovina': 'Bosnia',
    'Bosnia & Herz.': 'Bosnia', 'Bosnia-Herz': 'Bosnia',
    'Curaçao': 'Curacao', 'Turkey': 'Turkiye', 'Türkiye': 'Turkiye',
    'Cape Verde Islands': 'Cape Verde',
}

def _display(name):
    return _DISPLAY_MAP.get(name, name)

# ESPN status → period (extra time / penalty / None)
PERIOD_MAP = {
    "STATUS_EXTRA_TIME":             "EXTRA_TIME",
    "STATUS_EXTRA_TIME_SECOND_HALF": "EXTRA_TIME",
    "STATUS_EXTRA_TIME_HALF_TIME":   "EXTRA_TIME",
    "STATUS_OVERTIME":               "EXTRA_TIME",
    "STATUS_PENALTY":                "PENALTY",
}

# ESPN status → score.duration (football-data.org schema)
DURATION_MAP = {
    "STATUS_EXTRA_TIME":             "EXTRA_TIME",
    "STATUS_EXTRA_TIME_SECOND_HALF": "EXTRA_TIME",
    "STATUS_EXTRA_TIME_HALF_TIME":   "EXTRA_TIME",
    "STATUS_OVERTIME":               "EXTRA_TIME",
    "STATUS_FINAL_AET":              "EXTRA_TIME",
    "STATUS_PENALTY":                "PENALTY_SHOOTOUT",
    "STATUS_FINAL_PEN":              "PENALTY_SHOOTOUT",
}

# ESPN status → football-data.org status
STATUS_MAP = {
    "STATUS_SCHEDULED":              "TIMED",
    "STATUS_IN":                     "IN_PLAY",
    "STATUS_IN_PROGRESS":            "IN_PLAY",
    "STATUS_FIRST_HALF":             "IN_PLAY",
    "STATUS_SECOND_HALF":            "IN_PLAY",
    "STATUS_HALFTIME":               "PAUSED",
    "STATUS_EXTRA_TIME":             "IN_PLAY",
    "STATUS_EXTRA_TIME_SECOND_HALF": "IN_PLAY",
    "STATUS_EXTRA_TIME_HALF_TIME":   "PAUSED",
    "STATUS_OVERTIME":               "IN_PLAY",
    "STATUS_PENALTY":                "IN_PLAY",
    "STATUS_FULL_TIME":              "FINISHED",
    "STATUS_FINAL":                  "FINISHED",
    "STATUS_FINAL_AET":              "FINISHED",
    "STATUS_FINAL_PEN":              "FINISHED",
    "STATUS_ABANDONED":              "FINISHED",
    "STATUS_CANCELED":               "TIMED",
    "STATUS_POSTPONED":              "TIMED",
}

# Cache for FINISHED matches: event_id → (ht_home, ht_away, key_events[])
_cache = {}

# Live state guard: event_id → {status, h_score, a_score, ht_home, ht_away, key_events, duration}
# Prevents ESPN glitches from downgrading an in-play match back to TIMED
_live_state = {}

# Duration cache for finished matches: event_id → "REGULAR"|"EXTRA_TIME"|"PENALTY_SHOOTOUT"
_duration_cache = {}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def parse_event_clock(display_value):
    """'45+2'' → (45, 2),  '23'' → (23, None)"""
    v = (display_value or "").replace("'", "").strip()
    if "+" in v:
        base, extra = v.split("+", 1)
        return (int(base) if base.isdigit() else None,
                int(extra) if extra.isdigit() else None)
    return (int(v) if v.isdigit() else None, None)


def build_detail_entry(status, h_score, a_score, key_events, pen_home=None, pen_away=None):
    """Build a match-details.json entry from raw ESPN keyEvents."""
    goals_out = []
    for e in key_events:
        if not e.get("scoringPlay"):
            continue
        etype = (e.get("type") or {}).get("type", "")
        participants = e.get("participants", [])
        scorer = participants[0].get("athlete", {}).get("displayName", "") if participants else ""
        assist = participants[1].get("athlete", {}).get("displayName", "") if len(participants) > 1 else None
        minute, injury = parse_event_clock((e.get("clock") or {}).get("displayValue", ""))
        team_name = (e.get("team") or {}).get("displayName", "")
        goal_type = "OWN" if etype == "own-goal" else ("PENALTY" if etype == "penalty" else None)
        entry = {
            "minute": minute,
            "injuryTime": injury,
            "type": goal_type,
            "scorer": {"name": scorer},
            "team": {"name": team_name},
        }
        if assist:
            entry["assist"] = {"name": assist}
        goals_out.append(entry)

    bookings_out = []
    for e in key_events:
        if e.get("scoringPlay"):
            continue
        etype = (e.get("type") or {}).get("type", "")
        if etype not in ("yellow-card", "red-card", "yellow-red-card"):
            continue
        participants = e.get("participants", [])
        player = participants[0].get("athlete", {}).get("displayName", "") if participants else ""
        minute, _ = parse_event_clock((e.get("clock") or {}).get("displayValue", ""))
        team_name = (e.get("team") or {}).get("displayName", "")
        card = "YELLOW_RED" if etype == "yellow-red-card" else ("RED" if etype == "red-card" else "YELLOW")
        bookings_out.append({
            "minute": minute,
            "card": card,
            "player": {"name": player},
            "team": {"name": team_name},
        })

    out = {
        "status": status,
        "score": {"fullTime": {"home": h_score, "away": a_score}},
        "goals": goals_out,
        "bookings": bookings_out,
    }
    if pen_home is not None and pen_away is not None:
        out["score"]["penShootout"] = {"home": pen_home, "away": pen_away}
    return out


def normalize_date(d):
    """'2026-06-11T19:00Z' → '2026-06-11T19:00:00Z'"""
    if d and d.endswith("Z") and d.count(":") == 1:
        return d[:-1] + ":00Z"
    return d


SLUG_STAGE = {
    "group-stage":     "GROUP_STAGE",
    "round-of-32":     "ROUND_OF_32",
    "round-of-16":     "ROUND_OF_16",
    "quarterfinals":   "QUARTER_FINALS",
    "semifinals":      "SEMI_FINALS",
    "third-place":     "THIRD_PLACE",
    "3rd-place-match": "THIRD_PLACE",
    "final":           "FINAL",
}

def parse_group_and_stage(event, comp):
    """Extract group and stage from ESPN event."""
    slug  = event.get("season", {}).get("slug", "")
    note  = comp.get("altGameNote", "")
    stage = SLUG_STAGE.get(slug, "GROUP_STAGE")
    group = None
    if ", Group " in note:
        group = "GROUP_" + note.split("Group ")[-1].strip()
    return group, stage


def parse_minute(comp):
    clock = comp["status"].get("displayClock", "")
    base = clock.replace("'", "").split("+")[0].strip()
    return int(base) if base.isdigit() else None

def parse_injury_time(comp):
    clock = comp["status"].get("displayClock", "")
    if "+" in clock:
        part = clock.replace("'", "").split("+", 1)[1].strip()
        return int(part) if part.isdigit() else None
    return None


def fetch_summary(event_id):
    """
    Fetch match summary and return:
      ht_home, ht_away  — first-half scores (or None)
      pen_home, pen_away — penalty shootout scores (or None)
      key_events        — all keyEvents (goals, own goals, cards)
    Uses cache for FINISHED matches.
    """
    if event_id in _cache:
        return _cache[event_id]

    try:
        s = fetch(SUMMARY_URL + str(event_id))

        # Scores from header competitors linescores:
        # [1H, 2H, ET1, ET2, Pens] — indices 0=HT, -1=penalties when len>=5
        hcomps = s.get("header", {}).get("competitions", [{}])[0].get("competitors", [])
        ht_home = ht_away = None
        pen_home = pen_away = None
        for hc in hcomps:
            ls = hc.get("linescores", [])
            if ls:
                try:
                    val = int(ls[0].get("displayValue", "0"))
                    if hc.get("homeAway") == "home":
                        ht_home = val
                    else:
                        ht_away = val
                except ValueError:
                    pass
                # Penalty shootout score is the last linescore when 5+ periods exist
                if len(ls) >= 5:
                    try:
                        pval = int(ls[-1].get("displayValue", "0"))
                        if hc.get("homeAway") == "home":
                            pen_home = pval
                        else:
                            pen_away = pval
                    except ValueError:
                        pass

        key_events = s.get("keyEvents", [])

        return ht_home, ht_away, pen_home, pen_away, key_events

    except Exception as e:
        print(f"  warning: summary failed for {event_id}: {e}")
        return None, None, None, None, []


def build_matches_and_scorers(events):
    matches = []
    match_details = {}
    scorer_stats = defaultdict(lambda: {"goals": 0, "assists": 0, "penalties": 0, "matches": set()})

    for event in events:
        comp    = event["competitions"][0]
        stype   = comp["status"]["type"]
        status  = STATUS_MAP.get(stype["name"], "TIMED")
        group, stage = parse_group_and_stage(event, comp)

        comps  = comp.get("competitors", [])
        home   = next((c for c in comps if c["homeAway"] == "home"), {})
        away   = next((c for c in comps if c["homeAway"] == "away"), {})
        h_team = home.get("team", {})
        a_team = away.get("team", {})

        # Scores and winner — null for TIMED/not-yet-started
        is_started = status in ("IN_PLAY", "PAUSED", "FINISHED")
        h_score = int(home["score"]) if is_started and home.get("score") is not None else None
        a_score = int(away["score"]) if is_started and away.get("score") is not None else None

        # score.winner — used by bracket.html to determine who advances
        winner = None
        if status == "FINISHED" and h_score is not None and a_score is not None:
            if home.get("winner"):
                winner = "HOME_TEAM"
            elif away.get("winner"):
                winner = "AWAY_TEAM"
            else:
                winner = "DRAW"

        eid = int(event["id"])
        ht_home = ht_away = None
        pen_home = pen_away = None
        key_events = []

        duration = DURATION_MAP.get(stype["name"], "REGULAR")

        # Guard: if ESPN transiently returns TIMED for a match we know is live,
        # keep the last known good state rather than writing null scores
        if status == "TIMED" and eid in _live_state:
            saved      = _live_state[eid]
            status     = saved["status"]
            h_score    = saved["h_score"]
            a_score    = saved["a_score"]
            ht_home    = saved["ht_home"]
            ht_away    = saved["ht_away"]
            pen_home   = saved.get("pen_home")
            pen_away   = saved.get("pen_away")
            key_events = saved["key_events"]
            duration   = saved["duration"]
            is_started = True
            print(f"  guard: kept {eid} as {status} (ESPN returned TIMED)")
        elif is_started:
            ht_home, ht_away, pen_home, pen_away, key_events = fetch_summary(eid)
            if status == "FINISHED":
                _cache[eid] = (ht_home, ht_away, pen_home, pen_away, key_events)
                # Preserve duration from live tracking (e.g. ET decided match)
                if eid in _live_state:
                    duration = _live_state[eid]["duration"]
                _duration_cache[eid] = duration
                _live_state.pop(eid, None)
            time.sleep(0.3)  # polite between requests

        if status in ("IN_PLAY", "PAUSED"):
            _live_state[eid] = {
                "status": status, "h_score": h_score, "a_score": a_score,
                "ht_home": ht_home, "ht_away": ht_away,
                "pen_home": pen_home, "pen_away": pen_away,
                "key_events": key_events, "duration": duration,
            }

        # For finished matches seen in previous cycles, restore persisted duration
        if status == "FINISHED" and eid in _duration_cache:
            duration = _duration_cache[eid]

        # Build event card detail entry for started matches
        if is_started:
            match_details[str(eid)] = build_detail_entry(status, h_score, a_score, key_events, pen_home, pen_away)

        # Aggregate scorers (scoring plays only, own goals excluded)
        goals = [e for e in key_events if e.get("scoringPlay") and (e.get("type") or {}).get("type") != "own-goal"]
        for g in goals:
            participants = g.get("participants", [])
            team = g.get("team", {}).get("displayName", "")
            is_pen = g.get("type", {}).get("type") == "penalty"
            if participants:
                name = participants[0].get("athlete", {}).get("displayName", "")
                key = (name, team)
                scorer_stats[key]["goals"] += 1
                scorer_stats[key]["matches"].add(eid)
                if is_pen:
                    scorer_stats[key]["penalties"] += 1
            if len(participants) > 1:
                aname = participants[1].get("athlete", {}).get("displayName", "")
                akey = (aname, team)
                scorer_stats[akey]["assists"] += 1
                scorer_stats[akey]["matches"].add(eid)

        city = comp.get("venue", {}).get("address", {}).get("city", "").split(",")[0].strip()

        matches.append({
            "id":      eid,
            "utcDate": normalize_date(event["date"]),
            "status":     status,
            "period":     PERIOD_MAP.get(stype["name"]),
            "minute":     parse_minute(comp) if status == "IN_PLAY" else None,
            "injuryTime": parse_injury_time(comp) if status == "IN_PLAY" else None,
            "stage":   stage,
            "group":   group,
            "homeTeam": {
                "name":      h_team.get("displayName", ""),
                "shortName": h_team.get("shortDisplayName", ""),
                "tla":       h_team.get("abbreviation", ""),
            },
            "awayTeam": {
                "name":      a_team.get("displayName", ""),
                "shortName": a_team.get("shortDisplayName", ""),
                "tla":       a_team.get("abbreviation", ""),
            },
            "score": {
                "winner":   winner,
                "duration": duration,
                "fullTime": {"home": h_score, "away": a_score},
                "halfTime": {"home": ht_home, "away": ht_away},
                "penalties": {"home": pen_home, "away": pen_away} if duration == "PENALTY_SHOOTOUT" and pen_home is not None else None,
            },
            "venue": city,
        })

    scorers = []
    for (name, team), s in sorted(scorer_stats.items(), key=lambda x: (-x[1]["goals"], -x[1]["assists"])):
        scorers.append({
            "player":        {"name": name},
            "team":          {"shortName": team},
            "goals":         s["goals"],
            "assists":       s["assists"] or None,
            "penalties":     s["penalties"] or None,
            "playedMatches": len(s["matches"]),
        })

    return matches, scorers, match_details


def build_group_winners(matches):
    """
    Returns {letter: {first, second}} for groups where all 6 games are FINISHED.
    Uses pts → GD → GF → alphabetical sort (approximation; H2H edge cases are rare).
    """
    pts_map  = defaultdict(lambda: defaultdict(int))
    gd_map   = defaultdict(lambda: defaultdict(int))
    gf_map   = defaultdict(lambda: defaultdict(int))
    finished = defaultdict(int)

    for m in matches:
        if m.get("stage") != "GROUP_STAGE" or m.get("status") != "FINISHED":
            continue
        grp = (m.get("group") or "").replace("GROUP_", "")
        if not grp:
            continue
        hg = m["score"]["fullTime"]["home"]
        ag = m["score"]["fullTime"]["away"]
        if hg is None or ag is None:
            continue
        home = _display(m["homeTeam"].get("shortName") or m["homeTeam"].get("name", ""))
        away = _display(m["awayTeam"].get("shortName") or m["awayTeam"].get("name", ""))
        if not home or not away:
            continue

        finished[grp] += 1
        gf_map[grp][home] += hg;  gf_map[grp][away] += ag
        gd_map[grp][home] += hg - ag;  gd_map[grp][away] += ag - hg
        if hg > ag:   pts_map[grp][home] += 3
        elif hg < ag: pts_map[grp][away] += 3
        else:         pts_map[grp][home] += 1; pts_map[grp][away] += 1

    winners = {}
    for grp, n in finished.items():
        if n < 6:
            continue
        teams = list({*pts_map[grp].keys(), *gf_map[grp].keys()})
        teams.sort(key=lambda t: (-pts_map[grp][t], -gd_map[grp][t], -gf_map[grp][t], t))
        if len(teams) >= 2:
            winners[grp] = {"first": teams[0], "second": teams[1]}
    return winners


def write_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def run():
    print(f"[fetcher] starting — ESPN source, {INTERVAL}s interval")
    while True:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        try:
            raw = fetch(SCORES_URL)
            events = raw.get("events", [])

            matches, scorers, match_details = build_matches_and_scorers(events)

            write_atomic(DATA_OUT, {"matches": matches})
            print(f"[{ts}] data.json updated ({len(matches)} matches)")

            write_atomic(SCORERS_OUT, {"scorers": scorers})
            print(f"[{ts}] scorers.json updated ({len(scorers)} scorers)")

            write_atomic(DETAILS_OUT, match_details)
            print(f"[{ts}] match-details.json updated ({len(match_details)} entries)")

            group_winners = build_group_winners(matches)
            write_atomic(WINNERS_OUT, group_winners)
            print(f"[{ts}] group-winners.json updated ({len(group_winners)} groups complete)")

        except Exception as e:
            print(f"[{ts}] error: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    run()
