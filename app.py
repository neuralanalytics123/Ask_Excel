import hmac
import logging

import pandas as pd
import streamlit as st

from core.config import APP_TITLE, load_settings
from core.data import (TABLE, build_connection, column_profile, read_file, sheet_names)
from core.limits import get_limiter
from core.llm import ask, resolve_models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")
settings = load_settings()

# ----------------------------------------------------------------------------
# Optional access code (set APP_ACCESS_CODE to restrict the app to your company)
# ----------------------------------------------------------------------------
if settings.access_code and not st.session_state.get("authed"):
    st.title(f"📊 {APP_TITLE}")
    code = st.text_input("Access code", type="password")
    if code:
        if hmac.compare_digest(code.encode(), settings.access_code.encode()):
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Wrong access code.")
    st.stop()

# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
st.session_state.setdefault("messages", [])
st.session_state.setdefault("used", 0)

with st.sidebar:
    st.header(f"📊 {APP_TITLE}")
    st.write("Upload a spreadsheet and ask questions in plain English.")
    remaining = max(settings.max_questions - st.session_state.used, 0)
    st.metric("Questions left this session", remaining)
    if st.button("🗑️ Clear chat"):
        st.session_state.messages = []
    st.divider()
    st.caption(
        "Privacy: your file is processed in memory and is not saved. Your questions and the "
        "relevant data are sent to an AI provider (Groq) to produce answers. Don't upload "
        "data you aren't allowed to share."
    )

# ----------------------------------------------------------------------------
# Upload
# ----------------------------------------------------------------------------
st.title(f"📊 {APP_TITLE}")
st.caption("Upload a CSV or Excel file, then ask questions in plain English.")

uploaded_file = st.file_uploader("Upload a CSV or Excel file (max 20 MB)", type=["csv", "xlsx", "xls"])
if uploaded_file is None:
    st.info("👆 Upload a file to get started.")
    st.stop()

file_bytes = uploaded_file.getvalue()
sheet = None
if not uploaded_file.name.lower().endswith(".csv"):
    try:
        sheets = sheet_names(file_bytes)
    except Exception:
        st.error("Could not open this Excel file. Please check that it is a valid .xlsx or .xls file.")
        st.stop()
    sheet = st.selectbox("Sheet", sheets) if len(sheets) > 1 else sheets[0]

try:
    df = read_file(file_bytes, uploaded_file.name, sheet, settings.max_rows)
except Exception:
    st.error("Could not read this file. Please check the format and try again.")
    st.stop()

if df.empty:
    st.error("The file has no data.")
    st.stop()
if len(df) >= settings.max_rows:
    st.warning(f"Only the first {settings.max_rows:,} rows are used.")

# Rebuild the DuckDB table only when the uploaded data changes
data_key = (uploaded_file.name, uploaded_file.size, sheet)
if st.session_state.get("data_key") != data_key:
    st.session_state.data_key = data_key
    st.session_state.con = build_connection(df)
    st.session_state.messages = []
    st.session_state.agents = {}
con = st.session_state.con

c1, c2, c3 = st.columns(3)
c1.metric("Rows", f"{len(df):,}")
c2.metric("Columns", len(df.columns))
c3.metric("Missing cells", f"{int(df.isna().sum().sum()):,}")

tab_chat, tab_data, tab_sql, tab_chart = st.tabs(["💬 Ask", "🔎 Data & Profile", "🧮 SQL", "📈 Charts"])

