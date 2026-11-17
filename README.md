# Universal Data Quality & Auto-Cleaning Engine

A Python-based data quality application designed to identify data issues, evaluate cleaning opportunities, and support review-based data cleaning workflows.

## Project Overview

The Universal Data Quality & Auto-Cleaning Engine helps users inspect datasets and identify common data quality problems before using data for analysis or reporting.

The project focuses on making data cleaning more structured by combining quality checks with a review-based workflow.

## Key Features

- **Data Quality Checks:** Identify common data issues in datasets.
- **Missing Value Detection:** Detect missing or null values.
- **Duplicate Detection:** Identify duplicate records.
- **Invalid Data Checks:** Help identify potentially invalid data.
- **Review-Based Cleaning:** Support approval or rejection of proposed cleaning actions.
- **Action Logging:** Maintain a record of cleaning decisions, where implemented.

## Technology Stack

- Python
- Pandas
- Streamlit
- CSV

## Project Structure

```text
Universal-Data-Quality-Engine/
│
├── .streamlit/
│   └── config.toml
│
├── tests/
│   └── test_quality_engine.py
│
├── app.py
├── quality_engine.py
├── sample_data.csv
├── requirements.txt
├── CHANGELOG.md
├── TESTING_GUIDE_HINGLISH.txt
└── README.md
```

## Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/Shubhampandit2410/Universal-Data-Quality-Engine.git
```

### 2. Open the project directory

```bash
cd Universal-Data-Quality-Engine
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Run the Application

```bash
streamlit run app.py
```

Open the local URL displayed in your terminal to access the application.

## Testing

Run the project's tests using:

```bash
pytest
```

Refer to `TESTING_GUIDE_HINGLISH.txt` for additional testing instructions.

## Sample Dataset

The repository includes `sample_data.csv` for trying the application with sample data.

## Learning Objectives

This project demonstrates practical concepts related to:

- Data quality assessment
- Data cleaning workflows
- Python-based data processing
- Dataset validation
- Review and approval workflows

## Future Improvements

- Support for additional file formats.
- More advanced validation rules.
- Expanded automated data quality reports.
- Improved testing coverage.

## Author

**Shubham Mishra**

GitHub: [Shubhampandit2410]
