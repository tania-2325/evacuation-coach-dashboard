"""
Evacuation Coach Dashboard — Streamlit Cloud version
Setup:  pip install streamlit pandas plotly requests
Run locally:  streamlit run app.py
Deploy: push to GitHub, deploy via share.streamlit.io, add GROQ_API_KEY in Secrets.
"""

import json
import tempfile
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from context_builder import build_package
from prompts import WHO_FAILED, BOTTLENECKS, RECOMMENDATIONS, WHAT_IF, DIRECT_QUESTION, build_prompt
from llm_connection import ask_coach


# ── Config ────────────────────────────────────────────────────────────────────
BUILDING_LAYOUT = {
    "Bathrooms": {"x": 3.5,  "y": 6.2, "width": 2.0,  "height": 1.3},
    "Offices 1": {"x": 5.8,  "y": 6.2, "width": 1.4,  "height": 1.3},
    "Offices 2": {"x": 7.5,  "y": 6.2, "width": 2.0,  "height": 1.3},
    "Exit 3":    {"x": 0.0,  "y": 4.8, "width": 1.0,  "height": 1.2},
    "Hallway 1": {"x": 1.2,  "y": 5.2, "width": 2.2,  "height": 0.8},
    "Main Hall": {"x": 3.5,  "y": 2.5, "width": 1.7,  "height": 2.7},
    "Hallway 2": {"x": 5.3,  "y": 5.2, "width": 3.2,  "height": 0.8},
    "Exit 2":    {"x": 9.5,  "y": 4.8, "width": 0.8,  "height": 1.2},
    "Offices 7": {"x": 1.2,  "y": 3.2, "width": 1.6,  "height": 1.8},
    "Offices 3": {"x": 5.3,  "y": 4.0, "width": 1.5,  "height": 1.1},
    "Hallway 3": {"x": 7.0,  "y": 2.5, "width": 0.7,  "height": 2.5},
    "Offices 5": {"x": 8.0,  "y": 4.0, "width": 1.3,  "height": 1.1},
    "Offices 4": {"x": 5.3,  "y": 2.5, "width": 1.5,  "height": 1.3},
    "Offices 6": {"x": 8.0,  "y": 2.5, "width": 1.5,  "height": 1.3},
    "Classroom": {"x": 0.3,  "y": 0.3, "width": 2.9,  "height": 2.8},
    "Exit 1":    {"x": 3.5,  "y": 1.0, "width": 1.3,  "height": 1.2},
}
EXIT_ZONES = {"Exit 1", "Exit 2", "Exit 3"}

C = {
    "bg":          "#ffffff",
    "surface":     "#faf9f7",
    "border":      "#e2e8f0",
    "text":        "#1a2332",
    "soft":        "#64748b",
    "muted":       "#94a3b8",
    "fire_dark":   "#5f0f0a",
    "fire_red":    "#ab2a18",
    "fire_orange": "#e38931",
    "fire_yellow": "#ecb02b",
    "fire_light":  "#e8c351",
    "tbl_head":    "#fef3c7",
    "tbl_body":    "#fffbeb",
    "tbl_border":  "#f0d97a",
}

SIM_WORDS = [
    "agent","exit","fire","escape","trapped","evacuat","zone","hallway",
    "smoke","hazard","block","warning","route","simulation","sensor",
    "design","bottleneck","flee","occupancy","health","elderly","young",
    "adult","disability","vulnerable","alarm","detector",
    "activity","recent","runtime","busiest","breakdown","total","still",
    "inside","status","kpi","chart","table","dashboard","coach","layout",
    "mean","building",
]
REFUSAL = "I can only answer questions about the simulation results."
MENU = {
    "Who did not escape": WHO_FAILED,
    "Bottlenecks":        BOTTLENECKS,
    "Recommendations":    RECOMMENDATIONS,
}


# ── Page + CSS ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Evacuation Coach", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown(f"""
<style>

.st-key-age_donut [data-testid="stPlotlyChart"] {{
    background:transparent !important;
    border:none !important;
    box-shadow:none !important;
}}

.block-container {{
    padding-top:1rem; padding-bottom:0.5rem;
    padding-left:2rem; padding-right:2rem;
    max-width:100%;
}}
#MainMenu, footer, header {{ visibility:hidden; }}

[data-testid="stPlotlyChart"] {{
    border:1px solid {C['border']};
    border-radius:10px;
    overflow:hidden;
    background:{C['bg']};
    box-shadow:0 2px 6px rgba(15,23,42,0.06);
}}

