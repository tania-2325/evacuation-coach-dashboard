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
        "Exit 2": "reached through Hallway 2",
        "Exit 3": "reached through Hallway 1"
    },
"exit_blocking_note": "Any exit can be manually blocked or unblocked at any point during a run as a deliberate researcher intervention. No exit is inherently blocked by default, check the events for whether and when a specific exit was actually blocked in this run.",
    "sensors": {
        "zone_occupancy": "one counter per zone and exit",
        "smoke_detectors": "placed in hallways and key zones, report Clear or Smoke detected per tick",
        "hazard": "fire severity per agent, global burning cell count, structural damage tracking"
    }
}

EXIT_ZONES = {"Exit 1", "Exit 2", "Exit 3"}

GLOSSARY = {
    "Total Agents": "The total number of agents who started inside the building at the beginning of the run.",
    "Agents Escaped": "The number of agents who have successfully exited through any exit, as of the current time shown.",
    "Agents Trapped": "The number of agents confirmed unable to escape, for example blocked by fire or a collapsed route, as of the current time shown. This does not include agents who are still evacuating and simply have not exited yet.",
    "Vulnerable Inside": "Agents with an age band or disability tag (e.g. elderly, child, mobility-impaired) who are still inside and have not exited.",
    "Avg Agent Health": "The average health value (0-100) across all agents still inside the building at the current time. Health drops from fire exposure and smoke/visibility damage.",
    "Critical Health Inside": "The number of agents still inside whose health has dropped to a critical, low threshold.",
    "Busiest Zone": "The zone (room or hallway) with the highest agent occupancy count at the current time.",
    "Runtime": "How long the simulation has been running, in seconds, up to the current time shown.",
    "Recent Activity": "A live list of the most recent timed events in the run, such as smoke being detected in a zone, an agent starting to evacuate, or an agent exiting the building, shown up to the current time.",
    "Demographic Escape Progression": "A chart of the complete run showing how many agents from each age group (Young, Adult, Elderly) remain inside over time, starting at that group's total headcount and stepping down as members exit. Always shows the whole run, not just the current dashboard moment.",
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


def build_demographic_summary(records):
    """Always computed from the complete, unfiltered run, matching the
    static Demographic Escape Progression chart on the dashboard, which
    also always shows the whole run regardless of the timeline slider.
    """
    profiles = [r for r in records if r.get("sensorType") == 5]
    totals = {}
    for p in profiles:
        age = p.get("ageBand", "Unknown")
        totals[age] = totals.get(age, 0) + 1

    exit_by_agent = {}
    for r in records:
        if r.get("sensorType") == 2 and r.get("hasExited") is True:
            exit_by_agent[r.get("agentId")] = r

    by_age_exits = {}
    for agent_id, r in exit_by_agent.items():
        age = r.get("ageBand", "Unknown")
        by_age_exits.setdefault(age, []).append({
            "agentId": agent_id,
            "time": round(r.get("exitTime", r.get("timestamp", 0)), 2),
        })

    trapped_by_agent = {}
    for r in records:
        if r.get("sensorType") == 2:
            reason = r.get("trapReason", "")
            if reason and reason != "None" and not r.get("hasExited", False):
                trapped_by_agent[r.get("agentId")] = r

    groups = {}
    for age, total in totals.items():
        exits = sorted(by_age_exits.get(age, []), key=lambda x: x["time"])
        trapped_in_group = [
            {"agentId": aid, "reason": r.get("trapReason", "")}
            for aid, r in trapped_by_agent.items()
            if r.get("ageBand") == age
        ]
        groups[age] = {
            "total_in_group": total,
            "escaped_count": len(exits),
            "first_to_escape": exits[0] if exits else None,
            "last_to_escape": exits[-1] if exits else None,
            "trapped_in_group": trapped_in_group,
        }

    finished_times = {age: g["last_to_escape"]["time"]
                       for age, g in groups.items() if g["last_to_escape"]}
    group_finished_first = min(finished_times, key=finished_times.get) if finished_times else None
    group_finished_last  = max(finished_times, key=finished_times.get) if finished_times else None

    return {
        "by_group": groups,
        "group_finished_escaping_first": group_finished_first,
        "group_finished_escaping_last": group_finished_last,
    }


def build_disability_summary(records):
    """Same structure as build_demographic_summary, grouped by disability
    status instead of age band. Always computed from the complete,
    unfiltered run.
    """
    profiles = [r for r in records if r.get("sensorType") == 5]
    totals = {}
    for p in profiles:
        dis = p.get("disability") or "None"
        totals[dis] = totals.get(dis, 0) + 1

    exit_by_agent = {}
    for r in records:
        if r.get("sensorType") == 2 and r.get("hasExited") is True:
            exit_by_agent[r.get("agentId")] = r

    by_dis_exits = {}
    for agent_id, r in exit_by_agent.items():
        dis = r.get("disability") or "None"
        by_dis_exits.setdefault(dis, []).append({
            "agentId": agent_id,
            "time": round(r.get("exitTime", r.get("timestamp", 0)), 2),
        })

    trapped_by_agent = {}
    for r in records:
        if r.get("sensorType") == 2:
            reason = r.get("trapReason", "")
            if reason and reason != "None" and not r.get("hasExited", False):
                trapped_by_agent[r.get("agentId")] = r

    groups = {}
    for dis, total in totals.items():
        exits = sorted(by_dis_exits.get(dis, []), key=lambda x: x["time"])
        trapped_in_group = [
            {"agentId": aid, "reason": r.get("trapReason", "")}
            for aid, r in trapped_by_agent.items()
            if (r.get("disability") or "None") == dis
        ]
        groups[dis] = {
            "total_in_group": total,
            "escaped_count": len(exits),
            "first_to_escape": exits[0] if exits else None,
            "last_to_escape": exits[-1] if exits else None,
            "trapped_in_group": trapped_in_group,
        }

    finished_times = {dis: g["last_to_escape"]["time"]
                       for dis, g in groups.items() if g["last_to_escape"]}
    group_finished_first = min(finished_times, key=finished_times.get) if finished_times else None
    group_finished_last  = max(finished_times, key=finished_times.get) if finished_times else None

    return {
        "by_group": groups,
        "group_finished_escaping_first": group_finished_first,
        "group_finished_escaping_last": group_finished_last,
    }


def build_congestion_summary(records):
    """Always computed from the complete, unfiltered run. At each logged
    tick, finds whichever zone had the single highest occupancy, then
    finds when that per-tick busiest value was highest overall, i.e.
    when the building was most congested. Kept compact, one peak figure
    plus a coarse timing label, not a full per-tick timeline, to avoid
    the same token bloat that caused problems earlier in this project.
    """
    zone_records = [r for r in records if r.get("sensorType") == 0]
    if not zone_records:
        return {
            "peak_time": None, "peak_zone": None, "peak_occupancy": None,
            "peak_period": None, "congestion_roughly_constant": None,
        }

    by_time = {}
    for r in zone_records:
        ts  = round(r.get("timestamp", 0), 3)
        val = r.get("value", 0)
        loc = r.get("location", "Unknown")
        if ts not in by_time or val > by_time[ts]["value"]:
            by_time[ts] = {"zone": loc, "value": val}

    peak_time = max(by_time, key=lambda t: by_time[t]["value"])
    peak_info = by_time[peak_time]
    runtime   = max(by_time.keys())

    values = [v["value"] for v in by_time.values()]
    max_val = max(values) if values else 0
    value_range = (max_val - min(values)) if values else 0
    congestion_roughly_constant = (value_range <= max_val * 0.25) if max_val > 0 else True

    frac = (peak_time / runtime) if runtime else 0
    if frac < 0.33:
        peak_period = "the first third of the run"
    elif frac < 0.67:
        peak_period = "around the middle of the run"
    else:
        peak_period = "the final third of the run"

    return {
        "peak_time":       round(peak_time, 2),
        "peak_zone":       peak_info["zone"],
        "peak_occupancy":  peak_info["value"],
        "peak_period":     peak_period,
        "congestion_roughly_constant": congestion_roughly_constant,
    }


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
    exits_by_agent = {}
    for r in records:
        if r.get("sensorType") == 2 and r.get("hasExited") is True:
            exits_by_agent[r.get("agentId")] = r
    agent_exits = []
    for agent_id, r in exits_by_agent.items():
        agent_exits.append({
            "agentId":      agent_id,
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

    # ── Disabled agents currently still inside, as of this filtered
    # window ──────────────────────────────────────────────────────────
    disabled_total_in_window = sum(
        1 for p in agent_profiles if p.get("disability") not in (None, "", "None")
    )
    disabled_exited_in_window = sum(
        1 for e in agent_exits if e.get("disability") not in (None, "", "None")
    )
    disabled_inside_now = disabled_total_in_window - disabled_exited_in_window

    # ── Exit usage: how many agents escaped through each named exit ──────
    exit_usage_counts = {}
    for r in agent_exits:
        loc = r.get("exitLocation")
        exit_usage_counts[loc] = exit_usage_counts.get(loc, 0) + 1
    busiest_exit = max(exit_usage_counts, key=exit_usage_counts.get) if exit_usage_counts else None

    # ── Zone occupancy: current count per zone as of this filtered
    # window ────────────────────────────────────────────────────────────
    latest_zone_reading = {}
    for r in records:
        if r.get("sensorType") == 0:
            loc = r.get("location", "Unknown")
            ts  = r.get("timestamp", 0)
            if loc not in latest_zone_reading or ts >= latest_zone_reading[loc].get("timestamp", 0):
                latest_zone_reading[loc] = r

    zone_occupancy_now = {}
    for loc, r in latest_zone_reading.items():
        zone_occupancy_now[loc] = int(r.get("value", 0))

    exit_counts = {}
    for e in agent_exits:
        loc = e.get("exitLocation", "")
        if loc in EXIT_ZONES:
            exit_counts[loc] = exit_counts.get(loc, 0) + 1
    for loc in EXIT_ZONES:
        zone_occupancy_now[loc] = exit_counts.get(loc, 0)

    busiest_zone_now = None
    if zone_occupancy_now:
        busiest_zone_now = max(zone_occupancy_now, key=zone_occupancy_now.get)

    # ── Trapped agents (sensorType=2, trapReason not empty/"None") ────────
    trapped_by_agent = {}
    for r in records:
        if r.get("sensorType") == 2:
            reason = r.get("trapReason", "")
            if reason and reason != "None" and not r.get("hasExited", False):
                trapped_by_agent[r.get("agentId")] = r
    trapped_agents = []
    for agent_id, r in trapped_by_agent.items():
        trapped_agents.append({
            "agentId":      agent_id,
            "location":     r.get("location"),
            "trapReason":   r.get("trapReason", ""),
            "ageBand":      r.get("ageBand", ""),
            "disability":   r.get("disability", ""),
            "healthAtTrap": round(r.get("health", 0), 1),
        })

    # ── Average agent health as of this filtered window's latest tick ────
    latest_health_by_agent = {}
    for r in records:
        if r.get("sensorType") == 2 and not r.get("hasExited", False):
            agent_id = r.get("agentId")
            ts = r.get("timestamp", 0)
            if agent_id not in latest_health_by_agent or ts >= latest_health_by_agent[agent_id].get("timestamp", 0):
                latest_health_by_agent[agent_id] = r
    healthy_values = [r.get("health", 0) for r in latest_health_by_agent.values() if r.get("health", 0) > 0]
    avg_agent_health_now = round(sum(healthy_values) / len(healthy_values), 1) if healthy_values else None

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
            elif sid.startswith("EVENT-Exit") or sid.startswith("EVENT-UserBlock"):
                blocks.append(f"At {t}s, {detail}")
            else:
                other_events.append(f"At {t}s [{sid}] {detail}")

    # ── Smoke detectors: first-ever alert per detector ────────────────────
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

    # ── Smoke: which zones currently have smoke, as of this filtered
    # window's latest data ─────────────────────────────────────────────────
    latest_smoke_by_sensor = {}
    for r in records:
        if r.get("sensorType") == 1:
            sid = r.get("sensorId")
            ts  = r.get("timestamp", 0)
            if sid not in latest_smoke_by_sensor or ts >= latest_smoke_by_sensor[sid].get("timestamp", 0):
                latest_smoke_by_sensor[sid] = r
    smoke_zones_active_now = []
    for sid, r in latest_smoke_by_sensor.items():
        if r.get("eventDetails", "").strip() != "Clear":
            smoke_zones_active_now.append({
                "detector": sid,
                "location": r.get("location"),
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
        "avg_agent_health_now":     avg_agent_health_now,
        "zone_occupancy_now":       zone_occupancy_now,
        "busiest_zone_now":         busiest_zone_now,
        "exit_usage_counts":        exit_usage_counts,
        "busiest_exit":             busiest_exit,
        "disabled_inside_now":      disabled_inside_now,
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
        "smoke_zones_active_now":   smoke_zones_active_now,
        "structural_damage":        structural_damage,
    }


def build_package(path, start=None, end=None):
    all_records = load_records(path)
    demographic_progression = build_demographic_summary(all_records)
    disability_progression  = build_disability_summary(all_records)
    congestion_summary      = build_congestion_summary(all_records)

    records = all_records
    if start is not None:
        records = [r for r in records if r.get("timestamp", 0) >= start]
    if end is not None:
        records = [r for r in records if r.get("timestamp", 0) <= end]

    summary = summarize(records)
    return json.dumps({
        "environment": ENVIRONMENT,
        "glossary": GLOSSARY,
        "summary": summary,
        "demographic_escape_progression": demographic_progression,
        "disability_escape_progression": disability_progression,
        "congestion_over_time": congestion_summary,
    })


if __name__ == "__main__":
    print(build_package("simulation_data.jsonl"))
