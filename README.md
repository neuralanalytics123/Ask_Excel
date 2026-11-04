# 📊 AI Excel Analyst

Upload a CSV or Excel file and ask questions about it in plain English. No sign-up and no API key for users.

## What it is

A web app that turns a spreadsheet into something you can chat with. An AI model (via [Groq](https://groq.com)) writes and runs SQL on your data with [DuckDB](https://duckdb.org) and explains the results. Built with Streamlit, Agno, DuckDB and pandas.

## How it works

1. The user uploads a CSV/XLSX file. It is cleaned with pandas (trimmed text, numbers and dates detected, `NA`/`null` treated as empty).
2. The data is loaded into a private in-memory DuckDB table. File and network access is switched off and locked.
3. The user asks a question. An AI agent writes read-only SQL, runs it, and answers with numbers and tables.
4. If a model is busy, unavailable or rate-limited, the app automatically tries the next best Groq model, so it keeps working.

The Groq key is stored once on the server as a secret. Users never see it.

## How to use (for users)

1. Open the app link.
2. Upload a CSV or Excel file (up to 20 MB).
3. Ask a question, or click **Summarize dataset**, **Data quality check** or **Suggest questions**.
4. Use the other tabs for a data profile, your own SQL, and charts.

Example: *"What are the top 5 products by revenue?"*

## Features

- Chat with your data, with follow-up questions
- Excel sheet picker, automatic data cleaning, data profile
- Read-only SQL tab and charts (bar, line, scatter, histogram)
- Download the cleaned CSV, query results and the chat
- Automatic model selection and fallback
- Usage limits per visitor and for the whole app
- Optional access code to keep the app private to your company

## Deploy live (for the owner)

You need a free Groq key from <https://console.groq.com/keys>.

### Option A: Streamlit Community Cloud (free, easiest)

1. Push this project to a GitHub repo (`app.py`, `pyproject.toml` and `uv.lock` in the root).
2. Go to <https://share.streamlit.io> → **Create app** → choose the repo → main file `app.py`.
3. Before deploying, open **Advanced settings → Secrets** and paste:
   ```toml
   GROQ_API_KEY = "gsk_your_key_here"
   ```
4. Click **Deploy** and share the `*.streamlit.app` link.

Free apps go to sleep when idle and wake on the next visit. For an always-on service use Option B.

### Option B: Docker on any host (Render, Railway, Google Cloud Run, a VPS)

```bash
docker build -t ai-excel-analyst .
docker run -p 8501:8501 -e GROQ_API_KEY=gsk_your_key_here ai-excel-analyst
```

On a hosting service, deploy from the repo (it detects the `Dockerfile`) and add `GROQ_API_KEY` as an environment variable in the dashboard. The app listens on `$PORT`.

### Run locally

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                                       # install dependencies
cp .streamlit/secrets.toml.example .streamlit/secrets.toml    # then put your key in it
uv run streamlit run app.py
```

Run `uv lock` once and commit the generated `uv.lock` so every deploy installs the same versions. Always start the app with `uv run streamlit run app.py`, not `python app.py`.

## Settings (all optional)

Set these as secrets or environment variables.

| Name | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | none (required) | Your Groq key |
| `APP_ACCESS_CODE` | off | Password users must enter (for company-only use) |
| `MODELS` | auto | Comma-separated model order, e.g. `openai/gpt-oss-120b,openai/gpt-oss-20b` |
| `MAX_QUESTIONS_PER_SESSION` | 40 | Questions per visitor session |
| `MAX_QUESTIONS_PER_MINUTE` | 20 | All visitors together |
| `MAX_QUESTIONS_PER_DAY` | 1500 | All visitors together |
| `MAX_ROWS` | 200000 | Rows used from an upload |

The upload size limit (20 MB) is set in `.streamlit/config.toml`.

## Important for running it for other people

- **Your key pays for everyone.** The free Groq tier has its own rate limits, so keep the usage limits above set. For many users or company use, use a paid Groq plan.
- **Never commit your key.** Use secrets or environment variables only. `secrets.toml` is git-ignored.
- **Privacy.** Files are processed in memory and not saved. Questions and the relevant data are sent to Groq. Tell users not to upload data they can't share with a third-party AI provider, and add a privacy notice for company use.
- **Security.** The AI and SQL tab can only read the uploaded table. SQL is read-only and DuckDB external access is locked.
- **AI can be wrong.** Check important numbers with the SQL tab.

## Project structure

```
ai_excel_analyst/
├── app.py                 # Streamlit interface
├── core/
│   ├── config.py          # Settings and secrets
│   ├── data.py            # Reading, cleaning, DuckDB
│   ├── llm.py             # Groq models and fallback
│   └── limits.py          # Shared usage limits
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── Dockerfile
├── pyproject.toml         # Dependencies (uv)
├── uv.lock                # Created by `uv lock`
├── .python-version
└── README.md
```

## Troubleshooting

| Problem | Fix |
|---|---|
| "The AI is not configured yet" | `GROQ_API_KEY` is missing or not set in Secrets / environment variables. |
| "The AI service is very busy" | Groq rate limit. Wait a minute, or upgrade your Groq plan. |
| "Temporarily unavailable" / model errors | Set `MODELS` to models your key can use (see <https://console.groq.com/docs/models>). |
| `missing ScriptRunContext` | You ran `python app.py`. Use `uv run streamlit run app.py`. |
| Build fails on deploy | Check the log. Run `uv lock` locally and commit `uv.lock` so versions are pinned. |

## License

Add a `LICENSE` file (for example MIT) before publishing.
