# Evacuation Coach Dashboard

Streamlit dashboard for the Immersive Digital Twin Lite for Evacuation Training
research co-op. Reads simulation logs exported from the Unity evacuation sim and
gives users an interactive AI coach to explore what happened during a run.

## Core Research Question

Does an LLM coach improve human decision-making in high-stress virtual evacuation
scenarios, compared to reviewing the same data without a coach?

## Features

- **Simulation timeline** — scrub through the run tick by tick, all KPIs and
  charts update to reflect that point in time
- **KPI row** — total agents, agents escaped, agents trapped, disabled inside,
  busiest zone, runtime
- **Building layout** — floor plan view showing live occupancy per room, with
  smoke status. Rooms with no logged reading yet show `—` rather than a
  misleading `0`
- **Occupancy by zone** — bar chart of top zones by agent count
- **Recent activity** — event log (alarms, exits, blocked exits, obstacles)
- **Agent breakdown** — donut chart by age group
- **Demographic escape progression** — line chart of agents remaining inside
  per age group over time
- **AI coach** — chat panel backed by Gemini, grounded in the actual run data.
  Preset questions (Who Failed, Bottlenecks, Recommendations) plus free-typed
  questions and what-if scenarios
- **Time-aware querying** — the coach detects whether a question is asking
  about a specific moment, the current dashboard view, or the whole run
  ("in total," "at the end," demographic questions, "blocked," "obstacle,"
  etc. all trigger full-run context regardless of where the timeline slider is)

## Tech Stack

- **Simulation:** Unity (C#) — 3D floor plan, A* pathfinding + NavMesh, fire/smoke
  hazard model, virtual sensors (zone occupancy, smoke detectors, obstacles)
- **Dashboard:** Streamlit (Python)
- **AI Coach:** Google Gemini API, `gemini-3.5-flash-lite`, called directly via
  the REST endpoint (`generativelanguage.googleapis.com`) using `requests`,
  no SDK dependency

## File Structure

| File | Purpose |
|---|---|
| `app.py` | Main Streamlit app — layout, charts, KPIs, coach panel |
| `context_builder.py` | Builds the data + environment context package sent to the AI |
| `prompts.py` | System prompt and question templates for the coach |
| `llm_connection.py` | Handles the Gemini API call |
| `requirements.txt` | `streamlit`, `pandas`, `plotly`, `requests` |

Unity-side (separate repo/folder):

| File | Purpose |
|---|---|
| `SimulationLogger.cs` | Runs the tick loop, writes every sensor reading to the JSONL buffer |
| `AgentDataTracker.cs` | Per-agent state, exit/trap detection and logging |
| `ZoneOccupancy.cs` | Per-room agent counting |
| `ExitBlocker.cs` | Manual researcher intervention to block an exit mid-run |

## Setup & Running Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Set your Gemini API key as the environment variable `GEMINI_API_KEY`
(`llm_connection.py` checks Streamlit secrets first, then falls back to the
local environment automatically, so the same code path works locally and
deployed).

## Deploying

Push to GitHub, deploy via [share.streamlit.io](https://share.streamlit.io), add
`GEMINI_API_KEY` in the app's Secrets settings. Dashboard code changes for the
deployed version must be made directly on GitHub, not tested only locally, since
Streamlit Cloud pulls from the repo.

## AI Coach Design Notes

- The system prompt (`prompts.py`) is split into `CORE_ROLE` (shared by every
  template) and `GUARD` (refusal/off-topic handling). `GUARD` is only attached
  to `DIRECT_QUESTION` and `WHAT_IF`, the two templates that handle real
  free-typed text. The three preset buttons (Who Failed, Bottlenecks,
  Recommendations) use `CORE_ROLE` alone, since giving a fixed button an
  explicit refusal option made the model occasionally self-refuse under any
  uncertainty, even though a preset can never actually be off-topic.
- `context_builder.py` precomputes several fields so the model doesn't have to
  derive them from raw records: `exited`/`not_escaped`, `avg_agent_health_now`,
  `zone_occupancy_now`/`busiest_zone_now`, `smoke_zones_active_now`,
  `demographic_escape_progression`, `disability_escape_progression`,
  `congestion_over_time`, `age_breakdown`/`disability_breakdown`,
  `disabled_inside_now`, `blocked_exits`. The prompt explicitly tells the model
  to use these directly rather than recount from raw lists.

## Study Condition

The with/without-coach condition is set via a URL query parameter, never a
visible toggle, so participants can't see or flip it:

- `?g=a` — control (no AI coach)
- `?g=b` — treatment (AI coach enabled)

A missing or invalid `?g=` value throws an explicit error rather than silently
defaulting to a condition.

## Uploading a Run

Upload the `.jsonl` file exported from a Unity run. The dashboard resets the
timeline slider automatically when a new file is uploaded.

## Known Limitations

- The AI coach runs on Gemini's free tier and can occasionally hallucinate,
  particularly when composing a sentence that names a specific agent (blending
  details from two different records). Aggregate/field-level answers (totals,
  KPI-matching numbers, first/last to escape) have been reliable across
  extensive testing. Spot-check any single-agent narrative claim against the
  raw JSONL; trust aggregate numbers by default.
- Ground truth for any data question should always be verified directly against
  the `.jsonl` file with a script, not assumed from a screenshot or the coach's
  own answer.
