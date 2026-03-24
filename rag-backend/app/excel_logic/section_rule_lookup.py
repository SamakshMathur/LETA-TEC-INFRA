import re
import pandas as pd
from pathlib import Path

EXCEL_PATH = Path("data/raw/excel/Sections List.xlsx")


def extract_section_number(question: str) -> str | None:
    match = re.search(r"section\s+(\d+)", question.lower())
    if match:
        return match.group(1)
    return None


def find_rule_for_section(question: str) -> dict:
    section_no = extract_section_number(question)

    if not section_no:
        return {
            "found": False,
            "message": "No section number found in question."
        }

    # Read Excel
    df = pd.read_excel(EXCEL_PATH)

    # Drop fully empty rows
    df = df.dropna(how="all")

    # Column positions based on your file structure
    section_col = df.columns[0]
    topic_col = df.columns[1]
    rule_col = df.columns[3]

    # Normalize section column to extract digits only
    df["_section_clean"] = (
        df[section_col]
        .astype(str)
        .str.extract(r"(\d+)")
    )

    match = df[df["_section_clean"] == section_no]

    if match.empty:
        return {
            "found": False,
            "message": f"No rule found for Section {section_no}."
        }

    row = match.iloc[0]

    return {
        "found": True,
        "section": section_no,
        "topic": str(row[topic_col]),
        "rule": str(row[rule_col]),
        "source": "Sections List.xlsx"
    }
