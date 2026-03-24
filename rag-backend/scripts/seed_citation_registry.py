import json
from pathlib import Path
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import LOCAL_DATA_ROOT

REGISTRY_PATH = Path(LOCAL_DATA_ROOT) / "data" / "citation_registry.json"

seed_data = [
    {
        "Type": "Section",
        "Law": "CGST Act",
        "Citation": "Section 22",
        "Title": "Persons liable for registration",
        "Text": "Every supplier shall be liable to be registered under this Act in the State or Union territory, other than special category States, from where he makes a taxable supply of goods or services or both, if his aggregate turnover in a financial year exceeds twenty lakh rupees."
    },
    {
        "Type": "Section",
        "Law": "CGST Act",
        "Citation": "Section 24",
        "Title": "Compulsory registration in certain cases",
        "Text": "(i) persons making any inter-State taxable supply; (ii) casual taxable persons making taxable supply; (iii) persons who are required to pay tax under reverse charge."
    },
    {
        "Type": "Rule",
        "Law": "CGST Rules",
        "Citation": "Rule 43",
        "Title": "Manner of determination of input tax credit in respect of capital goods and reversal thereof in certain cases",
        "Text": "Subject to the provisions of sub-section (3) of section 16, the input tax credit in respect of capital goods, which attract the provisions of sub-sections (1) and (2) of section 17, being partly used for the purposes of business and partly for other purposes, or partly used for effecting taxable supplies including zero rated supplies and partly for effecting exempt supplies, shall be attributed to the purposes of business or for effecting taxable supplies in the following manner..."
    },
    {
        "Type": "Notification",
        "Law": "CGST Act",
        "Citation": "Notification No. 13/2017-Central Tax (Rate)",
        "Title": "Reverse Charge Mechanism on certain specified services",
        "Text": "The Central Government on the recommendations of the Council hereby notifies that on categories of supply of services mentioned in column (2) of the Table below, supplied by a person as specified in column (3) of the said Table, the whole of central tax leviable under section 9 of the said Central Goods and Services Tax Act, shall be paid on reverse charge basis by the recipient of the such services as specified in column (4) of the said Table."
    }
]

def run_seed():
    """Seeds the foundational Citation Registry."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(seed_data, f, indent=4, ensure_ascii=False)
    print(f"Verified Citation Registry seeded successfully at: {REGISTRY_PATH}")
    print(f"Total Entries: {len(seed_data)}")

if __name__ == "__main__":
    run_seed()
