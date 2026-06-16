# Deploy AIMS as a shareable link

Goal: a private URL you can send to colleagues/clients. Live scoring runs on **your** central
DeepSeek/OpenAI keys (held as server secrets — never shown to visitors), there's **no Settings/API
page**, the link is behind a **passphrase**, and live spend is **capped**.

## What the hosted build does (automatically, when `AIMS_HOSTED=1`)
- Hides the Settings & API-key page and the Database/Prior-reports list.
- Reads keys only from server env vars (your central account).
- Requires the access **passphrase** (`/unlock`) before anything loads.
- Enforces a **global live-spend cap** (`AIMS_GLOBAL_CAP_USD`, default $25) and a **per-visitor
  hourly rate limit** (`AIMS_RATE_LIMIT_PER_HOUR`, default 8). The Sample engine stays free/unlimited.

## Environment variables to set on the host
| Var | Value |
|---|---|
| `AIMS_HOSTED` | `1` |
| `AIMS_ACCESS_PASSPHRASE` | the password you share with trusted users |
| `AIMS_SECRET_KEY` | any long random string (signs the login cookie) |
| `DEEPSEEK_API_KEY` | your DeepSeek key |
| `OPENAI_API_KEY` | your OpenAI key (enables RAG) |
| `AIMS_GLOBAL_CAP_USD` | e.g. `25` (total live spend before it pauses) |
| `AIMS_RATE_LIMIT_PER_HOUR` | e.g. `8` |

Keys are **secrets** — they live only on the host, never in the repo (`.env` / `settings.json` are
gitignored). Rotate them if a passphrase leaks.

## Option A — Render (recommended, ~10–15 min)
1. Put this repo on **GitHub** (private is fine):
   ```
   cd aims
   git remote add origin https://github.com/<you>/aims.git
   git push -u origin main
   ```
2. On **render.com**: **New → Blueprint**, connect the repo. It reads `render.yaml` and creates the
   service (Docker, single instance, health check `/healthz`).
3. In the service's **Environment**, fill the three `sync:false` secrets: `AIMS_ACCESS_PASSPHRASE`,
   `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`. (Others are preset.)
4. **Create / Deploy**. In ~3–5 min you get a URL like `https://aims-xyz.onrender.com`.
5. Share the URL **and** the passphrase. Done. (Add a custom domain later in Render settings.)

## Option B — any Docker host (Railway, Fly.io, a VPS)
```
docker build -t aims .
docker run -p 8765:8765 \
  -e AIMS_HOSTED=1 \
  -e AIMS_ACCESS_PASSPHRASE="your-passphrase" \
  -e AIMS_SECRET_KEY="a-long-random-string" \
  -e DEEPSEEK_API_KEY="sk-..." \
  -e OPENAI_API_KEY="sk-..." \
  -e AIMS_GLOBAL_CAP_USD=25 \
  aims
```
Put it behind HTTPS (the platform's proxy, or Caddy/nginx on a VPS).

## Important notes
- **Run a single instance.** Scoring progress + batches are kept in memory on one server. Scaling to
  multiple instances would break the progress/polling. (Moving to Postgres + a job queue is the
  upgrade path when you outgrow one box — see the commercialization estimate.)
- **Cost control.** A public link that scores on your keys can spend your money — the passphrase +
  global cap + rate limit bound it. Watch the cap; raise/lower via env.
- **PDF.** The "Download PDF" button needs headless Chromium, which isn't in the slim image — visitors
  can use their browser's Print → Save as PDF. (Add `playwright install chromium` to the Dockerfile if
  you want server-side PDF.)
- **Data.** Submitted stories are stored in the container's SQLite (ephemeral on most hosts — wiped on
  redeploy). Fine for a demo; add a managed Postgres for anything you must keep.
- **Local dev is unchanged.** Without `AIMS_HOSTED=1`, the app behaves exactly as before (Settings
  page, your local keys, no gate).
