# 📊 Ask_Excel

Talk to your Excel Files . Upload a CSV or Excel file and ask questions in plain English.

Project Link( https://neuralanalytics123-ask-excel-app-qr7agy.streamlit.app/)

## What it is

ExcelTalk is a web app that turns a spreadsheet into something you can chat with. You upload a file, ask a question such as *"What are the top 5 products by revenue?"*.

It also includes a data profile, a SQL editor and charts, so you can check the AI's answers yourself.

**Built with: Streamlit, Groq , LLM .

**Main features**

- Ask questions in plain English, with follow-up questions
- One-click *Summarize dataset*, *Data quality check* and *Suggest questions*
- CSV, XLSX and XLS support, with an Excel sheet picker
- Automatic data cleaning
- Data profile, read-only SQL tab and charts (bar, line, scatter, histogram)
- Download the cleaned CSV, query results and the chat
- Automatic model fallback and usage limits

---

## How to run it locally

You need Python 3.10+ , UV.

**1. Get the code**

```bash
git clone https://github.com/neuralanalytics123/Ask_Excel.git
cd Ask_Excel
```

**2. Install the dependencies**

```bash
uv sync
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Windows (PowerShell)
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Open `.streamlit/secrets.toml` and put your key inside the quotes:

```toml
GROQ_API_KEY = "gsk_your_key_here"
```

This file is git-ignored. Never commit it or share your key.

**4. Start the app**

```bash
uv run streamlit run app.py
```

Open <http://localhost:8501>, upload a file and ask a question.

> Always start the app with `uv run streamlit run app.py`. Running `python app.py` does not work.

**Optional settings.** Add these to `secrets.toml` or set them as environment variables:

| Name | Default | Purpose |
|---|---|---|
| `APP_ACCESS_CODE` | off | Password users must enter before using the app |
| `MODELS` | auto | Comma-separated model order, e.g. `openai/gpt-oss-120b,openai/gpt-oss-20b` |
| `MAX_QUESTIONS_PER_SESSION` | 40 | Questions per visitor session |
| `MAX_QUESTIONS_PER_MINUTE` | 20 | All visitors together |
| `MAX_QUESTIONS_PER_DAY` | 1500 | All visitors together |
| `MAX_ROWS` | 200000 | Rows used from an upload |

The upload limit (20 MB) is set in `.streamlit/config.toml`.

---

## Project structure

```
exceltalk/
├── app.py                      # Streamlit interface: tabs, chat, upload, limits check
├── core/
│   ├── __init__.py
│   ├── config.py               # Settings and secrets (API key, limits, model list)
│   ├── data.py                 # File reading, cleaning, profiling, locked DuckDB table
│   ├── llm.py                  # Groq models through Agno, model discovery and fallback
│   └── limits.py               # Shared rate limiter for all visitors
├── .streamlit/
│   ├── config.toml             # Upload size, XSRF protection, theme
│   └── secrets.toml.example    # Template for your local secrets.toml
├── Dockerfile                  # Optional container build (uses uv)
├── .dockerignore
├── .gitignore                  # Keeps secrets and data files out of Git
├── .python-version
├── pyproject.toml              # Project metadata and dependencies (uv)
├── uv.lock                     # Exact dependency versions
└── README.md
```

---

## How it works

```
 Upload CSV / XLSX
        │
        ▼
 pandas: read + clean
        │
        ▼
 DuckDB (in memory)  →  table `uploaded_data`   (file/network access locked)
        ▲
        │  read-only SQL through Agno's DuckDB tool
        │
 Agno agent  ⇄  Groq model (auto-selected, with fallback)
        │
        ▼
 Streamlit: Ask · Data & Profile · SQL · Charts
```

**1. Reading and cleaning (`core/data.py`)**
The file is read with pandas, up to `MAX_ROWS` rows. Column names are trimmed, empty rows and columns are dropped, and text is trimmed. Values such as `NA`, `N/A`, `null`, `missing` and `-` become empty. A text column becomes numeric only if every non-empty value parses as a number. Columns whose name contains `date` or `time` are parsed as dates.

**2. A private, locked database (`core/data.py`)**
The cleaned data is loaded into an in-memory DuckDB table called `uploaded_data`. Then DuckDB's external access is turned off and its configuration is locked, so neither the AI nor the SQL tab can read server files or URLs. Each visitor session gets its own database.

**3. The AI agent (`core/llm.py`)**
An Agno agent is given the table's column names and types, plus rules: always quote column names, run only read-only `SELECT` queries, never invent numbers, and fix failed queries. The agent writes SQL, runs it through the DuckDB tool and explains the result. The last few chat messages are sent as context so follow-up questions work.

**4. Model selection and fallback (`core/llm.py`)**
On start, the app asks Groq which chat models the configured key can use (refreshed every 30 minutes) and orders them by preference. If a model is missing, rate-limited or fails, the app tries up to three models before showing a friendly error. Groq's model names change over time, so nothing depends on one fixed model. You can force an order with `MODELS`.

**5. Usage limits (`core/limits.py`, `app.py`)**
A shared limiter caps questions per minute and per day for the whole app, and each session has its own question cap. This protects the API quota from heavy use.

**6. The interface (`app.py`)**
- **Ask:** chat, quick actions and chat download.
- **Data & Profile:** preview, missing values, unique counts, numeric summary, cleaned CSV download.
- **SQL:** your own read-only queries (`SELECT`, `WITH`, `DESCRIBE`, `SUMMARIZE`).
- **Charts:** bar, line, scatter and histogram without calling the AI.

**7. Security and privacy**
- The API key is read only from Streamlit secrets or environment variables and is never shown to users.
- Files are processed in memory and not saved. Each user's data and chat stay in their own session.
- Questions, the table schema and query results are sent to Groq to produce answers. Don't upload data you aren't allowed to share with a third-party AI provider.
- Optional `APP_ACCESS_CODE` restricts the app to people who know the password.
- AI answers can be wrong. Check important numbers with the SQL tab.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `missing ScriptRunContext` or `'NoneType' object has no attribute 'getvalue'` | You ran `python app.py`. Use `uv run streamlit run app.py`. |
| `uv: command not found` | Install uv from <https://docs.astral.sh/uv/getting-started/installation/>, then open a new terminal. |
| "The AI is not configured yet" | `GROQ_API_KEY` was not found. Check that the file is named exactly `.streamlit/secrets.toml`, the line is `GROQ_API_KEY = "gsk_..."` with quotes, then restart the app with Ctrl+C and run it again. |
| "The AI service is not configured correctly" | The key is invalid or revoked. Create a new one at <https://console.groq.com/keys> and update `secrets.toml`. |
| "The AI service is very busy" / rate limit | Groq's limit was reached. Wait a minute and retry, or use a paid Groq plan. |
| `model_not_found` or "temporarily unavailable" | Models change on Groq. Check <https://console.groq.com/docs/models> and set `MODELS` to models your key can use. |
| "That question needs too much data at once" | Ask a narrower question or upload a smaller file. |
| "Could not read this file" | Make sure it is a valid `.csv`, `.xlsx` or `.xls` file under 20 MB. |
| Numbers or dates are not detected correctly | Name date columns with `date` or `time`, and remove text such as "$" or "units" from number cells. |
| You see "questions left: 0" | The session limit was reached. Refresh the page, or raise `MAX_QUESTIONS_PER_SESSION`. |
| Dependency install or deploy build fails | Run `uv lock` and commit the new `uv.lock`, then try again. |
| Free Streamlit app is asleep | Open the link and click the wake-up button. |

If your problem is not listed, open a GitHub issue with the error message and the steps you took. Don't include your API key or private data.

---

## Future collaborations

Ideas where contributions are welcome:

- **More file types:** Parquet, JSON, Google Sheets, multi-sheet joins
- **Better charts:** AI-generated charts from questions, downloadable images
- **Saved projects:** optional accounts and saved conversations
- **More AI providers:** a provider switch beyond Groq
- **Team features:** shared workspaces, role-based access, audit logs
- **Quality:** automated tests, benchmarks for SQL accuracy, more languages
- **Deployment:** one-click deploy guides, a Docker Compose setup

**How to contribute**

1. Fork the repository and create a branch (`git checkout -b feature/your-idea`).
2. Make your change and test it with `uv run streamlit run app.py`.
3. Open a pull request that explains what changed and why.

For bigger ideas, partnerships or company use, open a GitHub issue titled "Collaboration" or contact the maintainer: `neuralrush82@gmail.com`.

