import json

ENVIRONMENT = {
    "building": "single floor, three exits",
    "zones": [
        "Main Hall", "Classroom", "Office1", "Office2", "Office3",
        "Office4", "Office5", "Office6", "Office7",
        "Bathrooms", "Hallway 1", "Hallway 2", "Hallway 3"
    ],
    "exits": ["Exit 1", "Exit 2", "Exit 3"],
    "exit_notes": {
        "Exit 1": "reached through Main Hall",
        "Exit 2": "partly blocked by a fixed obstacle, reached through Hallway 2",
        "Exit 3": "reached through Hallway 1"
    },
    "sensors": {
        "zone_occupancy": "one counter per zone and exit",
        "smoke_detectors": "placed in hallways and key zones, report Clear or Smoke detected per tick",
        "hazard": "fire severity per agent, global burning cell count, structural damage tracking"
    }
}

# Static definitions for every term shown on the dashboard.
# Small and fixed, doesn't grow with simulation data, so it costs
# the same handful of tokens no matter what question is asked.
GLOSSARY = {
    "Total Agents": "The total number of agents who started inside the building at the beginning of the run.",
    "Agents Escaped": "The number of agents who have successfully exited through any exit, as of the current time shown.",
    "Vulnerable Inside": "Agents with an age band or disability tag (e.g. elderly, child, mobility-impaired) who are still inside and have not exited.",
    "Avg Agent Health": "The average health value (0-100) across all agents still inside the building at the current time. Health drops from fire exposure and smoke/visibility damage.",
    "Critical Health Inside": "The number of agents still inside whose health has dropped to a critical, low threshold.",
    "Busiest Zone": "The zone (room or hallway) with the highest agent occupancy count at the current time.",
    "Runtime": "How long the simulation has been running, in seconds, up to the current time shown.",
    "Trapped": "Agents unable to reach an exit, for example blocked by fire, structural damage, or smoke, who have not exited.",
}


