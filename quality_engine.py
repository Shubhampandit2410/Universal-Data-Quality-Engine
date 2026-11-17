"""Quality inspection helpers for Universal Data Quality & Auto-Cleaning Engine.

These functions inspect data and never modify the caller's DataFrame.
"""
import pandas as pd
import numbers


_NUMBER_SMALL = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_NUMBER_SCALES = {"hundred": 100, "thousand": 1000, "million": 1000000}
_NUMERIC_NAME_HINTS = ("age", "year", "score", "mark", "amount", "price", "cost", "quantity", "qty", "count", "number", "num", "salary", "height", "weight", "rating", "total", "value", "duration", "days", "months", "hours", "quantity")

def parse_number_word(value):
    """Parse a conservative subset of English number words; return None if unsupported."""
    if not isinstance(value, str):
        return None
    words = value.strip().lower().replace("-", " ").replace(",", "").split()
    words = [w for w in words if w != "and"]
    if not words or any(w not in _NUMBER_SMALL and w not in _NUMBER_SCALES for w in words):
        return None
    total = current = 0
    for word in words:
        if word in _NUMBER_SMALL:
            current += _NUMBER_SMALL[word]
        elif word == "hundred":
            current = max(current, 1) * 100
        else:
            total += max(current, 1) * _NUMBER_SCALES[word]
            current = 0
    return total + current

def is_numeric_context(column, values):
    """Avoid converting arbitrary category labels; require a numeric-looking column."""
    name_hint = any(token in str(column).lower() for token in _NUMERIC_NAME_HINTS)
    parsed_numeric = pd.to_numeric(values, errors="coerce")
    parsed_words = values.map(parse_number_word)
    ratio = (parsed_numeric.notna() | parsed_words.notna()).sum() / max(len(values), 1)
    return name_hint or ratio >= 0.5

def _display_row(index):
    """Use human-friendly one-based row numbers for the displayed table."""
    return int(index) + 1 if isinstance(index, numbers.Integral) else str(index)


