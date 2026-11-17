UNIVERSAL DATA QUALITY & AUTO-CLEANING ENGINE
============================================

PROJECT RUN KARNE KE STEPS (WINDOWS)
1. Is folder ko extract karne ke baad open karo.
2. Folder ke address bar mein cmd type karo aur Enter dabao.
3. Python check karo:
   python --version
4. Libraries install karo:
   python -m pip install -r requirements.txt
5. App run karo:
   python -m streamlit run app.py
6. Browser mein Streamlit ka diya hua local URL kholo (usually http://localhost:8501).
7. Left sidebar se sample_data.csv upload karo aur Load / Replace dataset dabao.
8. Issues & Evidence tab mein row, column, original value aur suggested action dekho.
9. Cleaning Review tab mein options select karo aur Preview proposed cleaning dabao.
10. Proposed data check karo. Approve & Apply changes apply karega; Reject proposal changes ko discard karega.
11. Dashboard aur Reports & Downloads tabs check karo.

TESTS RUN KARNE KE LIYE
Folder ke andar CMD mein:
   python -m unittest discover -s tests -v
Syntax check:
   python -m py_compile app.py quality_engine.py

CURRENT BUILD KI LIMITS
- Supported input: CSV, XLSX, JSON aur SQLite database table.
- Legacy .xls enabled nahi hai; file ko .xlsx mein save karke use karo.
- Streamlit upload cap 10 GB (10240 MB) par configure kiya gaya hai. IMPORTANT: app abhi poori file memory mein load karta hai; 10 GB file process karne ke liye bahut zyada RAM chahiye aur current version mein successful processing guaranteed nahi hai. Reliable 10 GB processing ke liye chunked/streaming pipeline aur performance testing abhi bhi required hai.
- App current session ka dataset rakhta hai; naya upload purane active dataset ko replace karta hai.
- Processing history permanent database mein save nahi hoti.
- Streamlit browser flow aur actual file downloads ko apne Windows PC par run karke final verify karna zaroori hai.

IMPORTANT
- Source file disk par overwrite nahi hoti; cleaned output alag download hota hai.
- Email check sirf format check hai; mailbox ki existence verify nahi karta.
- Numeric/date conversion preview ko approve karne se pehle check karo.
- Student name, roll number, guide details aur signatures apne official records ke mutabik fill karo.
KPI blank-box fix: metric cards now force dark, high-contrast text in both light and dark Streamlit themes. If the old app is running, stop it with Ctrl+C and start it again from this updated folder.

NEW CLEANING REVIEW OPTION:
- “Convert English number words (e.g. twenty -> 20)” ko enable karne par Age jaise numeric columns mein “twenty” ko 20 propose kiya ja sakta hai.
- Pehle Preview proposed cleaning dekho; tabhi Approve & Apply karo.
- Agar column mein koi unsupported text value ho, poora column safe rakhne ke liye conversion skip hota hai. App kisi unknown word ka andaza nahi lagata.


AUTOMATIC CLEANING REVIEW (UPDATED)
- Per-feature checkboxes hata diye gaye hain: ek button se automatic review chalta hai.
- Safe transformations: whitespace trim, supported number-word/numeric conversion, case-only category standardization, safely parseable date conversion, exact duplicate removal proposal.
- Validation: age values outside 0–120 / non-numeric age, invalid dates, IQR statistical outliers are flagged.
- Fuzzy matching: similar text candidates are shown as suggestions; fuzzy matches are NOT auto-merged.
- Changes apply only after Approve & Apply. Reject keeps current dataset unchanged.
- 10 GB configuration does not guarantee 10 GB processing: current pandas/Streamlit flow is memory-bound and requires chunked architecture for genuine large-file support.


ENHANCED AUTOMATIC CLEANING REVIEW
- One combined automatic review pass; no per-feature checkboxes.
- Safe numeric/type conversion including supported English number words.
- Category normalization is limited to likely categorical columns.
- Date conversion occurs only when all non-empty values parse.
- Age/date validation, IQR outlier flags and fuzzy text candidates are findings, not guessed corrections.
- Exact duplicate removal is proposed for approval.
- Review before/after and use one Approve & Apply or Reject decision.
- Upload setting is 10 GB (10240 MB), but in-memory processing does not guarantee successful 10 GB processing.
- Team details: report/PPT include placeholders for four members; identify the Team Leader / Head and fill official names/roll numbers.

CLEANING REVIEW OPTIONS (latest update)
- Trim extra whitespace
- Smart type conversion (including supported number words such as twenty -> 20)
- Category standardization
- Date conversion
- Data validation (age/type/date)
- Outlier detection (IQR; flags only)
- Remove exact duplicate rows (proposed, preview first)
- Fuzzy matching suggestions (never auto-merge)
- Email format validation
- Missing-value strategy: keep, flag, remove rows containing missing values, or fill numeric median/text mode

All proposed changes are shown in a combined before/after preview. Approve & Apply is required before the working dataset changes. Review removal/fill proposals carefully before approval.


CLEANING REVIEW OPTIONS (latest update)
- Remove rows containing any missing value: removes every row with at least one blank/NA cell. Use only if losing partial rows is acceptable.
- Remove rows that are completely empty: removes rows where every column is blank/NA. Usually safe.
- Remove columns that are completely empty: removes columns with no non-missing values.
- Numeric fill strategy = Median: fills missing numeric cells with the median of that column; less sensitive to extreme values than mean.
- Custom numeric fill value = 0.00: fills missing numeric cells with 0.00. Use only when zero has real meaning; zero is not always the same as missing.
- Text/category fill strategy = Mode: fills missing text/category cells with the most frequent value in that column.
- Custom text fill value = Unknown: fills missing text/category cells with the entered text (default Unknown).
- Remove constant columns: removes columns with one unique non-missing value; consider whether a constant flag/feature is meaningful before removing.
- Convert date-like columns (review first): detects columns named with date/DOB/joined/created hints, and proposes conversion only when all non-empty values parse; inspect preview, especially ambiguous formats such as 03/04/2025.
- Convert numeric-like text to numbers: converts a text column only when values can be parsed safely; supported number words such as twenty become 20.
- Convert numeric columns to text: changes numeric column values to strings; use only for identifiers/codes or display/export needs, not calculations.
- Fill missing values instead of deleting rows: when enabled, filling takes priority over the remove-rows option; numeric and text strategies apply separately.
All changes are proposed on a copy. Check before/after preview and click Approve & Apply to change the working dataset. Reject proposal keeps current data unchanged.
