# Change log

## Updated academic package (29 October 2026)

- Separated reusable inspection functions into `quality_engine.py`.
- Added detailed issue evidence: row, column, original value, issue type and suggested action.
- Fixed manual editor behaviour so duplicate-row status alone does not make every cell editable.
- Made numeric/date conversion more conservative: invalid non-empty values are preserved by skipping conversion instead of being silently converted to missing values.
- Expanded dashboard metrics and separated issue-count chart categories from row/column counts.
- Added five unit tests for quality helper behaviour.
- Limited the advertised Excel input to `.xlsx`; legacy `.xls` is not enabled in this dependency set.
- Increased Streamlit upload cap from 200 MB to 10 GB (10240 MB). Actual processing of 10 GB files is not guaranteed because the current app loads the full file into memory; chunked/streaming processing and benchmarking remain necessary.
- Reworked the report, synopsis, approval/weekly templates and 20-slide presentation.
- Added architecture, DFD, UML-style, sequence/collaboration and illustrative UI wireframe diagrams.

## Verification status

- `python -m py_compile app.py quality_engine.py`: passed.
- `python -m unittest discover -s tests -v`: 5 passed.
- Streamlit UI end-to-end upload/approval/export: pending verification on the student's Windows machine.
- Fixed KPI/metric cards appearing blank in some Streamlit themes by explicitly setting high-contrast label, value, and delta text colors.

## Cleaning Review enhancement — number words
- Added detection for English number words in numeric-context columns, e.g. `Age = "twenty"`.
- Added a separate opt-in Cleaning Review action: “Convert English number words (e.g. twenty → 20)”.
- Supports conservative English forms such as zero–ninety-nine and common hundred/thousand/million combinations.
- Conversion remains preview-first and requires explicit **Approve & Apply**. If any non-empty value in a candidate column cannot be parsed, the column is preserved unchanged.
- Added a regression test for number-word parsing and detection.


## Automatic Cleaning Review expansion
- Replaced individual cleaning option checkboxes with one automatic review action.
- Added conservative case-only category standardization and automatic numeric/number-word conversion when a numeric-context column fully parses.
- Added age-range validation, invalid date findings, IQR outlier flags, and fuzzy text-match suggestions.
- Fuzzy matches and suspicious values are findings only; they are not silently changed. Exact duplicate removal remains a proposal requiring user approval.
- Approval/rejection workflow retained to protect original data.

## 2026-10-29 — Automatic review and team-document update
- Clarified single-pass automatic cleaning review (no per-feature checkboxes; one overall approval/rejection).
- Restricted category case normalization to likely categorical columns and excluded names, identifiers, email and free text.
- Updated report, synopsis and presentation to describe smart conversion, validation, outlier review, fuzzy match suggestions, dashboard comparison and export/audit behavior.
- Added four-person team structure with Team Leader / Head of Team role; names and roll numbers remain placeholders because official details were not supplied.
- Corrected stale upload-limit wording: 10 GB is configured, but memory-bound processing is not guaranteed at that size.

## Expanded Cleaning Review options
- Restored the exact duplicate removal option as an explicit cleaning proposal.
- Added missing-value handling choices: keep, flag only, remove rows containing missing values, or fill numeric columns with median and text columns with mode.
- Added email-format validation findings.
- Kept fuzzy matches as suggestions only; similar values are never auto-merged or deleted.
- All proposed changes remain subject to the combined before/after preview and user approval.


## Consolidated review update
- Preserved selectable cleaning options while adding/retaining smart type conversion, category standardization, date conversion, validation, outlier detection, fuzzy-match suggestions, email validation, duplicate handling, and missing-value strategies.
- Date conversion is conservative and should be reviewed for ambiguous locale-specific formats.
- Report formatting compacted to reduce excessive paragraph and heading gaps; date conversion and Cleaning Review descriptions clarified.


## Cleaning Review options restored/expanded (2026-10-29)
- Added separate controls for rows with any missing values, completely empty rows, completely empty columns, and constant columns.
- Added numeric median/custom fill and text/category mode/custom fill strategies, with configurable custom values (defaults 0.00 and Unknown).
- Added explicit fill-missing-instead-of-deleting-rows switch.
- Added numeric-to-text option and clarified date-like conversion preview workflow.
- Updated Hinglish README with exact purpose and caution for each option.
