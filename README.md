# FRM Forge

Reactive FRM operations console built with Python, NiceGUI, and SQLite.

This app is meant to be hosted separately from the FRM web root. The browser talks only to this app. The app talks to the FRM HTTP API on the server side, stores operator settings in SQLite, and runs schedules or threshold-triggered write actions from the backend.

## What It Does

- Live overview, factory, power, and map views backed by the FRM API.
- Backend-managed FRM reads and write actions for `setEnabled` and `setSwitches`.
- SQLite persistence for:
  - connection settings
  - schedules and threshold rules
  - automation history
  - custom dashboards and pinned widgets
  - custom name mappings from FRM object IDs to operator-friendly labels
- Imported rule feed support from an external JSON endpoint.
- Container-friendly deployment for hosting anywhere Docker can reach the FRM API.

## Stack

- Python 3.11+
- [NiceGUI](https://nicegui.io/)
- SQLAlchemy + SQLite
- httpx
- Docker / Docker Compose

## Project Layout

- `frm_forge/app.py`
- `frm_forge/automation.py`
- `frm_forge/frm_client.py`
- `frm_forge/models.py`
- `frm_forge/repository.py`
- `frm_forge/snapshot_service.py`
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`

## How It Connects To FRM

FRM Forge connects to the FRM HTTP API from the backend, not from the browser. That solves the cross-origin problem you hit with a static frontend.

Important detail: if FRM Forge runs in Docker and FRM runs on the same Windows host machine, `localhost` inside the container will point to the container, not to Satisfactory. Use `http://host.docker.internal:8080` or the server's LAN IP instead.

FRM docs say the web server runs on the FRM HTTP port, defaults to `8080`, and write calls require the token from `Configs/FicsitRemoteMonitoring/WebServer.cfg`.

## Configuration

Environment variables are only the bootstrap values. After first launch, operators can update the FRM base URL, token, default schedule timezone, and imported-rule feed URL from the Settings tab, and those values are persisted in SQLite.

### Environment Variables

- `FRM_FORGE_HOST`: bind host for the web app. Default `0.0.0.0`.
- `FRM_FORGE_PORT`: web UI port. Default `8088`.
- `FRM_FORGE_DB_URL`: SQLAlchemy database URL. Default `sqlite:///data/frm_forge.db`.
- `FRM_FORGE_BOOTSTRAP_FRM_BASE_URL`: initial FRM API base URL.
- `FRM_FORGE_BOOTSTRAP_FRM_TOKEN`: initial FRM API token.
- `FRM_FORGE_BOOTSTRAP_DEFAULT_SCHEDULE_TIMEZONE`: initial timezone for schedules, for example `America/New_York`.
- `FRM_FORGE_BOOTSTRAP_REFRESH_SECONDS`: initial FRM polling interval.
- `FRM_FORGE_AUTOMATION_INTERVAL_SECONDS`: how often automation rules are evaluated.
- `TZ`: container local timezone used when rules are set to `local`.

### Schedule Timezones

Schedules are stored per rule. Use an explicit IANA timezone such as `America/New_York` unless you intentionally want rules to follow the container's `TZ` setting.

## Running With Docker

1. Create a `.env` file from `.env.example`.
2. Set `FRM_FORGE_BOOTSTRAP_FRM_BASE_URL` to the FRM server your container can reach.
3. Start the stack:

```bash
docker compose up --build -d
```

4. Open [http://localhost:8088](http://localhost:8088).
5. Use the Settings tab to adjust the FRM URL, token, timezone, or imported rule feed if needed.

The SQLite file is stored under `./data/frm_forge.db` and is mounted into the container by `docker-compose.yml`.

## GitHub Build And Unraid Template

The GitHub Actions workflow in `.github/workflows/container.yml` does three things:

- builds the container on pull requests
- publishes multi-arch images to `ghcr.io/<owner>/<repo>` on pushes to `master` and on version tags
- renders `unraid/frm-forge.xml.tmpl` into a concrete unRAID XML file based on the active GitHub repository slug

Every workflow run uploads the rendered unRAID XML as an artifact named `unraid-template`. Tag pushes also attach that XML to the GitHub release for the tag.

The template source for unRAID lives in `unraid/frm-forge.xml.tmpl` and includes the port, `/app/data` path mapping, FRM bootstrap URL/token, database URL, and timezone variables needed to start the container cleanly on Unraid.

## Running Without Docker

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python -m frm_forge.app
```

## FRM Write Support

The UI supports these documented FRM write endpoints:

- `setEnabled`
- `setSwitches`

That means the app can:

- enable or disable existing factory buildables
- turn existing switches on or off
- rename switches
- update switch priority

It does not create new in-game switches because the FRM write docs describe updating switches, not creating them.

## Automation Rules

Two local rule types are supported:

- schedule rules
- threshold rules

Schedule rules can target switches or factory actors and fire on selected weekdays at a configured `HH:MM` time. Threshold rules evaluate FRM snapshot data such as power margin, battery percent, paused machine count, utilization, or item production values.

Imported rules can be synced from an external JSON array. Imported rules replace the previous imported set and are stored with source `imported`.

### Example Imported Schedule Rule

```json
[
  {
    "name": "Weeknight backup grid",
    "type": "schedule",
    "enabled": true,
    "targetType": "switch",
    "targetId": "Build_PriorityPowerSwitch_C_2147423102",
    "action": {
      "status": true
    },
    "schedule": {
      "days": [1, 2, 3, 4, 5],
      "time": "18:00",
      "timezone": "America/New_York"
    },
    "cooldownMinutes": 5
  }
]
```

### Example Imported Threshold Rule

```json
[
  {
    "name": "Start backup when margin is low",
    "type": "threshold",
    "enabled": true,
    "metric": "power.margin.min",
    "operator": "<",
    "threshold": 400,
    "targetType": "switch",
    "targetId": "Build_PriorityPowerSwitch_C_2147423102",
    "action": {
      "status": true
    }
  }
]
```

## Current Limitations

- FRM snapshot history is rolling in-memory history for charts, not long-term telemetry storage.
- There is no schema migration tool yet; this is currently table-create-on-start.
- The backend currently polls FRM over HTTP. Websocket consumption is not wired up yet.

## FRM References

- [FRM API overview](https://docs.ficsit.app/ficsitremotemonitoring/latest/json/json.html)
- [FRM authentication](https://docs.ficsit.app/ficsitremotemonitoring/latest/json/authentication.html)
- [FRM setEnabled](https://docs.ficsit.app/ficsitremotemonitoring/latest/json/Write/setEnabled.html)
- [FRM setSwitches](https://docs.ficsit.app/ficsitremotemonitoring/latest/json/Write/setSwitches.html)
- [FRM web server](https://docs.ficsit.app/ficsitremotemonitoring/latest/webserver.html)