def issues_for(df):
    out=[]
    for c in df.columns:
        n=int(df[c].isna().sum())
        if n: out.append({"Issue":"Missing values","Column":str(c),"Count":n,"Recommendation":"Choose a fill strategy or leave unchanged"})
        if pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c]):
            s=df[c].dropna().astype(str)
            spaces=int((s != s.str.strip()).sum())
            if spaces: out.append({"Issue":"Leading/trailing spaces","Column":str(c),"Count":spaces,"Recommendation":"Trim whitespace"})
            if "email" in str(c).lower() or "mail" in str(c).lower():
                bad=int((~s.str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")).sum())
                if bad: out.append({"Issue":"Invalid email format","Column":str(c),"Count":bad,"Recommendation":"Review manually; do not guess address"})
            if any(k in str(c).lower() for k in ["date","dob","joined","created"]):
                parsed=pd.to_datetime(s,errors="coerce")
                bad=int(parsed.isna().sum())
                if bad: out.append({"Issue":"Unparseable dates","Column":str(c),"Count":bad,"Recommendation":"Review date formats before conversion"})
            non=s.dropna()
            if len(non)>0:
                numeric=pd.to_numeric(non,errors="coerce")
                word_numbers=non.map(parse_number_word)
                if is_numeric_context(c, non):
                    word_mask = numeric.isna() & word_numbers.notna()
                    bad_mask = numeric.isna() & word_numbers.isna()
                    if word_mask.any():
                        out.append({"Issue":"Number written as text","Column":str(c),"Count":int(word_mask.sum()),"Recommendation":"Convert supported English number words to numeric values after preview/approval"})
                    if (numeric.notna() | word_numbers.notna()).any() and bad_mask.any():
                        out.append({"Issue":"Possible numeric type mismatch","Column":str(c),"Count":int(bad_mask.sum()),"Recommendation":"Review unsupported values manually; do not silently replace them"})
    dups=int(df.duplicated().sum())
    if dups: out.append({"Issue":"Duplicate rows","Column":"(entire row)","Count":dups,"Recommendation":"Remove exact duplicate rows"})
    return pd.DataFrame(out,columns=["Issue","Column","Count","Recommendation"])

def issue_details_for(df):
    """Return row-level evidence for supported issues without modifying data."""
    records = []
    for col in df.columns:
        series = df[col]
        col_name = str(col)
        for idx in df.index[series.isna()]:
            records.append({"Row": _display_row(idx), "Column": col_name,
                            "Original value": "<MISSING>", "Issue": "Missing value",
                            "Suggested action": "Review: fill with an approved strategy or keep missing"})
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            text = series.dropna().astype(str)
            space_mask = text.ne(text.str.strip())
            for idx, value in text[space_mask].items():
                records.append({"Row": _display_row(idx), "Column": col_name,
                                "Original value": value, "Issue": "Leading/trailing whitespace",
                                "Suggested action": "Trim whitespace after review"})
            if "email" in col_name.lower() or "mail" in col_name.lower():
                bad_mask = ~text.str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
                for idx, value in text[bad_mask].items():
                    records.append({"Row": _display_row(idx), "Column": col_name,
                                    "Original value": value, "Issue": "Invalid email format",
                                    "Suggested action": "Correct manually; the app cannot infer the real address"})
            if any(k in col_name.lower() for k in ["date", "dob", "joined", "created"]):
                parsed = pd.to_datetime(text, errors="coerce")
                bad_mask = parsed.isna()
                for idx, value in text[bad_mask].items():
                    records.append({"Row": _display_row(idx), "Column": col_name,
                                    "Original value": value, "Issue": "Unparseable date",
                                    "Suggested action": "Choose/confirm a date format or correct manually"})
            if len(text):
                numeric = pd.to_numeric(text, errors="coerce")
                word_numbers = text.map(parse_number_word)
                if is_numeric_context(col_name, text) and (numeric.notna() | word_numbers.notna()).any():
                    bad_mask = numeric.isna() & word_numbers.isna()
                    for idx, value in text[bad_mask].items():
                        records.append({"Row": _display_row(idx), "Column": col_name,
                                        "Original value": value, "Issue": "Possible numeric type mismatch",
                                        "Suggested action": "Review value; supported English number words can be converted (e.g. twenty → 20)"})
                    word_mask = numeric.isna() & word_numbers.notna()
                    for idx, value in text[word_mask].items():
                        records.append({"Row": _display_row(idx), "Column": col_name,
                                        "Original value": value, "Issue": "Number written as text",
                                        "Suggested action": f"Convert to numeric value {word_numbers.loc[idx]} after approval"})
    dup_mask = df.duplicated(keep=False)
    for idx in df.index[dup_mask]:
        records.append({"Row": _display_row(idx), "Column": "(entire row)",
                        "Original value": "Full row matches another row", "Issue": "Duplicate row",
                        "Suggested action": "Review duplicate group; remove only if appropriate"})
    return pd.DataFrame(records, columns=["Row", "Column", "Original value", "Issue", "Suggested action"])

def cell_errors_for(df):
    """Boolean DataFrame: True only for cells that have a detected quality issue."""
    errors = pd.DataFrame(False, index=df.index, columns=df.columns)
    errors |= df.isna()

    for col in df.columns:
        series = df[col]
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            text = series.dropna().astype(str)

            bad_space = text != text.str.strip()
            if bad_space.any():
                errors.loc[text.index[bad_space], col] = True

            if "email" in str(col).lower() or "mail" in str(col).lower():
                bad_email = ~text.str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
                if bad_email.any():
                    errors.loc[text.index[bad_email], col] = True

            if any(k in str(col).lower() for k in ["date", "dob", "joined", "created"]):
                bad_dates = pd.to_datetime(text, errors="coerce").isna()
                if bad_dates.any():
                    errors.loc[text.index[bad_dates], col] = True

            if len(text):
                numeric = pd.to_numeric(text, errors="coerce")
                word_numbers = text.map(parse_number_word)
                if is_numeric_context(col, text):
                    bad_numeric = numeric.isna() & word_numbers.isna()
                    word_numeric = numeric.isna() & word_numbers.notna()
                    if bad_numeric.any(): errors.loc[text.index[bad_numeric], col] = True
                    if word_numeric.any(): errors.loc[text.index[word_numeric], col] = True

    # Duplicate rows are row-level issues, not cell-level errors. Do not unlock
    # every cell in a duplicate row in the manual editor.
    return errors

def rows_with_errors(df):
    """Return rows containing at least one detected issue."""
    return cell_errors_for(df).any(axis=1)

def metrics(df):
    total_cells = max(int(df.shape[0] * df.shape[1]), 1)
    missing = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())
    whitespace = email_bad = date_bad = numeric_bad = 0
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            s = df[col].dropna().astype(str)
            whitespace += int((s != s.str.strip()).sum())
            if "email" in str(col).lower() or "mail" in str(col).lower():
                email_bad += int((~s.str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")).sum())
            if any(k in str(col).lower() for k in ["date", "dob", "joined", "created"]):
                date_bad += int(pd.to_datetime(s, errors="coerce").isna().sum())
            if len(s):
                numeric = pd.to_numeric(s, errors="coerce")
                word_numbers = s.map(parse_number_word)
                if is_numeric_context(col, s):
                    numeric_bad += int((numeric.isna() & word_numbers.isna()).sum())
    # Transparent project metric: issue instances are normalized by dataset size.
    issue_instances = missing + duplicate_rows + whitespace + email_bad + date_bad + numeric_bad
    score = max(0, min(100, round(100 * (1 - min(issue_instances / total_cells, 1)))))
    return {"Rows": len(df), "Columns": len(df.columns), "Missing cells": missing,
            "Duplicate rows": duplicate_rows, "Whitespace cells": whitespace,
            "Invalid email formats": email_bad, "Unparseable dates": date_bad,
            "Possible numeric mismatches": numeric_bad, "Indicative quality score": score}
