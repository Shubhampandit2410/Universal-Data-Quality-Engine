import io, json, sqlite3, re
from datetime import datetime
import pandas as pd
import streamlit as st
from difflib import SequenceMatcher
from quality_engine import issues_for, issue_details_for, cell_errors_for, rows_with_errors, metrics, parse_number_word, is_numeric_context

st.set_page_config(page_title="Universal Data Quality & Auto-Cleaning Engine", page_icon="🧹", layout="wide")
st.title("🧹 Universal Data Quality & Auto-Cleaning Engine")
st.caption("A transparent, approval-based workflow for profiling, reviewing and cleaning tabular data")
st.markdown("""<style>
.block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {background: #f4f7fb !important; border: 1px solid #dbe4f0; padding: 0.8rem 1rem; border-radius: 12px;}
/* Force readable KPI text in both Streamlit light and dark themes. */
[data-testid="stMetric"] label,
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] *,
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] *,
[data-testid="stMetricDelta"],
[data-testid="stMetricDelta"] * {color: #172033 !important; opacity: 1 !important;}
[data-testid="stMetricValue"] {font-weight: 750 !important;}
[data-testid="stSidebar"] {border-right: 1px solid #dbe4f0;}
</style>""", unsafe_allow_html=True)
st.info("Safety first: transformations are previewed on a separate copy. The active working dataset changes only after you select **Approve & Apply**.")
st.caption("Upload limit configured: up to 10 GB. Important: this prototype loads files into memory, so processing very large files depends on available RAM and is not guaranteed. Reliable 10 GB processing needs chunked/streaming support and benchmarking.")

def read_input(file, sqlite_table=None):
    name=file.name.lower()
    raw=file.getvalue()
    if name.endswith(".csv"): return pd.read_csv(io.BytesIO(raw)), file.name
    if name.endswith(".xlsx"): return pd.read_excel(io.BytesIO(raw)), file.name
    if name.endswith(".json"): 
        try: return pd.read_json(io.BytesIO(raw)), file.name
        except ValueError: return pd.json_normalize(json.loads(raw.decode("utf-8"))), file.name
    if name.endswith((".db",".sqlite",".sqlite3")):
        con=sqlite3.connect(":memory:")
        # Load uploaded database bytes into a temporary file-like SQLite DB is not supported directly.
        # Write bytes to a temporary file, then open it read-only.
        import tempfile, os
        fd,path=tempfile.mkstemp(suffix=".db"); os.close(fd)
        try:
            with open(path,"wb") as f: f.write(raw)
            src=sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            tables=pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",src)
            if tables.empty: raise ValueError("No tables found in SQLite database.")
            table=sqlite_table or tables["name"].iloc[0]
            if table not in tables["name"].tolist(): raise ValueError("Selected SQLite table was not found.")
            df=pd.read_sql_query(f'SELECT * FROM "{table.replace(chr(34), chr(34)*2)}"',src)
            src.close()
            return df, f"{file.name} / {table}"
        finally:
            try: os.remove(path)
            except OSError: pass
    raise ValueError("Supported formats: CSV, XLSX, JSON, SQLite DB. Legacy .xls is not enabled in this build.")









if "original" not in st.session_state:
    st.session_state.original=None; st.session_state.current=None; st.session_state.pending=None
    st.session_state.source_name=""; st.session_state.actions=[]
if "pending_log" not in st.session_state:
    st.session_state.pending_log=[]
if "manual_edit_version" not in st.session_state:
    st.session_state.manual_edit_version=0

with st.sidebar:
    st.header("1. Import data")
    up=st.file_uploader("Choose CSV, Excel (.xlsx), JSON, or SQLite file", type=["csv","xlsx","json","db","sqlite","sqlite3"])
    sqlite_table = None
    if up is not None and up.name.lower().endswith((".db",".sqlite",".sqlite3")):
        try:
            import tempfile, os
            fd, temp_path = tempfile.mkstemp(suffix=".db"); os.close(fd)
            with open(temp_path, "wb") as f: f.write(up.getvalue())
            db = sqlite3.connect(f"file:{temp_path}?mode=ro", uri=True)
            table_names = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", db)["name"].tolist()
            db.close(); os.remove(temp_path)
            if table_names: sqlite_table = st.selectbox("Choose SQLite table", table_names)
            else: st.error("No tables found in SQLite database.")
        except Exception as e:
            st.error(f"Could not inspect SQLite database: {e}")
    if up is not None:
        if st.button("Load / Replace dataset", type="primary", use_container_width=True):
            try:
                df,name=read_input(up, sqlite_table)
                if df.empty and len(df.columns)==0: st.warning("The file has no tabular data.")
                else:
                    st.session_state.original=df.copy(deep=True)
                    st.session_state.current=df.copy(deep=True)
                    st.session_state.pending=None; st.session_state.actions=[]
                    st.session_state.manual_edit_version += 1
                    st.session_state.source_name=name
                    st.success(f"Loaded {name}")
            except Exception as e: st.error(f"Import failed: {e}")

