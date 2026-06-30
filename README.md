# Compass

Compass is a multi-agent system for helping students discover, evaluate, save, and manage scholarships, internships, fellowships, research openings, and related application workflows.

## Required API Keys

Add these to `.env`:

```bash
GROQ_API_KEY=
TAVILY_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_ANON_KEY=
EMAIL_ENABLED=true
EMAIL_PROVIDER=resend
EMAIL_PROVIDER_API_KEY=
EMAIL_FROM=
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
SEARCH_PROVIDER=tavily
DYNAMIC_SCRAPING_ENABLED=false
```

Notes:

- `GROQ_API_KEY`: required at API startup and used by the main agents.
- `MISTRAL_API_KEY`: optional. Used for poster image extraction, embeddings, and Mistral-backed opportunity extraction when enabled.
- `TAVILY_API_KEY`: web search.
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`: database, auth, storage, RLS-backed user data.
- `EMAIL_PROVIDER=resend`, `EMAIL_PROVIDER_API_KEY`, `EMAIL_FROM`, `EMAIL_ENABLED`: Resend reminder sender. `EMAIL_FROM` must be a sender address or domain accepted by your Resend account.
- `TESSERACT_CMD`: optional OCR path. Set it if Windows cannot find `tesseract.exe` in PATH.
- `DYNAMIC_SCRAPING_ENABLED`: keep `false` for faster, more reliable searches. Set `true` only if you need Playwright-rendered pages and have installed Chromium with `python -m playwright install chromium`.
- `SEARCH_JOB_TIMEOUT_SECONDS`, `SEARCH_PLANNING_TIMEOUT_SECONDS`, `SEARCH_EXTRACTION_TIMEOUT_SECONDS`: increase these if searches need more time to finish on slower networks or larger result sets.

## Implemented

- Phase 1: FastAPI backend, config, typed graph state, intent router, profile agent, date-aware search planner.
- Phase 2: Tavily search integration, source policy gate, policy-gated scraper, PDF parser, OCR tool, opportunity extraction agent, Supabase repository boundary.
- Phase 3: source verification, eligibility with deadline filter, deduplication/merge, prioritization.
- Phase 4: save opportunity, tracker updates, deadline planning, grounded document draft endpoint, reminder formatting job.
- Phase 5: poster uploads, CV/document uploads, Supabase Storage integration, and optional Mistral vision extraction for poster images.
- Phase 6: golden-set extraction eval runner with optional Supabase persistence.
- Phase 7: React frontend for profile, search, opportunities, tracker, documents, uploads, and notification preferences.

Users create and sign in to **Compass accounts** in the React UI. Supabase Auth is the hidden identity provider behind that screen.

Private API endpoints require a user access token in:

```text
Authorization: Bearer <access_token>
```

## Run

```bash
cd F:\Compass-Opportunity-Workspace-main
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload
```

## Test

```bash
pytest
```

## Evaluation

```bash
python -m eval.run_eval --golden-set eval/golden_set/sample_opportunities.json --output eval/latest_eval_report.json --resume
```

To save aggregate eval metrics to Supabase:

```bash
python -m eval.run_eval --golden-set eval/golden_set/sample_opportunities.json --output eval/latest_eval_report.json --resume --save
```

If you hit model-provider rate limits, wait and rerun the same command. Completed cases are reused from the output file.

## Supabase

Apply:

```text
supabase/migrations/001_initial_schema.sql
supabase/migrations/002_jobs_observability.sql
supabase/migrations/003_short_opportunity_ids.sql
supabase/migrations/004_compass_user_ids.sql
supabase/migrations/005_security_workflow_hardening.sql
supabase/migrations/006_uuid_opportunity_primary_keys.sql
supabase/migrations/007_document_review_workflow.sql
supabase/migrations/008_search_job_resilience.sql
supabase/migrations/009_document_upload_attachment.sql
supabase/migrations/010_normalized_opportunity_types.sql
supabase/migrations/011_due_today_reminders.sql
supabase/policies.sql
```

Apply migrations in numeric order before running `supabase/policies.sql`. The policies file assumes the current UUID-backed opportunity schema from migration `006`.

For a brand-new reset, `supabase/migrations/000_fresh_baseline.sql` is a squashed baseline for the final schema. Use it instead of replaying `001` through `011`; do not apply both paths to the same database.

Create these private Supabase Storage buckets:

- `posters`
- `documents`

Run daily reminders:

```bash
python -m jobs.daily_reminder_job
```

Run React UI:

```bash
cd frontend/react
npm install
npm run dev
```

Create `frontend/react/.env`:

```env
VITE_COMPASS_API_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```
