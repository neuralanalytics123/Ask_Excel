"""File reading, cleaning, profiling and the locked-down DuckDB table."""

import io

import duckdb
import pandas as pd
import streamlit as st

TABLE = "uploaded_data"
NA_VALUES = ["NA", "N/A", "n/a", "missing", "null", "NULL", "-"]


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Tidy column names, trim text, and parse numbers and dates."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~pd.Index(df.columns).duplicated()]  # drop duplicate column names
    df = df.dropna(how="all").dropna(axis=1, how="all")

    for col in df.columns:
        series = df[col]
        is_text = pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)
        name = col.lower()

        if is_text:
            text = series.astype("string").str.strip()
            text = text.mask(text.isin(["", "nan", "None", "NaT", *NA_VALUES]))
            if "date" in name or "time" in name:
                df[col] = pd.to_datetime(text, errors="coerce")
            else:
                numeric = pd.to_numeric(text, errors="coerce")
                # Treat the column as numeric only if every non-empty value parsed
                if numeric.notna().sum() == text.notna().sum() and text.notna().any():
                    df[col] = numeric.astype("float64")
                else:
                    df[col] = text.astype(object).where(text.notna(), None)
        elif ("date" in name or "time" in name) and not pd.api.types.is_datetime64_any_dtype(series):
            df[col] = pd.to_datetime(series, errors="coerce")
    return df


def sheet_names(file_bytes: bytes) -> list[str]:
    return pd.ExcelFile(io.BytesIO(file_bytes)).sheet_names


@st.cache_data(show_spinner=False, max_entries=5)
def read_file(file_bytes: bytes, file_name: str, sheet: str | None, max_rows: int) -> pd.DataFrame:
    buffer = io.BytesIO(file_bytes)
    if file_name.lower().endswith(".csv"):
        df = pd.read_csv(buffer, na_values=NA_VALUES, encoding_errors="replace", nrows=max_rows)
    else:
        df = pd.read_excel(buffer, sheet_name=sheet or 0, na_values=NA_VALUES, nrows=max_rows)
    return clean_dataframe(df)


def schema_text(df: pd.DataFrame) -> str:
    return "\n".join(f'- "{c}" ({t})' for c, t in df.dtypes.astype(str).items())


def build_connection(df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB holding only the uploaded table, locked down afterwards."""
    con = duckdb.connect(":memory:")
    con.register("df_view", df)
    con.execute(f"CREATE TABLE {TABLE} AS SELECT * FROM df_view")
    con.unregister("df_view")
    # Security: no reading/writing server files or URLs, and settings can't be changed back
    con.execute("SET enable_external_access=false")
    con.execute("SET lock_configuration=true")
    return con


def column_profile(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "type": df.dtypes.astype(str),
        "missing": df.isna().sum(),
        "missing %": (df.isna().mean() * 100).round(1),
        "unique": df.nunique(),
    })
