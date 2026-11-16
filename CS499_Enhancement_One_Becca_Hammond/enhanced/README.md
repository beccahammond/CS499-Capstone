# Grazioso Salvare Animal Rescue Dashboard

**CS 499 Enhancement One: Software Design and Engineering**
Becca Hammond, November 2026

This dashboard helps Grazioso Salvare find shelter dogs that are good candidates for search-and-rescue training. It reads Austin Animal Center records from MongoDB and lets staff filter by rescue type (water, mountain or wilderness, disaster or tracking), with a data table, a breed chart and a map of the selected animal.

I originally built it in CS 340 as a Jupyter notebook. For CS 499, I rebuilt it as a standalone Python web app with a modular structure, environment-based settings, real error handling and automated tests.

## Project structure

```
app.py                         Entry point: loads settings, connects, starts the server
grazioso/
    config.py                  Loads settings from environment variables or .env
    exceptions.py              Custom errors used across the app
    layout.py                  Dash page layout (view)
    callbacks.py               Dash callbacks (controller)
    data/animal_shelter.py     CRUD module for MongoDB (model)
    services/rescue_filters.py Rescue type criteria and queries
assets/                        Logo, served by Dash
tests/                         pytest tests (use mongomock, no database needed)
.github/workflows/tests.yml    Runs the tests on every push
```

## Setup

You need Python 3.12 or newer and a MongoDB server with the Austin Animal Center data loaded into the `aac` database's `animals` collection.

1. Install the packages:
   ```
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in at least `DB_USER` and `DB_PASSWORD`. `.env` is in `.gitignore`, so the password stays out of GitHub.
3. Start the dashboard:
   ```
   python app.py
   ```
4. Open http://127.0.0.1:8050 in a browser.

If a required setting is missing, the app stops and says which one. If MongoDB can't be reached, the page shows a "Database unavailable" message instead of hanging.

## Settings

| Variable | Default | Notes |
|---|---|---|
| `DB_USER` | none | Required |
| `DB_PASSWORD` | none | Required |
| `DB_HOST` | `localhost` | |
| `DB_PORT` | `27017` | |
| `DB_NAME` | `aac` | |
| `DB_COLLECTION` | `animals` | |
| `DB_AUTH_SOURCE` | `admin` | Database the user was created in |
| `DB_TIMEOUT_MS` | `5000` | How long to wait for MongoDB before giving up |
| `APP_HOST` | `127.0.0.1` | |
| `APP_PORT` | `8050` | |
| `APP_DEBUG` | `false` | |
| `LOG_LEVEL` | `INFO` | |

## Running the tests

```
python -m pytest -v
```

The tests use mongomock in place of a real database, so they run anywhere without a password. GitHub Actions runs the same tests on every push.

## What changed from the CS 340 version

| Code review finding | Change |
|---|---|
| Database password hard-coded in the notebook | Loaded from environment variables; `.env.example` and `.gitignore` added |
| Credentials built into the connection string | Passed to `MongoClient` as arguments |
| No connection timeout | Configurable timeout and a ping at startup |
| CRUD methods hid errors by returning `False`, `[]` or `0` | Errors are logged and raised as `DatabaseError` |
| Everything in one notebook cell; needed `jupyter_dash` | Split into model, view, controller and service modules; runs with `python app.py` |
| Rescue criteria hard-coded in an if/elif chain | Named constants in `rescue_filters.py` |
| Unknown filter values returned the whole collection | Raise `UnknownRescueTypeError` and show a message |
| `read()` didn't support a projection, as its design required | `read(query, projection)`; `_id` left out by the database instead of dropped twice in pandas |
| Logo opened without checking it existed, and never closed | Served from `assets/`, with a check and a warning if missing |
| Unused imports, debug code, outdated comments, typos | Removed or rewritten |
| `print()` for errors | `logging` throughout |
| Chart title said "Preferred Breeds" for any results | "Top 10 Breeds in Current Results" |
| No automated tests | 61 pytest tests and a GitHub Actions workflow |

## Coming in later enhancements

- **Enhancement Two (algorithms and data structures):** rescue suitability ranking, server-side pagination and caching.
- **Enhancement Three (databases):** indexes matched to the dashboard's queries, aggregation for the chart, schema validation, least-privilege users and stored rescue profiles.
