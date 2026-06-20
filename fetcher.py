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
DATA_OUT    = "/data/data.json"
SCORERS_OUT = "/data/scorers.json"
INTERVAL    = 60

# ESPN status → period (extra time / penalty / None)
PERIOD_MAP = {
    "STATUS_EXTRA_TIME":             "EXTRA_TIME",
    "STATUS_EXTRA_TIME_SECOND_HALF": "EXTRA_TIME",
    "STATUS_EXTRA_TIME_HALF_TIME":   "EXTRA_TIME",
    "STATUS_PENALTY":                "PENALTY",
}

# ESPN status → score.duration (football-data.org schema)
DURATION_MAP = {
    "STATUS_EXTRA_TIME":             "EXTRA_TIME",
    "STATUS_EXTRA_TIME_SECOND_HALF": "EXTRA_TIME",
    "STATUS_EXTRA_TIME_HALF_TIME":   "EXTRA_TIME",
    "STATUS_PENALTY":                "PENALTY_SHOOTOUT",
    "STATUS_FINAL_PEN":              "PENALTY_SHOOTOUT",
}

# ESPN status → football-data.org status
STATUS_MAP = {
    "STATUS_SCHEDULED":              "TIMED",
    "STATUS_IN":                     "IN_PLAY",
    "STATUS_FIRST_HALF":             "IN_PLAY",
    "STATUS_SECOND_HALF":            "IN_PLAY",
    "STATUS_HALFTIME":               "PAUSED",
    "STATUS_EXTRA_TIME":             "IN_PLAY",
    "STATUS_EXTRA_TIME_SECOND_HALF": "IN_PLAY",
    "STATUS_EXTRA_TIME_HALF_TIME":   "PAUSED",
    "STATUS_PENALTY":                "IN_PLAY",
    "STATUS_FULL_TIME":              "FINISHED",
    "STATUS_FINAL":                  "FINISHED",
    "STATUS_FINAL_PEN":              "FINISHED",
    "STATUS_ABANDONED":              "FINISHED",
    "STATUS_CANCELED":               "TIMED",
    "STATUS_POSTPONED":              "TIMED",
}

# Cache for FINISHED matches: event_id → (ht_home, ht_away, goals[])
_cache = {}

# Live state guard: event_id → {status, h_score, a_score, ht_home, ht_away, goals, duration}
# Prevents ESPN glitches from downgrading an in-play match back to TIMED
_live_state = {}

# Duration cache for finished matches: event_id → "REGULAR"|"EXTRA_TIME"|"PENALTY_SHOOTOUT"
_duration_cache = {}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


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
      goals             — list of scoring play keyEvents (own goals excluded)
    Uses cache for FINISHED matches.
    """
    if event_id in _cache:
        return _cache[event_id]

    try:
        s = fetch(SUMMARY_URL + str(event_id))

        # Half-time scores from header competitors linescores
        hcomps = s.get("header", {}).get("competitions", [{}])[0].get("competitors", [])
        ht_home = ht_away = None
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

        # Goal events
        goals = [
            e for e in s.get("keyEvents", [])
            if e.get("scoringPlay") and e.get("type", {}).get("type") != "own-goal"
        ]

        return ht_home, ht_away, goals

    except Exception as e:
        print(f"  warning: summary failed for {event_id}: {e}")
        return None, None, []


def build_matches_and_scorers(events):
    matches = []
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
        goals = []

        duration = DURATION_MAP.get(stype["name"], "REGULAR")

        # Guard: if ESPN transiently returns TIMED for a match we know is live,
        # keep the last known good state rather than writing null scores
        if status == "TIMED" and eid in _live_state:
            saved    = _live_state[eid]
            status   = saved["status"]
            h_score  = saved["h_score"]
            a_score  = saved["a_score"]
            ht_home  = saved["ht_home"]
            ht_away  = saved["ht_away"]
            goals    = saved["goals"]
            duration = saved["duration"]
            is_started = True
            print(f"  guard: kept {eid} as {status} (ESPN returned TIMED)")
        elif is_started:
            ht_home, ht_away, goals = fetch_summary(eid)
            if status == "FINISHED":
                _cache[eid] = (ht_home, ht_away, goals)
                # Preserve duration from live tracking (e.g. ET decided match)
                if eid in _live_state:
                    duration = _live_state[eid]["duration"]
                _duration_cache[eid] = duration
                _live_state.pop(eid, None)
            time.sleep(0.3)  # polite between requests

        if status in ("IN_PLAY", "PAUSED"):
            _live_state[eid] = {
                "status": status, "h_score": h_score, "a_score": a_score,
                "ht_home": ht_home, "ht_away": ht_away, "goals": goals,
                "duration": duration,
            }

        # For finished matches seen in previous cycles, restore persisted duration
        if status == "FINISHED" and eid in _duration_cache:
            duration = _duration_cache[eid]

        # Aggregate scorers
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

    return matches, scorers


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

            matches, scorers = build_matches_and_scorers(events)

            write_atomic(DATA_OUT, {"matches": matches})
            print(f"[{ts}] data.json updated ({len(matches)} matches)")

            write_atomic(SCORERS_OUT, {"scorers": scorers})
            print(f"[{ts}] scorers.json updated ({len(scorers)} scorers)")

        except Exception as e:
            print(f"[{ts}] error: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    run()