if st.session_state.current is None:
    st.subheader("Welcome")
    st.write("Upload a dataset using the left sidebar, then use the tabs below.")
    st.write("Included sample: `sample_data.csv` — use it to demonstrate missing values, duplicates, spaces, email formats, and dates.")
    st.stop()

original=st.session_state.original
current=st.session_state.current
tabs=st.tabs(["📥 Data Preview", "🔎 Issues & Evidence", "✍️ Manual Editor", "🛠️ Cleaning Review", "📊 Quality Dashboard", "📄 Reports & Downloads"])

def automatic_cleaning_proposal(df, options=None):
    """Build a conservative automatic cleaning proposal plus validation findings.

    Safe transformations are proposed automatically; suspicious/ambiguous records
    are flagged for review rather than silently altered or deleted.
    """
    proposed = df.copy(deep=True)
    log = []
    findings = []
    options = options or {"whitespace": True, "type_conversion": True, "category": True, "dates": True, "validation": True, "outliers": True, "duplicates": True, "fuzzy": True, "missing_action": "Keep missing values", "email_validation": True}
    if options.get("whitespace", True):
        # Trim whitespace in text fields.
        changed = 0
        for col in proposed.select_dtypes(include=["object", "string"]).columns:
            before = proposed[col].copy()
            proposed[col] = proposed[col].map(lambda v: v.strip() if isinstance(v, str) else v)
            changed += int((before.astype("string") != proposed[col].astype("string")).fillna(False).sum())
        if changed:
            log.append(f"Automatic whitespace trimming: {changed} cell(s)")

    if options.get("type_conversion", True):
        # Convert number words and numeric strings only in numeric-context columns and only if all values parse.
        for col in list(proposed.columns):
            series = proposed[col]
            if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
                continue
            vals = series.dropna().astype(str)
            if not len(vals) or not is_numeric_context(col, vals):
                continue
            converted=[]; valid=True
            for val in vals:
                n=pd.to_numeric(val, errors="coerce")
                if pd.isna(n): n=parse_number_word(val)
                if n is None or pd.isna(n): valid=False; break
                converted.append(n)
            if valid:
                proposed[col] = pd.to_numeric(proposed[col].map(lambda v: parse_number_word(v) if isinstance(v,str) and pd.isna(pd.to_numeric(v,errors="coerce")) else v), errors="coerce")
                log.append(f"Automatic numeric conversion in '{col}' (including supported number words)")
            else:
                word_cells = [(idx, val, parse_number_word(val)) for idx,val in vals.items() if parse_number_word(val) is not None and pd.isna(pd.to_numeric(val,errors="coerce"))]
                for idx,val,num in word_cells:
                    findings.append({"Type":"Convertible number word", "Column":str(col), "Row":int(idx)+1 if isinstance(idx,int) else str(idx), "Value":val, "Recommendation":f"Convert to {num}; column kept unchanged because other values need review"})

    if options.get("convert_numeric_to_text", False):
        converted_cols = []
        for col in proposed.select_dtypes(include=["number"]).columns:
            proposed[col] = proposed[col].map(lambda v: str(v) if pd.notna(v) else v)
            converted_cols.append(str(col))
        if converted_cols:
            log.append("Converted numeric columns to text: " + ", ".join(converted_cols))

    if options.get("category", True):
        # Standardize case/outer whitespace only for likely categorical columns.
        # Avoid names, free text, e-mails and identifiers: similar casing there may be meaningful.
        category_hints = ("category", "status", "city", "state", "country", "gender", "type",
                          "department", "team", "segment", "region", "grade", "product", "channel")
        excluded_hints = ("name", "email", "mail", "address", "description", "comment", "text",
                          "id", "code", "phone", "mobile", "url")
        for col in proposed.select_dtypes(include=["object", "string"]).columns:
            col_lower = str(col).lower()
            vals = proposed[col].dropna().astype(str)
            if not len(vals) or any(h in col_lower for h in excluded_hints):
                continue
            likely_category = any(h in col_lower for h in category_hints)
            likely_category = likely_category or (vals.nunique() <= min(50, max(2, int(len(vals) * 0.2))) and vals.nunique() / max(len(vals), 1) <= 0.2)
            if not likely_category:
                continue
            groups = {}
            for val in vals:
                key = val.strip().casefold()
                groups.setdefault(key, []).append(val)
            for key, variants in groups.items():
                if len(set(variants)) > 1:
                    canonical = sorted(set(variants), key=lambda x: (-variants.count(x), len(x), x))[0].strip()
                    mask = proposed[col].astype("string").str.strip().str.casefold().eq(key)
                    count = int((proposed.loc[mask, col].astype(str) != canonical).sum())
                    proposed.loc[mask, col] = canonical
                    if count:
                        log.append(f"Category standardization in '{col}': {len(set(variants))} case/whitespace variants → '{canonical}' ({count} cell(s))")

    if options.get("dates", True):
        # Date-like columns are converted only when all non-missing values parse; proposed values are shown for review.
        for col in proposed.columns:
            if any(k in str(col).lower() for k in ["date","dob","joined","created"]):
                vals=proposed[col].dropna()
                if len(vals):
                    parsed=pd.to_datetime(proposed[col], errors="coerce")
                    if int(parsed.notna().sum()) == len(vals):
                        proposed[col]=parsed
                        log.append(f"Automatic date conversion in '{col}'")
                    else:
                        bad=proposed[col].notna() & parsed.isna()
                        for idx,val in proposed.loc[bad,col].items(): findings.append({"Type":"Invalid date", "Column":str(col), "Row":int(idx)+1 if isinstance(idx,int) else str(idx), "Value":str(val), "Recommendation":"Correct date format; original preserved"})

    if options.get("validation", True):
        # Domain validation: flag, never silently rewrite age-like values.
        for col in proposed.columns:
            if "age" in str(col).lower():
                numeric=pd.to_numeric(proposed[col], errors="coerce")
                bad=proposed[col].notna() & (numeric.isna() | (numeric < 0) | (numeric > 120))
                for idx,val in proposed.loc[bad,col].items(): findings.append({"Type":"Age range/type validation", "Column":str(col), "Row":int(idx)+1 if isinstance(idx,int) else str(idx), "Value":str(val), "Recommendation":"Check expected age; plausible range is 0–120, not auto-corrected"})

    if options.get("outliers", True):
        # Statistical outliers: IQR-based flags, no automatic value changes.
        for col in proposed.select_dtypes(include="number").columns:
            vals=proposed[col].dropna()
            if len(vals) >= 5 and vals.nunique() >= 4:
                q1,q3=vals.quantile(.25),vals.quantile(.75); iqr=q3-q1
                if iqr > 0:
                    mask=proposed[col].notna() & ((proposed[col] < q1-1.5*iqr) | (proposed[col] > q3+1.5*iqr))
                    for idx,val in proposed.loc[mask,col].items(): findings.append({"Type":"Potential statistical outlier", "Column":str(col), "Row":int(idx)+1 if isinstance(idx,int) else str(idx), "Value":str(val), "Recommendation":"Review context; outliers may be valid and are not changed automatically"})

    # Structural cleanup options. Each operation is proposed on a copy and requires approval.
    if options.get("remove_fully_empty_rows", False):
        before_rows = len(proposed)
        proposed = proposed.dropna(how="all").reset_index(drop=True)
        removed = before_rows - len(proposed)
        if removed:
            log.append(f"Removed completely empty row(s): {removed}")

    if options.get("remove_fully_empty_columns", False):
        empty_cols = [c for c in proposed.columns if proposed[c].isna().all()]
        if empty_cols:
            proposed = proposed.drop(columns=empty_cols)
            log.append("Removed completely empty column(s): " + ", ".join(map(str, empty_cols)))

    if options.get("remove_constant_columns", False):
        constant_cols = [c for c in proposed.columns if proposed[c].nunique(dropna=True) <= 1 and proposed[c].notna().any()]
        if constant_cols:
            proposed = proposed.drop(columns=constant_cols)
            log.append("Removed constant column(s) with one non-missing unique value: " + ", ".join(map(str, constant_cols)))

    # Missing-value strategies. Filling takes precedence over row deletion when requested.
    if options.get("fill_missing_instead_delete_rows", False):
        numeric_strategy = options.get("numeric_fill_strategy", "Median")
        numeric_custom = options.get("custom_numeric_fill_value", 0.0)
        text_strategy = options.get("text_fill_strategy", "Mode")
        text_custom = options.get("custom_text_fill_value", "Unknown")
        filled = 0
        for col in proposed.columns:
            mask = proposed[col].isna()
            count = int(mask.sum())
            if not count:
                continue
            if pd.api.types.is_numeric_dtype(proposed[col]):
                non_missing = proposed[col].dropna()
                if numeric_strategy == "Median" and len(non_missing):
                    fill_value = non_missing.median()
                else:
                    fill_value = numeric_custom if numeric_strategy == "Custom value" else None
                if fill_value is not None:
                    proposed.loc[mask, col] = fill_value
                    filled += count
            elif pd.api.types.is_datetime64_any_dtype(proposed[col]):
                non_missing = proposed[col].dropna()
                if text_strategy == "Mode" and len(non_missing):
                    modes = non_missing.mode()
                    if len(modes):
                        proposed.loc[mask, col] = modes.iloc[0]
                        filled += count
                else:
                    findings.append({"Type":"Missing date value", "Column":str(col), "Row":"—", "Value":"∅", "Recommendation":"Custom text fill is not applied to a date column; choose a valid date explicitly"})
            else:
                non_missing = proposed[col].dropna()
                if text_strategy == "Mode" and len(non_missing):
                    modes = non_missing.mode()
                    fill_value = modes.iloc[0] if len(modes) else text_custom
                else:
                    fill_value = text_custom
                proposed.loc[mask, col] = fill_value
                filled += count
        if filled:
            log.append(f"Filled {filled} missing cell(s) instead of deleting rows (numeric: {numeric_strategy}; text/category: {text_strategy})")
        else:
            log.append("Missing-value fill selected, but no cells could be filled using the selected strategies")
    elif options.get("remove_rows_any_missing", False):
        before_rows = len(proposed)
        proposed = proposed.dropna(how="any").reset_index(drop=True)
        removed = before_rows - len(proposed)
        if removed:
            log.append(f"Removed row(s) containing one or more missing values: {removed}")
    elif options.get("missing_action") == "Flag missing values only":
        for col in proposed.columns:
            for idx in proposed.index[proposed[col].isna()]:
                findings.append({"Type":"Missing value", "Column":str(col), "Row":int(idx)+1 if isinstance(idx,int) else str(idx), "Value":"∅", "Recommendation":"Choose a fill strategy or keep it missing"})

    if options.get("email_validation", True):
        for col in proposed.select_dtypes(include=["object", "string"]).columns:
            if "email" in str(col).lower() or "e-mail" in str(col).lower():
                vals = proposed[col].dropna().astype(str)
                invalid = vals[~vals.str.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", na=False)]
                for idx, val in invalid.items():
                    findings.append({"Type":"Invalid email format", "Column":str(col), "Row":int(idx)+1 if isinstance(idx,int) else str(idx), "Value":val, "Recommendation":"Check spelling and email format; original value preserved"})

    if options.get("duplicates", True):
        # Exact duplicate rows are proposed for removal, but still require approval.
        dup_count=int(proposed.duplicated().sum())
        if dup_count:
            proposed=proposed.drop_duplicates(keep="first").reset_index(drop=True)
            log.append(f"Exact duplicate removal proposed: {dup_count} row(s); approve only after preview")

    if options.get("fuzzy", True):
        # Fuzzy matching suggestions across string columns; do not merge or delete fuzzy matches.
        for col in proposed.select_dtypes(include=["object", "string"]).columns:
            vals=proposed[col].dropna().astype(str).drop_duplicates().tolist()
            if 1 < len(vals) <= 500:
                seen=set()
                for i,a in enumerate(vals):
                    for b in vals[i+1:]:
                        pair=tuple(sorted((a,b), key=str.casefold))
                        if pair in seen or a.casefold()==b.casefold(): continue
                        seen.add(pair)
                        ratio=SequenceMatcher(None,a.casefold(),b.casefold()).ratio()
                        if ratio >= .88 and len(a.strip()) >= 4 and len(b.strip()) >= 4:
                            findings.append({"Type":"Possible fuzzy duplicate", "Column":str(col), "Row":"—", "Value":f"{a}  ↔  {b}", "Recommendation":"Compare records; similar text is not proof of same entity"})
    if not log: log.append("No safe automatic transformations were required.")
    return proposed, log, pd.DataFrame(findings, columns=["Type","Column","Row","Value","Recommendation"])

with tabs[0]:
    st.subheader("Data Preview")
    m=metrics(current)
    a,b,c,d=st.columns(4)
    a.metric("Rows",m["Rows"]); b.metric("Columns",m["Columns"]); c.metric("Missing cells",m["Missing cells"]); d.metric("Duplicate rows",m["Duplicate rows"])
    st.caption(f"Source: {st.session_state.source_name}")
    st.dataframe(current.head(100),use_container_width=True)
    profile=pd.DataFrame({"Column":current.columns.astype(str),"Data type":[str(x) for x in current.dtypes],"Non-null":[int(current[x].notna().sum()) for x in current.columns],"Missing":[int(current[x].isna().sum()) for x in current.columns],"Unique":[int(current[x].nunique(dropna=True)) for x in current.columns]})
    st.subheader("Column profile"); st.dataframe(profile,use_container_width=True)
with tabs[1]:
    st.subheader("Detected data-quality issues")
    issue = issues_for(current)
    details = issue_details_for(current)
    if issue.empty:
        st.success("No supported issue pattern detected.")
    else:
        st.markdown("#### Issue summary")
        st.dataframe(issue, use_container_width=True, hide_index=True)
        st.markdown("#### Where exactly is the issue?")
        st.caption("Rows are numbered from 1 for display. Duplicate rows are row-level findings; their cells are not made editable in the manual editor.")
        if not details.empty:
            issue_types = ["All issues"] + sorted(details["Issue"].dropna().unique().tolist())
            chosen_issue = st.selectbox("Filter detailed findings", issue_types, key="issue_detail_filter")
            shown = details if chosen_issue == "All issues" else details[details["Issue"] == chosen_issue]
            st.dataframe(shown, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Download detailed findings (CSV)", shown.to_csv(index=False).encode("utf-8"), "detailed_issue_findings.csv", "text/csv")
    st.download_button("⬇️ Download issue summary (CSV)", issue.to_csv(index=False).encode("utf-8"), "detected_issues.csv", "text/csv")
with tabs[2]:
    st.subheader("✍️ Manual Data Editor — Error Cells Only")
    st.write(
        "Only cells with detected issues can be edited. Rows and columns without "
        "any detected issue are not shown; non-error cells in shown rows are read-only."
    )

    error_cells = cell_errors_for(current)
    error_rows = error_cells.any(axis=1)
    error_cols = error_cells.any(axis=0)

    if not error_rows.any():
        st.success("No supported errors detected. There is nothing to edit.")
    else:
        visible_columns = list(current.columns[error_cols])
        visible_indices = list(current.index[error_rows])
        st.caption(
            f"Showing {len(visible_indices)} error rows and {len(visible_columns)} "
            "columns containing errors. Only marked error cells have editable inputs."
        )

        with st.form(key=f"manual_error_form_{st.session_state.manual_edit_version}"):
            st.caption("🟠 Editable = detected error. Plain text = protected value.")
            for row_index in visible_indices:
                st.markdown(f"**Row index: {row_index}**")
                display_cols = st.columns(max(1, len(visible_columns)))
                for j, col in enumerate(visible_columns):
                    with display_cols[j]:
                        st.caption(str(col))
                        value = current.at[row_index, col]
                        widget_key = f"manual_cell_{st.session_state.manual_edit_version}_{row_index}_{str(col)}"
                        if bool(error_cells.at[row_index, col]):
                            shown_value = "" if pd.isna(value) else str(value)
                            st.text_input(
                                "Fix value",
                                value=shown_value,
                                key=widget_key,
                                placeholder="Enter corrected value",
                                label_visibility="collapsed",
                            )
                        else:
                            shown_value = "∅ (missing)" if pd.isna(value) else str(value)
                            st.text(shown_value)
                st.divider()

            submitted = st.form_submit_button(
                "🔍 Preview Manual Changes", type="primary", use_container_width=True
            )

        if submitted:
            proposed = current.copy(deep=True)
            changed_count = 0
            conversion_warnings = []

            for row_index in visible_indices:
                for col in visible_columns:
                    if not bool(error_cells.at[row_index, col]):
                        continue

                    widget_key = f"manual_cell_{st.session_state.manual_edit_version}_{row_index}_{str(col)}"
                    raw_value = st.session_state.get(widget_key, "")
                    old_value = current.at[row_index, col]

                    if raw_value.strip() == "":
                        new_value = pd.NA
                    else:
                        new_value = raw_value
                        try:
                            if pd.api.types.is_integer_dtype(current[col].dtype):
                                parsed = pd.to_numeric(raw_value, errors="raise")
                                if float(parsed).is_integer():
                                    new_value = int(parsed)
                                else:
                                    conversion_warnings.append(f"{col}: '{raw_value}' is not an integer.")
                                    continue
                            elif pd.api.types.is_float_dtype(current[col].dtype):
                                new_value = float(pd.to_numeric(raw_value, errors="raise"))
                            elif pd.api.types.is_datetime64_any_dtype(current[col].dtype):
                                new_value = pd.to_datetime(raw_value, errors="raise")
                        except Exception:
                            conversion_warnings.append(f"{col}: could not convert '{raw_value}' to the column data type.")
                            continue

                    old_missing = pd.isna(old_value)
                    new_missing = pd.isna(new_value)
                    same = old_missing and new_missing
                    if not old_missing and not new_missing:
                        same = str(old_value) == str(new_value)
                    if not same:
                        proposed.at[row_index, col] = new_value
                        changed_count += 1

            st.session_state.pending = proposed
            st.session_state.pending_log = [
                f"Manual editor: proposed {changed_count} changed error cell(s); protected non-error cells were not modified."
            ]
            if conversion_warnings:
                st.session_state.pending_log.extend(conversion_warnings)
            st.rerun()

    st.info(
        "Only detected error cells are editable. Non-error cells are displayed as read-only, "
        "and the app independently blocks changes to them before creating the proposal. "
        "Nothing is applied until you approve it in the Cleaning Approval tab."
    )
with tabs[3]:
    st.subheader("Automatic Cleaning Review")
    st.write("Choose which cleaning checks should run. Enabled checks run automatically and produce one combined preview. Exact duplicate removal and missing-value handling are available as explicit options.")
    st.caption("Safe transformations are proposed automatically. Validation warnings, outliers and fuzzy matches are reported without guessing or silently changing uncertain values.")
    with st.expander("Cleaning options", expanded=True):
        st.markdown("**Text, type and date cleanup**")
        opt_cols = st.columns(2)
        cleaning_options = {
            "whitespace": opt_cols[0].checkbox("Trim extra whitespace", value=True, key="opt_whitespace"),
            "type_conversion": opt_cols[0].checkbox("Convert numeric-like text / number words to numbers", value=True, key="opt_type_conversion"),
            "convert_numeric_to_text": opt_cols[0].checkbox("Convert numeric columns to text", value=False, key="opt_numeric_to_text"),
            "category": opt_cols[0].checkbox("Standardize category values", value=True, key="opt_category"),
            "dates": opt_cols[0].checkbox("Convert date-like columns (review first)", value=True, key="opt_dates"),
            "validation": opt_cols[1].checkbox("Validate data types and ranges", value=True, key="opt_validation"),
            "email_validation": opt_cols[1].checkbox("Validate email formats", value=True, key="opt_email_validation"),
            "outliers": opt_cols[1].checkbox("Detect numeric outliers (IQR)", value=True, key="opt_outliers"),
            "duplicates": opt_cols[1].checkbox("Remove exact duplicate rows", value=True, key="opt_duplicates"),
            "fuzzy": opt_cols[1].checkbox("Suggest fuzzy matches (no auto-merge)", value=True, key="opt_fuzzy"),
        }
        st.markdown("**Empty rows, columns and constant columns**")
        struct_cols = st.columns(2)
        cleaning_options["remove_rows_any_missing"] = struct_cols[0].checkbox("Remove rows containing any missing value", value=False, key="opt_remove_rows_missing")
        cleaning_options["remove_fully_empty_rows"] = struct_cols[0].checkbox("Remove rows that are completely empty", value=False, key="opt_remove_empty_rows")
        cleaning_options["remove_fully_empty_columns"] = struct_cols[1].checkbox("Remove columns that are completely empty", value=False, key="opt_remove_empty_columns")
        cleaning_options["remove_constant_columns"] = struct_cols[1].checkbox("Remove constant columns (one unique value)", value=False, key="opt_remove_constant_columns")

        st.markdown("**Missing-value strategy**")
        cleaning_options["fill_missing_instead_delete_rows"] = st.checkbox(
            "Fill missing values instead of deleting rows", value=False, key="opt_fill_missing",
            help="When enabled, filling takes priority over the remove-rows option. Preview the changes before applying."
        )
        fill_cols = st.columns(2)
        cleaning_options["numeric_fill_strategy"] = fill_cols[0].selectbox("Numeric fill strategy", ["Median", "Custom value"], index=0, key="opt_numeric_fill_strategy")
        cleaning_options["custom_numeric_fill_value"] = fill_cols[0].number_input("Custom numeric fill value", value=0.00, key="opt_custom_numeric_fill", format="%.2f")
        cleaning_options["text_fill_strategy"] = fill_cols[1].selectbox("Text/category fill strategy", ["Mode", "Custom value"], index=0, key="opt_text_fill_strategy")
        cleaning_options["custom_text_fill_value"] = fill_cols[1].text_input("Custom text fill value", value="Unknown", key="opt_custom_text_fill")
        cleaning_options["missing_action"] = "Flag missing values only" if st.checkbox("Only flag missing values (do not fill or delete)", value=False, key="opt_flag_missing") else "Keep missing values"
        st.caption("If 'Fill missing values instead of deleting rows' is enabled, fill strategies are used. Otherwise, the 'Remove rows containing any missing value' option controls row deletion.")
    if st.button("🔍 Run automatic cleaning review", type="primary", use_container_width=True):
        proposed, log, findings = automatic_cleaning_proposal(current, cleaning_options)
        st.session_state.pending = proposed
        st.session_state.pending_log = log
        st.session_state.auto_findings = findings
        st.rerun()
    findings=st.session_state.get("auto_findings")
    if findings is not None and not findings.empty:
        st.markdown("### Validation & fuzzy-match findings")
        st.dataframe(findings, use_container_width=True, hide_index=True)
    if st.session_state.pending is not None:
        st.markdown("### Proposed changes — before / after")
        st.write("\n".join([f"- {x}" for x in st.session_state.get("pending_log",[])]))
        st.write("**Current data**")
        st.dataframe(current.head(20), use_container_width=True)
        st.write("**Proposed data**")
        st.dataframe(st.session_state.pending.head(20), use_container_width=True)
        left,right=st.columns(2)
        if left.button("✅ Approve & Apply",type="primary",use_container_width=True):
            st.session_state.current=st.session_state.pending.copy(deep=True)
            st.session_state.actions += st.session_state.get("pending_log",[])
            st.session_state.pending=None
            st.session_state.pending_log=[]
            st.session_state.manual_edit_version += 1
            st.success("Approved changes applied to the working copy.")
            st.rerun()
        if right.button("❌ Reject proposal",use_container_width=True):
            st.session_state.pending=None
            st.session_state.pending_log=[]
            st.info("Proposal rejected. Current data was not changed.")
            st.rerun()
with tabs[4]:
    st.subheader("Before / after quality dashboard")
    om=metrics(original); cm=metrics(current)
    left,right=st.columns(2)
    with left: st.markdown("**Original dataset**"); st.json(om)
    with right: st.markdown("**Current approved dataset**"); st.json(cm)
    comparison_keys = ["Rows", "Columns", "Missing cells", "Duplicate rows", "Whitespace cells", "Invalid email formats", "Unparseable dates", "Possible numeric mismatches", "Indicative quality score"]
    comp=pd.DataFrame({"Metric":comparison_keys,"Original":[om[k] for k in comparison_keys],"Current":[cm[k] for k in comparison_keys]})
    st.dataframe(comp,use_container_width=True, hide_index=True)
    issue_chart_keys = ["Missing cells", "Duplicate rows", "Whitespace cells", "Invalid email formats", "Unparseable dates", "Possible numeric mismatches"]
    issue_chart = comp[comp["Metric"].isin(issue_chart_keys)].set_index("Metric")[["Original", "Current"]]
    st.markdown("#### Issue-count comparison")
    st.bar_chart(issue_chart)
    st.caption("The indicative score normalizes detected issue instances by cell count. A cell can trigger more than one rule, so issue instances are not the same as unique affected cells. This is a project metric, not an industry standard.")
    st.markdown("#### Inspect a dashboard metric")
    st.caption("Select an issue card to open its detailed row/column findings.")
    detail_data = issue_details_for(current)
    metric_cards = [
        ("Missing values", cm["Missing cells"], "Missing value"),
        ("Duplicate rows", cm["Duplicate rows"], "Duplicate row"),
        ("Whitespace", cm["Whitespace cells"], "Leading/trailing whitespace"),
        ("Email format", cm["Invalid email formats"], "Invalid email format"),
        ("Unparseable dates", cm["Unparseable dates"], "Unparseable date"),
        ("Numeric mismatches", cm["Possible numeric mismatches"], "Possible numeric type mismatch"),
    ]
    selected_filter = st.session_state.get("dashboard_issue_filter", "All issues")
    metric_cols = st.columns(3)
    for i, (label, count, issue_type) in enumerate(metric_cards):
        with metric_cols[i % 3]:
            if st.button(f"{label}: {count}", key=f"dashboard_issue_{i}", use_container_width=True):
                st.session_state.dashboard_issue_filter = issue_type
                selected_filter = issue_type
    if st.button("Show all issue findings", key="dashboard_all_issues"):
        st.session_state.dashboard_issue_filter = "All issues"
        selected_filter = "All issues"
    if not detail_data.empty:
        filtered_details = detail_data if selected_filter == "All issues" else detail_data[detail_data["Issue"] == selected_filter]
        st.markdown(f"**Detailed findings: {selected_filter}**")
        st.dataframe(filtered_details, use_container_width=True, hide_index=True)
    else:
        st.success("No detailed issue findings remain in the current dataset.")
with tabs[5]:
    st.subheader("Reports & Downloads")
    issue=issues_for(current)
    report={"project":"Universal Data Quality & Auto-Cleaning Engine","source":st.session_state.source_name,"generated_at":datetime.now().isoformat(timespec="seconds"),"original_metrics":metrics(original),"current_metrics":metrics(current),"approved_actions":st.session_state.actions,"remaining_issues":issue.to_dict(orient="records")}
    st.download_button("⬇️ Download cleaned CSV",current.to_csv(index=False).encode("utf-8"),"cleaned_data.csv","text/csv")
    st.download_button("⬇️ Download quality report (JSON)",json.dumps(report,indent=2,default=str).encode("utf-8"),"quality_report.json","application/json")
    st.download_button("⬇️ Download remaining issues (CSV)",issue.to_csv(index=False).encode("utf-8"),"remaining_issues.csv","text/csv")
    excel=io.BytesIO()
    with pd.ExcelWriter(excel,engine="openpyxl") as writer:
        current.to_excel(writer,index=False,sheet_name="Cleaned Data")
        issue.to_excel(writer,index=False,sheet_name="Remaining Issues")
        pd.DataFrame({"Approved Action":st.session_state.actions}).to_excel(writer,index=False,sheet_name="Action Log")
        comparison_keys = ["Rows", "Columns", "Missing cells", "Duplicate rows", "Whitespace cells", "Invalid email formats", "Unparseable dates", "Possible numeric mismatches", "Indicative quality score"]
        comp=pd.DataFrame({"Metric":comparison_keys,"Original":[metrics(original)[k] for k in comparison_keys],"Current":[metrics(current)[k] for k in comparison_keys]})
        comp.to_excel(writer,index=False,sheet_name="Comparison")
    st.download_button("⬇️ Download Excel workbook",excel.getvalue(),"cleaned_data_report.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.write("Approved actions"); st.write(st.session_state.actions if st.session_state.actions else "No cleaning actions approved yet.")


st.divider()
st.caption("Universal Data Quality & Auto-Cleaning Engine • Local prototype • Review every proposed change before approval")