# ----------------------------------------------------------------------------
# Ask tab
# ----------------------------------------------------------------------------
with tab_chat:
    ai_ready = bool(settings.api_key)
    if not ai_ready:
        st.error("The AI is not configured yet. The site administrator must set `GROQ_API_KEY`. "
                 "The Data, SQL and Charts tabs still work.")

    quick = {
        "📋 Summarize dataset": "Give a short summary of this dataset: what it contains, key columns, and notable patterns.",
        "🧹 Data quality check": "Check data quality: missing values, duplicates, outliers and inconsistent values. List the problems found.",
        "💡 Suggest questions": "Suggest 6 insightful questions I could ask about this data.",
    }
    cols = st.columns(len(quick))
    pending = None
    for col, (label, prompt) in zip(cols, quick.items()):
        if col.button(label):
            pending = prompt

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    typed = st.chat_input("Ask a question about your data...")
    question = pending or typed

    if question and ai_ready:
        allowed, reason = True, ""
        if st.session_state.used >= settings.max_questions:
            allowed, reason = False, "session"
        else:
            allowed, reason = get_limiter(settings.per_minute, settings.per_day).acquire()

        if not allowed:
            msgs = {
                "session": "You have used all your questions for this session. Refresh the page to start a new session.",
                "busy": "Many people are using the app right now. Please wait a minute and try again.",
                "daily": "The app has reached its daily limit. Please come back tomorrow.",
            }
            st.warning(msgs[reason])
        else:
            st.session_state.used += 1
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    answer, _model = ask(question, st.session_state.messages, con, df,
                                         settings, resolve_models(settings))
                st.markdown(answer)
            st.session_state.messages += [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]

    if st.session_state.messages:
        transcript = "\n\n".join(
            f"**{m['role'].capitalize()}:** {m['content']}" for m in st.session_state.messages
        )
        st.download_button("⬇️ Download chat (.md)", transcript, "analysis_chat.md", "text/markdown")

# ----------------------------------------------------------------------------
# Data & profile tab
# ----------------------------------------------------------------------------
with tab_data:
    st.subheader("Preview")
    st.dataframe(df.head(1000))
    st.caption("Showing up to the first 1,000 rows.")
    st.download_button("⬇️ Download cleaned CSV", df.to_csv(index=False), "cleaned_data.csv", "text/csv")

    st.subheader("Column profile")
    st.dataframe(column_profile(df))

    numeric = df.select_dtypes("number")
    if not numeric.empty:
        st.subheader("Numeric summary")
        st.dataframe(numeric.describe().T)

# ----------------------------------------------------------------------------
# SQL tab
# ----------------------------------------------------------------------------
with tab_sql:
    st.write(f"Run your own DuckDB SQL on the table `{TABLE}`.")
    sql = st.text_area("SQL", value=f"SELECT * FROM {TABLE} LIMIT 100", height=120)
    if st.button("Run query"):
        if not sql.strip().lower().startswith(("select", "with", "describe", "summarize")):
            st.warning("Only read-only queries (SELECT / WITH / DESCRIBE / SUMMARIZE) are allowed here.")
        else:
            try:
                result = con.execute(sql).df()
                st.dataframe(result)
                st.download_button("⬇️ Download result", result.to_csv(index=False), "query_result.csv", "text/csv")
            except Exception as e:
                st.error(f"SQL error: {e}")

# ----------------------------------------------------------------------------
# Charts tab
# ----------------------------------------------------------------------------
with tab_chart:
    chart_type = st.selectbox("Chart type", ["Bar", "Line", "Scatter", "Histogram"])
    all_cols = df.columns.tolist()
    num_cols = df.select_dtypes("number").columns.tolist()

    if not num_cols:
        st.info("No numeric columns available for charts.")
    elif chart_type == "Histogram":
        col = st.selectbox("Column", num_cols)
        counts = pd.cut(df[col].dropna(), bins=20).value_counts().sort_index()
        counts.index = counts.index.astype(str)
        st.bar_chart(counts)
    else:
        x = st.selectbox("X axis", all_cols)
        y = st.selectbox("Y axis", num_cols)
        if chart_type == "Scatter":
            st.scatter_chart(df, x=x, y=y)
        elif chart_type == "Bar":
            top = df[[x, y]].dropna().groupby(x)[y].sum().sort_values(ascending=False).head(50)
            st.caption("Total of the Y column per X value (top 50).")
            st.bar_chart(top)
        else:
            st.line_chart(df[[x, y]].dropna().set_index(x)[y])
