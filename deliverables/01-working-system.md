# Working System

## Live URLs

- Frontend (claim submission and decision review): `https://health-insurance-claims-processing.vercel.app/`
- Backend API: `https://plum-claims-api-sut5.onrender.com`
- API health check: `https://plum-claims-api-sut5.onrender.com/health`

The frontend is hosted on Vercel and the backend on Render. The frontend talks to the
backend through Vercel rewrites, so the browser only ever calls the Vercel domain and
the requests get forwarded to Render behind the scenes. That keeps things same-origin
and avoids any CORS setup.

One thing worth knowing before you click around: the backend runs on Render's free
tier, which puts the service to sleep after about 15 minutes of no traffic. The first
request after it has been idle takes 30 to 50 seconds while it wakes up and reloads the
policy file. If you are about to demo or review, open the health check URL once first
to warm it up, then the app will feel snappy.

## Source

The code is on GitHub with one commit per logical change. The commit history follows a
conventional style (feat, fix, test, docs, chore) so it reads as a sequence of real
steps rather than one big dump.

## Running it locally

You need Python 3.12, Node 18 or newer, and a Gemini API key. The key is free from
Google AI Studio.

A note on Python: stick to 3.12. Newer versions like 3.13 and 3.14 don't have prebuilt
`pydantic-core` wheels yet, so the install will try to compile from source and usually
fails. 3.12 just works.

### Backend

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# open .env and set GEMINI_API_KEY=AIza...

uvicorn app.api.routes:app --reload --port 8000
```

Once it is up, the interactive API docs are at `http://localhost:8000/docs`.

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The UI runs at `http://localhost:5173`. In dev mode Vite proxies `/claims` and
`/health` to the backend on port 8000, so you don't need to configure anything.

### Tests

```bash
pytest
```

That runs the full suite (132 tests) with no live API calls, so it is fast and doesn't
cost anything. Every LLM call is mocked.

### Eval harness

```bash
python eval/run_eval.py
```

This runs all 12 cases from `test_cases.json` end to end, prints a summary, and writes
the full report to `eval/eval_report.md`.

## What the two screens do

The submission screen takes member details, the claim category, the treatment date, the
claimed amount, an optional hospital name, and one or more uploaded documents. The
review screen shows the decision (approved, partial, rejected, or manual review), the
approved amount, the confidence score, the reason, and the full trace rendered as a
readable timeline rather than a raw JSON blob.