def load_records(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def summarize(records):
    # ── Sys-Summary (final tick within whatever records were passed in) ──
    summaries = [r for r in records if r.get("sensorId") == "Sys-Summary"]
    exited = trapped = inside = 0
    vulnerable_inside = critical_health_inside = 0
    if summaries:
        for part in summaries[-1].get("eventDetails", "").split():
            k, _, v = part.partition(":")
            if k == "Exited":                    exited                 = int(v)
            if k == "Trapped":                   trapped                = int(v)
            if k == "Inside":                    inside                 = int(v)
            if k == "VulnerableStillInside":     vulnerable_inside      = int(v)
            if k == "CriticalHealthStillInside": critical_health_inside = int(v)

    # ── Agent profiles (sensorType=5) ─────────────────────────────────────
    profiles = [r for r in records if r.get("sensorType") == 5]
    agent_profiles = []
    for p in profiles:
        agent_profiles.append({
            "agentId":    p.get("agentId"),
            "ageBand":    p.get("ageBand"),
            "disability": p.get("disability"),
            "baseSpeed":  round(p.get("speed", 0), 2),
            "startHealth":p.get("health", 100),
        })
    age_breakdown = {}
    disability_breakdown = {}
    for p in agent_profiles:
        age_breakdown[p["ageBand"]] = age_breakdown.get(p["ageBand"], 0) + 1
        disability_breakdown[p["disability"]] = disability_breakdown.get(p["disability"], 0) + 1

    # ── Agent exits (sensorType=2, hasExited=True) ────────────────────────
    agent_exits = []
    for r in records:
        if r.get("sensorType") == 2 and r.get("hasExited") is True:
            agent_exits.append({
                "agentId":      r.get("agentId"),
                "exitLocation": r.get("location"),
                "exitTime":     round(r.get("exitTime", r.get("timestamp", 0)), 2),
                "ageBand":      r.get("ageBand", ""),
                "disability":   r.get("disability", ""),
                "healthAtExit": round(r.get("health", 0), 1),
                "fireDamage":   round(r.get("fireDamageTotal", 0), 2),
                "visDamage":    round(r.get("visibilityDamageTotal", 0), 2),
                "path":         r.get("eventDetails", ""),
            })
    agent_exits.sort(key=lambda x: x["exitTime"])

    # ── Trapped agents (sensorType=2, trapReason not empty/"None") ────────
    trapped_agents = []
    for r in records:
        if r.get("sensorType") == 2:
            reason = r.get("trapReason", "")
            if reason and reason != "None" and not r.get("hasExited", False):
                trapped_agents.append({
                    "agentId":    r.get("agentId"),
                    "location":   r.get("location"),
                    "trapReason": reason,
                    "ageBand":    r.get("ageBand", ""),
                    "disability": r.get("disability", ""),
                    "healthAtTrap": round(r.get("health", 0), 1),
                })

    # ── Evacuation triggers (sensorType=3, EVENT-Evac-*) ──────────────────
    evac_triggers = []
    for r in records:
        if r.get("sensorType") == 3 and str(r.get("sensorId","")).startswith("EVENT-Evac"):
            evac_triggers.append({
                "agentId": r.get("agentId") or r.get("sensorId","").replace("EVENT-Evac-",""),
                "reason":  r.get("eventDetails", ""),
                "time":    round(r.get("timestamp", 0), 2),
            })

    # ── Other simulation events (exit blocked, warnings, etc.) ───────────
    warnings, flees, blocks, other_events = [], [], [], []
    for r in records:
        if r.get("sensorType") == 3 and r.get("sensorId") != "Sys-Summary" \
                and not str(r.get("sensorId","")).startswith("EVENT-Evac"):
            sid    = str(r.get("sensorId", ""))
            detail = r.get("eventDetails", "")
            t      = round(r.get("timestamp", 0), 1)
            if sid.startswith("EVENT-Warning"):
                warnings.append(f"At {t}s, {detail}")
            elif sid.startswith("EVENT-Flee"):
                flees.append(f"At {t}s, {detail}")
            elif sid.startswith("EVENT-Exit"):
                blocks.append(f"At {t}s, {detail}")
            else:
                other_events.append(f"At {t}s [{sid}] {detail}")

    # ── Smoke detectors ───────────────────────────────────────────────────
    smoke_events = []
    seen_smoke = set()
    for r in sorted(records, key=lambda x: x.get("timestamp", 0)):
        if r.get("sensorType") == 1 and r.get("eventDetails","").strip() != "Clear":
            key = r.get("sensorId")
            if key not in seen_smoke:
                seen_smoke.add(key)
                smoke_events.append({
                    "detector": r.get("sensorId"),
                    "location": r.get("location"),
                    "firstDetected": round(r.get("timestamp", 0), 2),
                    "status": r.get("eventDetails", ""),
                })

    # ── Structural damage (sensorType=6, last record per location) ────────
    dmg_by_loc = {}
    for r in records:
        if r.get("sensorType") == 6:
            loc = r.get("location", "Unknown")
            dmg_by_loc[loc] = r
    structural_damage = []
    for loc, r in dmg_by_loc.items():
        structural_damage.append({
            "location":          loc,
            "avgCharPct":        round(r.get("charLevel", 0) * 100, 1),
            "surfacesDestroyed": r.get("surfacesDestroyed", 0),
            "surfacesTotal":     r.get("surfacesTotal", 0),
            "damageLabel":       r.get("damageLabel", ""),
        })

    return {
        "total_agents":             len(agent_profiles),
        "exited":                   exited,
        "not_escaped":              trapped,
        "still_inside_at_end":      inside,
        "vulnerable_still_inside":  vulnerable_inside,
        "critical_health_inside":   critical_health_inside,
        "age_breakdown":            age_breakdown,
        "disability_breakdown":     disability_breakdown,
        "agent_profiles":           agent_profiles,
        "agent_exits":              agent_exits,
        "trapped_agents":           trapped_agents,
        "evac_triggers":            evac_triggers,
        "warnings":                 warnings,
        "cut_off":                  flees,
        "blocked_exits":            blocks,
        "other_events":             other_events,
        "smoke_detectors_triggered":smoke_events,
        "structural_damage":        structural_damage,
    }


def build_package(path, start=None, end=None):
    records = load_records(path)

    # Filter to the requested time window before summarizing.
    # Everything downstream (Sys-Summary lookup, exits, trapped, smoke,
    # damage) already picks "last" or accumulates over the list it's given,
    # so filtering here is enough to make the whole summary reflect
    # "as of time T" instead of always being the full/final run.
    if start is not None:
        records = [r for r in records if r.get("timestamp", 0) >= start]
    if end is not None:
        records = [r for r in records if r.get("timestamp", 0) <= end]

    summary = summarize(records)
    return json.dumps({
        "environment": ENVIRONMENT,
        "glossary": GLOSSARY,
        "summary": summary,
    })


if __name__ == "__main__":
    print(build_package("simulation_data.jsonl"))
