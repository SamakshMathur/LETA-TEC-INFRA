import pandas as pd

def extract_text_from_excel(path):
    df = pd.read_excel(path)
    rows = []

    for _, row in df.iterrows():
        sentence = ". ".join(
            f"{col} is {row[col]}"
            for col in df.columns
            if pd.notna(row[col])
        )

        if sentence.strip():
            rows.append({
                "text": sentence,
                "metadata": {
                    "source": str(path),
                    "type": "excel_row"
                }
            })

    return rows