.kpi-card {{
    background:{C['bg']}; border:1px solid {C['border']};
    border-left:4px solid {C['fire_orange']};
    border-radius:10px; padding:16px 18px 14px 18px;
    box-shadow:0 2px 8px rgba(15,23,42,0.07); height:100%;
}}
.kpi-card-warn    {{ border-left-color:{C['fire_red']}; }}
.kpi-card-neutral {{ border-left-color:{C['muted']}; }}
.kpi-card-health  {{ border-left-color:#4ade80; }}
.kpi-card-vuln    {{ border-left-color:{C['fire_yellow']}; }}

.kpi-top {{
    display:flex; justify-content:space-between;
    align-items:flex-start; margin-bottom:4px;
}}
.kpi-label {{
    color:{C['soft']}; font-size:0.68rem;
    text-transform:uppercase; letter-spacing:0.1em; font-weight:700;
}}
.kpi-badge {{
    width:30px; height:30px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    font-size:0.85rem; font-weight:700; flex-shrink:0;
}}
.kpi-badge-orange {{ background:#fff3e0; color:{C['fire_orange']}; }}
.kpi-badge-red    {{ background:#fde8e8; color:{C['fire_red']}; }}
.kpi-badge-grey   {{ background:#f1f5f9; color:{C['soft']}; }}
.kpi-badge-green  {{ background:#f0fdf4; color:#16a34a; }}
.kpi-badge-yellow {{ background:#fefce8; color:{C['fire_yellow']}; }}

.kpi-value {{
    color:{C['text']}; font-size:2.2rem; font-weight:800;
    font-variant-numeric:tabular-nums; line-height:1.05;
    margin:2px 0 8px 0;
}}
.kpi-good  {{ color:{C['fire_orange']}; }}
.kpi-warn  {{ color:{C['fire_red']}; }}
.kpi-green {{ color:#16a34a; }}
.kpi-sub   {{
    color:{C['muted']}; font-size:0.7rem;
    border-top:1px solid {C['border']}; padding-top:6px;
}}

.app-title {{ color:{C['text']}; font-size:1.3rem; font-weight:700; }}
.app-sub   {{ color:{C['muted']}; font-size:0.78rem; }}
.sec-label {{
    color:{C['soft']}; font-size:0.72rem; font-weight:700;
    text-transform:uppercase; letter-spacing:0.1em;
    margin-bottom:8px; padding-bottom:5px;
    border-bottom:2px solid {C['fire_light']}; display:inline-block;
}}

div[data-testid="stExpander"]:last-of-type {{
    position:fixed; left:24px; bottom:24px;
    width:760px; max-height:80vh; z-index:9999;
    background:{C['bg']}; border:1px solid {C['border']};
    border-top:3px solid {C['fire_orange']}; border-radius:10px;
    box-shadow:0 8px 32px rgba(44,26,14,0.2); overflow:hidden;
}}
div[data-testid="stExpander"]:last-of-type summary {{
    padding:14px 20px; font-weight:700; font-size:0.95rem;
    color:{C['text']}; background:{C['surface']}; border-radius:10px;
}}
div[data-testid="stExpander"]:last-of-type > details[open] > div {{
    padding:14px 20px 20px 20px; max-height:70vh; overflow-y:auto;
}}

.stButton > button {{
    border-radius:7px; border:1px solid {C['border']};
    background:{C['bg']}; color:{C['text']}; font-weight:600; font-size:0.85rem;
}}
.stButton > button:hover {{
    border-color:{C['fire_orange']}; color:{C['fire_orange']}; background:#fff8f0;
}}
</style>
""", unsafe_allow_html=True)

# ── Study condition ──────────────────────────────────────────────────────────
# Condition is set entirely by the URL query parameter, never by anything
# visible or interactive inside the app, so a participant can never see or
# flip it. This is read fresh from the URL on every rerun, not stored in
# session_state, so nothing that happens later in the session (uploading a
# file, moving the slider, asking the coach a question) can ever change or
# reset it.
#   ?g=a → control condition, no coach
#   ?g=b → treatment condition, coach enabled
# A missing or unrecognized value is treated as a hard error rather than
# silently defaulting to one condition, so a mistyped or missing link can
# never quietly reassign someone's condition.
GROUP_CODES = {"a": False, "b": True}

group_param = st.query_params.get("g")

if group_param not in GROUP_CODES:
    st.error(
        "This link is missing a valid session parameter and cannot be used. "
        "Please use the exact link provided for your session."
    )
    st.stop()

coach_unlocked = GROUP_CODES[group_param]


# ── File upload ────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload your simulation_data.jsonl", type=["jsonl"])
if uploaded_file is None:
    st.info("Upload a simulation_data.jsonl file to begin.")
    st.stop()

file_content = uploaded_file.getvalue().decode("utf-8")


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_all(file_content):
    rows = []
    for line in file_content.splitlines():
        line = line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except: continue

    zone_rows = [r for r in rows if r["sensorType"] == 0]
    zone_df   = pd.DataFrame(zone_rows)[["timestamp","location","value"]]
    timeline  = zone_df.pivot_table(
        index="timestamp", columns="location",
        values="value", aggfunc="last"
    ).reset_index().fillna(0)
    timeline  = timeline.sort_values("timestamp").reset_index(drop=True)

    KEY_MAP = {
        "Inside": "inside", "Exited": "exited", "Trapped": "trapped",
        "VulnerableStillInside": "vulnerable",
        "CriticalHealthStillInside": "critical_health",
    }
    summary_data = []
    for r in rows:
        if r.get("sensorId") != "Sys-Summary": continue
        d = {"timestamp": r["timestamp"]}
        for part in r.get("eventDetails","").split():
            k, _, v = part.partition(":")
            if k in KEY_MAP:
                try: d[KEY_MAP[k]] = int(v)
                except: pass
        summary_data.append(d)
    summary_df = pd.DataFrame(summary_data).sort_values("timestamp").reset_index(drop=True)

    smoke_rows = [r for r in rows if r.get("sensorType") == 1]
    if smoke_rows:
        s_df = pd.DataFrame(smoke_rows)[["timestamp","location","eventDetails"]]
        s_df["has_smoke"] = s_df["eventDetails"].str.strip() != "Clear"
        smoke_tl = s_df.pivot_table(
            index="timestamp", columns="location",
            values="has_smoke", aggfunc="max"
        ).reset_index().fillna(False)
        smoke_timeline = smoke_tl.sort_values("timestamp").reset_index(drop=True)
    else:
        smoke_timeline = pd.DataFrame()

    h_rows = [r for r in rows
              if r.get("sensorType") == 2
              and not r.get("hasExited", False)
              and r.get("health", 0) > 0]
    if h_rows:
        h_df = pd.DataFrame(h_rows)[["timestamp","health"]]
        health_tl = h_df.groupby("timestamp")["health"].mean().reset_index()
        health_tl.columns = ["timestamp","avg_health"]
        health_timeline = health_tl.sort_values("timestamp").reset_index(drop=True)
    else:
        health_timeline = pd.DataFrame()

    profiles = [r for r in rows if r.get("sensorType") == 5]
    age_counts = {}
    disability_counts = {}
    disabled_agent_ids = set()
    for p in profiles:
        age = p.get("ageBand", "Unknown")
        dis = p.get("disability", "None")
        age_counts[age] = age_counts.get(age, 0) + 1
        disability_counts[dis] = disability_counts.get(dis, 0) + 1
        if dis and dis not in ("None", ""):
            disabled_agent_ids.add(p.get("agentId"))
    events = []
    # Exit records (sensorType 2, hasExited=True) repeat every tick after
    # an agent exits, since their tracker keeps logging telemetry even
    # after leaving. Dedupe to one record per agent, and use exitTime (the
    # actual moment they exited) instead of the raw per-tick timestamp,
    # which keeps advancing long after the agent is already gone. Without
    # this, exit counts and anything built from exit_events silently
    # multiply per agent by however many ticks ran after their exit.
    exit_by_agent = {}
    for r in rows:
        if r.get("sensorType") == 2 and r.get("hasExited") is True:
            exit_by_agent[r.get("agentId")] = r
    exit_events = []
    for agent_id, r in exit_by_agent.items():
        exit_events.append({
            "agentId":   agent_id,
            "location":  r.get("location", ""),
            "ageBand":   r.get("ageBand", ""),
            "exit_time": r.get("exitTime", r.get("timestamp", 0)),
        })

    events = []
    for r in sorted(rows, key=lambda x: x.get("timestamp", 0)):
        st_ = r.get("sensorType")
        if st_ == 3 and r.get("sensorId") != "Sys-Summary":
            events.append({
                "timestamp": r["timestamp"],
                "text": r.get("eventDetails","")[:90],
                "warn": any(w in r.get("eventDetails","").lower()
                            for w in ("block","fire","trap","critical")),
            })
        if st_ == 1 and r.get("eventDetails","").strip() != "Clear":
            loc = r.get("location","")
            events.append({
                "timestamp": r["timestamp"],
                "text": f"Smoke detected at {loc}",
                "warn": True,
            })
    for e in exit_events:
        events.append({
            "timestamp": e["exit_time"],
            "text": f"{e['agentId']} ({e['ageBand']}) escaped via {e['location']}",
            "warn": False,
        })
    events = sorted(events, key=lambda x: x["timestamp"])

    total_agents = int(summary_df["inside"].iloc[0]) if len(summary_df) else 0
    runtime      = float(timeline["timestamp"].iloc[-1]) if len(timeline) else 0.0

    return (timeline, summary_df, smoke_timeline, health_timeline,
            events, exit_events, age_counts, disability_counts,
            total_agents, runtime, disabled_agent_ids)

@st.cache_data
def get_context_tmp_path(file_content):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
        tmp.write(file_content)
        return tmp.name


# ── Heatmap gradient ──────────────────────────────────────────────────────────
def _lerp(a, b, t): return int(a + (b - a) * t)

def heat_color(intensity, alpha=0.9):
    intensity = max(0.0, min(1.0, intensity))
    stops = [
        (0.00, (238, 240, 244)),
        (0.25, (232, 195,  81)),
        (0.50, (227, 137,  49)),
        (0.75, (171,  42,  24)),
        (1.00, ( 95,  15,  10)),
    ]
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]; p1, c1 = stops[i+1]
        if intensity <= p1:
            t = (intensity - p0) / (p1 - p0) if p1 > p0 else 0
            return (f"rgba({_lerp(c0[0],c1[0],t)},"
                    f"{_lerp(c0[1],c1[1],t)},"
                    f"{_lerp(c0[2],c1[2],t)},{alpha})")
    return f"rgba(95,15,10,{alpha})"


# ── Load ──────────────────────────────────────────────────────────────────────
timeline_df, summary_df, smoke_timeline, health_timeline, events, exit_events, age_counts, disability_counts, total_agents, runtime, disabled_agent_ids = load_all(file_content)
context_tmp_path = get_context_tmp_path(file_content)
total_frames = len(timeline_df)
max_occ      = max(
    (timeline_df[c].max() for c in BUILDING_LAYOUT if c in timeline_df.columns),
    default=1)
max_occ = max(max_occ, 1)


# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [("current_frame", 0), ("history", [])]:
    if k not in st.session_state:
        st.session_state[k] = v


# ── Frame values ──────────────────────────────────────────────────────────────
frame_idx    = st.session_state.current_frame
row          = timeline_df.iloc[frame_idx]
current_time = float(row["timestamp"])
context_pkg  = build_package(context_tmp_path, end=current_time)
zone_counts  = {z: int(row[z]) if z in row else 0 for z in BUILDING_LAYOUT}

cumulative_exits = {}
for e in [ev for ev in exit_events if ev["exit_time"] <= current_time]:
    loc = e.get("location", "")
    if loc in EXIT_ZONES:
        cumulative_exits[loc] = cumulative_exits.get(loc, 0) + 1
for loc in EXIT_ZONES:
    zone_counts[loc] = cumulative_exits.get(loc, 0)

disabled_exited_by_now = sum(
    1 for e in exit_events
    if e.get("agentId") in disabled_agent_ids and e["exit_time"] <= current_time
)
disabled_inside_now = len(disabled_agent_ids) - disabled_exited_by_now

busiest = max(zone_counts, key=zone_counts.get)

summary_at  = summary_df[summary_df["timestamp"] <= current_time]
if len(summary_at):
    s               = summary_at.iloc[-1]
    inside_now      = int(s.get("inside",  0))
    escaped_now     = int(s.get("exited",  0))
    trapped_now     = int(s.get("trapped", 0))
else:
    inside_now      = total_agents
    escaped_now     = 0
    trapped_now     = 0
    
if not health_timeline.empty:
    h_at = health_timeline[health_timeline["timestamp"] <= current_time]
    avg_health_now = round(h_at["avg_health"].iloc[-1], 1) if len(h_at) else 100.0
else:
    avg_health_now = 100.0

smoke_zones_now = set()
if not smoke_timeline.empty:
    sm_at = smoke_timeline[smoke_timeline["timestamp"] <= current_time]
    if len(sm_at):
        last_sm = sm_at.iloc[-1]
        for col in smoke_timeline.columns:
            if col == "timestamp": continue
            if last_sm.get(col, False):
                smoke_zones_now.add(col)

events_now = [e for e in events if e["timestamp"] <= current_time]


# ── Header ────────────────────────────────────────────────────────────────────
hl, hr = st.columns([3, 1])
with hl:
    st.markdown(
        '<div class="app-title">Evacuation Coach Dashboard</div>'
        '<div class="app-sub">Simulation analyst · single-run view</div>',
        unsafe_allow_html=True)
with hr:
    st.markdown(
        f'<div class="app-sub" style="text-align:right;padding-top:10px;">'
        f'Run: {uploaded_file.name}</div>',
        unsafe_allow_html=True)

st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)


# ── Timeline ──────────────────────────────────────────────────────────────────
st.markdown('<div class="sec-label">Simulation Timeline</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns([1, 10, 1])

with c1:
    if st.button("Reset", use_container_width=True, key="reset_btn"):
        st.session_state.current_frame = 0
        st.session_state["timeline_slider"] = 0
        st.rerun()

with c2:
    new_frame = st.slider(
        "Timeline", min_value=0,
        max_value=max(total_frames - 1, 1),
        value=st.session_state.current_frame,
        step=1, label_visibility="collapsed", key="timeline_slider",
    )
    if new_frame != st.session_state.current_frame:
        st.session_state.current_frame = new_frame
        st.rerun()

with c3:
    st.markdown(
        f'<div style="text-align:right;padding-top:8px;font-variant-numeric:tabular-nums;'
        f'color:{C["text"]};font-weight:700;font-size:1.05rem;">{current_time:.2f}s</div>',
        unsafe_allow_html=True)


# ── KPI row ───────────────────────────────────────────────────────────────────
st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

trapped_card  = "kpi-card-vuln" if trapped_now > 0 else "kpi-card-neutral"
disabled_card = "kpi-card-vuln" if disabled_inside_now > 0 else "kpi-card-neutral"
kpi_defs = [
    ("Total Agents",    f"{total_agents}",       "in this simulation",
     "", "kpi-badge-grey", "👥", "kpi-card-neutral",
     "Total number of agents who started inside the building."),
    ("Agents Escaped",  f"{escaped_now}",         f"of {total_agents} at {current_time:.1f}s",
     "kpi-good", "kpi-badge-orange", "🚪", "",
     "Agents who have exited through any exit, as of the current time."),
    ("Agents Trapped", f"{trapped_now}",    f"confirmed trapped at {current_time:.1f}s",
     "kpi-warn" if trapped_now > 0 else "", "kpi-badge-yellow", "⚠️", trapped_card,
     "Agents confirmed unable to escape, for example blocked by fire, as of the current time. Does not include agents still evacuating who simply have not exited yet."),
    ("Disabled Inside", f"{disabled_inside_now}", f"of {len(disabled_agent_ids)} at {current_time:.1f}s",
     "kpi-warn" if disabled_inside_now > 0 else "", "kpi-badge-yellow", "♿", disabled_card,
     "Agents with a disability (such as a mobility aid) who are still inside and have not exited, as of the current time."),
    ("Busiest Zone",    f"{busiest}",             f"{zone_counts[busiest]} agents at {current_time:.1f}s",
     "", "kpi-badge-grey", "📍", "kpi-card-neutral",
     "The zone with the highest agent count right now."),
    ("Runtime",         f"{runtime:.1f}s",        f"{total_frames} ticks captured",
     "", "kpi-badge-grey", "⏱", "kpi-card-neutral",
     "How long the simulation has been running, in seconds."),
]

for col, (label, value, sub, val_cls, badge_cls, icon, card_cls, tooltip) in zip(
    st.columns(6), kpi_defs
):
    col.markdown(f"""
    <div class="kpi-card {card_cls}" title="{tooltip}">
        <div class="kpi-top">
            <div class="kpi-label">{label}</div>
            <div class="kpi-badge {badge_cls}">{icon}</div>
        </div>
        <div class="kpi-value {val_cls}">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)



# ── Main area ─────────────────────────────────────────────────────────────────
LAYOUT_H = 480
BAR_H    = 300
AGE_H    = 220
DEMO_H   = 230

left_col, right_col = st.columns([1.4, 1])

with left_col:
    st.markdown('<div class="sec-label">Building Layout</div>', unsafe_allow_html=True)
    fig = go.Figure()
    hover_x, hover_y, hover_text = [], [], []
    for zone, pos in BUILDING_LAYOUT.items():
        occ       = zone_counts.get(zone, 0)
        intensity = min(occ / max_occ, 1.0)
        fill      = heat_color(intensity)
        txt_col   = "#ffffff" if intensity > 0.45 else C["text"]
        fig.add_shape(
            type="rect",
            x0=pos["x"], y0=pos["y"],
            x1=pos["x"]+pos["width"], y1=pos["y"]+pos["height"],
            fillcolor=fill, line=dict(color="#c8d0dc", width=1.5), layer="below",
        )
        if zone in smoke_zones_now:
            fig.add_shape(
                type="rect",
                x0=pos["x"], y0=pos["y"],
                x1=pos["x"]+pos["width"], y1=pos["y"]+pos["height"],
                fillcolor="rgba(90,90,110,0.32)",
                line=dict(color="rgba(70,70,90,0.55)", width=1.5, dash="dot"),
                layer="above",
            )
        label_text = f"<b>{zone}</b><br>{occ}"
        if zone in smoke_zones_now:
            label_text = f"<b>{zone}</b><br>{occ} 💨"
        fig.add_annotation(
            x=pos["x"]+pos["width"]/2, y=pos["y"]+pos["height"]/2,
            text=label_text, showarrow=False,
            font=dict(size=11, color=txt_col, family="Inter, sans-serif"),
        )

        # Center point for this zone, used below to attach hover data.
        # Shapes drawn above have no hover support on their own, so an
        # invisible marker at the zone's center is what actually makes
        # hovering show live info instead of just a static label.
        smoke_status = "Smoke present" if zone in smoke_zones_now else "Clear, no smoke detected"
        hover_x.append(pos["x"] + pos["width"] / 2)
        hover_y.append(pos["y"] + pos["height"] / 2)
        hover_text.append(f"<b>{zone}</b><br>Agents inside: {occ}<br>{smoke_status}")

    # Invisible hover layer, one point per zone, sized to roughly cover
    # each zone's area so hovering anywhere over a zone shows its data.
    fig.add_trace(go.Scatter(
        x=hover_x, y=hover_y, mode="markers",
        marker=dict(size=34, opacity=0),
        hovertext=hover_text, hoverinfo="text",
        showlegend=False,
    ))

    fig.update_layout(
        xaxis=dict(range=[-0.3, 10.3], showgrid=False, showticklabels=False,
                   zeroline=False, fixedrange=True),
        yaxis=dict(range=[-0.1, 7.9], showgrid=False, showticklabels=False,
                   zeroline=False, fixedrange=True),
        height=LAYOUT_H, autosize=True,
        paper_bgcolor=C["bg"], plot_bgcolor=C["surface"],
        hovermode="closest", margin=dict(l=24, r=24, t=24, b=24),
        hoverlabel=dict(
            bgcolor=C["bg"], bordercolor=C["fire_orange"],
            font=dict(color=C["text"], size=12, family="Inter, sans-serif"),
        ),
    )
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False}, key="heatmap")

with right_col:
    col_a, col_b = st.columns([0.8, 1.5])
    
    with col_a:
        st.markdown('<div class="sec-label">Recent Activity</div>', unsafe_allow_html=True)
        display_events = list(reversed(events_now[-7:])) if events_now else []
        while len(display_events) < 7:
            display_events.append(None)

        rows_html = ""
        for e in display_events:
            if e is None:
                rows_html += (
                    f"<tr>"
                    f"<td style='padding:6px 8px;font-size:0.75rem;white-space:nowrap;"
                    f"border-bottom:1px solid {C['tbl_border']};color:{C['muted']};'>--</td>"
                    f"<td style='padding:6px 8px;font-size:0.75rem;white-space:nowrap;"
                    f"border-bottom:1px solid {C['tbl_border']};color:{C['muted']};'>No event</td>"
                    f"</tr>"
                )
            else:
                ts      = f"{e['timestamp']:.1f}s"
                txt_css = f"color:{C['fire_red']};font-weight:600;" if e["warn"] else f"color:{C['text']};"
                rows_html += (
                    f"<tr>"
                    f"<td style='padding:6px 8px;color:{C['fire_orange']};font-weight:700;"
                    f"white-space:nowrap;font-size:0.75rem;"
                    f"border-bottom:1px solid {C['tbl_border']};'>{ts}</td>"
                    f"<td style='padding:6px 8px;{txt_css}font-size:0.75rem;white-space:nowrap;"
                    f"border-bottom:1px solid {C['tbl_border']};'>{e['text']}</td>"
                    f"</tr>"
                )
        st.markdown(
            f"<div style='width:100%;overflow-x:auto;border:1px solid {C['tbl_border']};"
            f"border-radius:8px;'>"
            f"<table style='width:max-content;min-width:100%;border-collapse:collapse;'>"
            f"<thead><tr>"
            f"<th style='padding:7px 8px;background:{C['tbl_head']};color:{C['soft']};"
            f"font-size:0.7rem;text-align:left;font-weight:700;white-space:nowrap;'>TIME</th>"
            f"<th style='padding:7px 8px;background:{C['tbl_head']};color:{C['soft']};"
            f"font-size:0.7rem;text-align:left;font-weight:700;white-space:nowrap;'>EVENT</th>"
            f"</tr></thead>"
            f"<tbody style='background:{C['tbl_body']};'>{rows_html}</tbody>"
            f"</table>"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-label">Agent Breakdown</div>', unsafe_allow_html=True)
        if age_counts:
            AGE_COLORS = ["#ecb02b", "#e38931", "#ab2a18", "#94a3b8"]
            ages   = list(age_counts.keys())
            counts = list(age_counts.values())
            fig_age = go.Figure(go.Pie(
                labels=ages, values=counts, hole=0.5,
                marker=dict(colors=AGE_COLORS[:len(ages)], line=dict(color=C["bg"], width=2)),
                textinfo="value", textfont=dict(size=11, color="#ffffff"),
                hovertemplate="%{label}: %{value}<extra></extra>",
            ))
            fig_age.update_layout(
                height=AGE_H, autosize=True,
                paper_bgcolor=C["bg"], plot_bgcolor=C["bg"],
                margin=dict(l=10, r=10, t=10, b=40),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2,
                           xanchor="center", x=0.5, font=dict(size=10, color=C["text"])),
            )
            st.plotly_chart(fig_age, use_container_width=True,
                            config={"displayModeBar": False}, key="age_chart")

    with col_b:
        st.markdown('<div class="sec-label">Occupancy by Zone</div>', unsafe_allow_html=True)
        df_bar = pd.DataFrame({
            "Zone":   list(zone_counts.keys()),
            "Agents": list(zone_counts.values()),
        }).sort_values("Agents", ascending=True)
        fig_bar = go.Figure(go.Bar(
            x=df_bar["Agents"], y=df_bar["Zone"], orientation="h",
            marker=dict(
                color=[heat_color(min(v/max_occ,1.0)) for v in df_bar["Agents"]],
                line=dict(color=C["border"], width=1),
            ),
            text=df_bar["Agents"], textposition="outside",
            textfont=dict(size=13, color=C["text"]),
        ))
        fig_bar.update_layout(
            height=BAR_H, autosize=True,
            paper_bgcolor=C["bg"], plot_bgcolor=C["bg"],
            margin=dict(l=8, r=32, t=8, b=30),
            xaxis=dict(gridcolor=C["border"], color=C["soft"],
                       title=dict(text="Agents", font=dict(size=11, color=C["soft"])),
                       tickfont=dict(size=11),
                       fixedrange=True),
            yaxis=dict(color=C["text"], tickfont=dict(size=13), fixedrange=True),
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True,
                        config={"displayModeBar": False}, key="bar_chart")

        st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-label">Demographic Escape Progression</div>', unsafe_allow_html=True)

        AGE_COLORS_MAP = {"Young": "#ecb02b", "Adult": "#ab2a18", "Elderly": "#e38931"}

        fig_demo = go.Figure()
        for age, total in age_counts.items():
            exit_times = sorted(
                e["exit_time"] for e in exit_events if e.get("ageBand") == age
            )
            x_vals = [0.0] + exit_times
            y_vals = [total] + [total - (i + 1) for i in range(len(exit_times))]
            if runtime > x_vals[-1]:
                x_vals.append(runtime)
                y_vals.append(y_vals[-1])
            fig_demo.add_trace(go.Scatter(
                x=x_vals, y=y_vals, mode="lines+markers", name=age,
                line=dict(width=2.5, color=AGE_COLORS_MAP.get(age, C["soft"])),
                marker=dict(size=6, color=AGE_COLORS_MAP.get(age, C["soft"])),
            ))

        fig_demo.update_layout(
            height=DEMO_H, autosize=True,
            paper_bgcolor=C["bg"], plot_bgcolor=C["bg"],
            margin=dict(l=40, r=20, t=10, b=40),
            xaxis=dict(title=dict(text="Time (seconds)", font=dict(size=11, color=C["soft"])),
                       gridcolor=C["border"], color=C["soft"], tickfont=dict(size=10),
                       fixedrange=True),
            yaxis=dict(title=dict(text="Agents still inside", font=dict(size=11, color=C["soft"])),
                       gridcolor=C["border"], color=C["soft"], tickfont=dict(size=10),
                       fixedrange=True),
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                       xanchor="right", x=1, font=dict(size=10, color=C["text"])),
        )
        st.plotly_chart(fig_demo, use_container_width=True,
                        config={"displayModeBar": False}, key="demo_chart")

# ── Coach panel ───────────────────────────────────────────────────────────────
import re

WHATIF_WORDS = ["what if", "suppose", "instead of", "were to", "would happen if"]
TOTAL_WORDS  = ["total", "overall", "altogether", "by the end", "at the end",
    "in the end", "final", "entire run", "whole run", "in total",
    "demographic", "age group", "escaped first", "escaped last",
    "which group"]

def is_what_if(q):
    ql = q.lower()
    return any(w in ql for w in WHATIF_WORDS)

def is_total_question(q):
    ql = q.lower()
    return any(w in ql for w in TOTAL_WORDS)

def parse_time_from_question(q):
    """Pulls a time like '3 seconds', '20s', 'at 15.5 sec' out of a typed
    question. Returns it directly as the raw simulation time, or None if
    no time reference was found."""
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s\b)', q.lower())
    if m:
        return float(m.group(1))
    return None

def is_off_topic(q):
    if parse_time_from_question(q) is not None:
        return False
    return not any(w in q.lower() for w in SIM_WORDS)

def send(label, prompt):
    st.session_state.history.append(("user", label))
    with st.spinner("Thinking..."):
        reply = ask_coach(prompt)
    st.session_state.history.append(("coach", reply))

if coach_unlocked:
    with st.expander("Ask the Coach", expanded=False):
        preset_as_of = f"This data reflects the current dashboard view, {current_time:.1f} seconds into the run."
        for i, (label, template) in enumerate(MENU.items()):
            if st.button(label, use_container_width=True, key=f"coach_pre_{i}"):
                send(label, build_prompt(template, context_pkg, as_of=preset_as_of))
                st.rerun()

        for who, text in st.session_state.history:
            with st.chat_message("user" if who == "user" else "assistant"):
                st.write(text)

        typed = st.chat_input("Ask anything about this run", key="coach_input")
    if typed:
        # No Python-side keyword filter here anymore. A fixed word list
        # can never cover every valid phrasing (it just missed
        # "congestion" and "demographic" in testing), and it has no way
        # to understand synonyms at all. The model itself, guided by
        # GUARD in prompts.py, correctly declines genuinely unrelated
        # questions in its own words, so relevance judgment is left
        # entirely to it instead of a brittle pre-check.
        asked_time = parse_time_from_question(typed)
        if asked_time is not None:
            # A specific time was named, build context for exactly
            # that moment.
            query_context = build_package(context_tmp_path, end=asked_time)
            as_of_note = f"This data reflects the simulation as of {asked_time:.1f} seconds into the run."
        elif is_total_question(typed):
            # "in total" / "at the end" style questions mean the
            # complete, final outcome of the whole run, not wherever
            # the slider currently sits.
            query_context = build_package(context_tmp_path)
            as_of_note = "This data covers the complete run from start to finish, this is the final outcome."
        else:
            # No time and no "total" wording, answer about wherever
            # the slider is right now, but say so explicitly.
            query_context = context_pkg
            as_of_note = f"This data reflects the current dashboard view, {current_time:.1f} seconds into the run, not the final outcome of the run."

        if is_what_if(typed):
            send(typed, build_prompt(WHAT_IF, query_context, typed, as_of_note))
        else:
            send(typed, build_prompt(DIRECT_QUESTION, query_context, typed, as_of_note))
        st.rerun()

        if st.session_state.history:
            if st.button("Clear", key="clear_chat"):
                st.session_state.history = []
                st.rerun()
