import pandas as pd

def extract_text_from_excel(path):
    """
    CLEAN LEGAL EXCEL READER:
    Filters out Unnamed columns and organizes data into readable sentences.
    """
    try:
        df = pd.read_excel(path)
        rows = []

        for _, row in df.iterrows():
            # Filter out "Unnamed" columns and NaN values
            valid_pairs = [f"{col}: {row[col]}" for col in df.columns 
                          if pd.notna(row[col]) and "Unnamed" not in str(col)]
            
            sentence = ". ".join(valid_pairs)

            if sentence.strip():
                rows.append({
                    "text": sentence,
                    "metadata": {
                        "source": str(path),
                        "type": "excel_data"
                    }
                })

        return rows
    except Exception as e:
        print(f"Excel extraction error for {path}: {e}")
        return []