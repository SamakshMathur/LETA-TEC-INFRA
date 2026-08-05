import pandas as pd


def _read_with_best_header(path) -> pd.DataFrame:
    """
    Try header=0 first.  If ALL columns are "Unnamed", the real headers are
    probably on row 1 (a common pattern when the file has a merged title row
    above the column headers).  Retry with header=1 in that case.
    """
    df = pd.read_excel(path)
    all_unnamed = all("Unnamed" in str(c) for c in df.columns)
    if all_unnamed:
        # Row 0 is a blank / merged title — re-read with row 1 as header
        df = pd.read_excel(path, header=1)
    return df


def extract_text_from_excel(path):
    """
    CLEAN LEGAL EXCEL READER:
    - Auto-detects header row (handles files where headers are on row 1)
    - Filters out Unnamed columns and NaN values
    - Organises each row into a readable sentence
    """
    try:
        df = _read_with_best_header(path)
        rows = []

        for _, row in df.iterrows():
            # Keep named columns with actual values
            valid_pairs = [
                f"{col}: {row[col]}"
                for col in df.columns
                if pd.notna(row[col]) and "Unnamed" not in str(col)
            ]

            sentence = ". ".join(valid_pairs)

            if sentence.strip():
                rows.append({
                    "text": sentence,
                    "metadata": {
                        "source": str(path),
                        "type": "excel_data",
                    }
                })

        return rows
    except Exception as e:
        print(f"Excel extraction error for {path}: {e}")
        return []
