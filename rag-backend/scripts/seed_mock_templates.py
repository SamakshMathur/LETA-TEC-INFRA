import os
import sys
import json
import random

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_template_collection

MOCK_TEMPLATES = [
    {
        "title": "Reply to ITC Mismatch Notice (ASMT-10)",
        "category": "ITC",
        "sub_category": "mismatch",
        "stage": "Notice Reply",
        "keywords": ["ASMT-10", "ITC", "mismatch", "GSTR-2A", "GSTR-3B"],
        "summary": "Standard reply format for addressing discrepancies between ITC claimed in GSTR-3B and auto-populated in GSTR-2A.",
        "content": "To,\nThe Proper Officer,\n[Jurisdiction]\n\nSub: Reply to Notice in Form GST ASMT-10 dated [Date] for the period [Period].\n\nDear Sir/Madam,\n\nWe are in receipt of your notice... [Full legal draft content goes here...]"
    },
    {
        "title": "Appeal against Rejection of Refund Claim",
        "category": "Refund",
        "sub_category": "rejection",
        "stage": "Appeal",
        "keywords": ["Refund", "Appeal", "APL-01", "rejection", "unutilized ITC"],
        "summary": "Draft appeal (Form GST APL-01) against an order rejecting the claim for refund of accumulated ITC.",
        "content": "FORM GST APL-01\nAppeal to Appellate Authority\n\n...[Full appeal draft content]..."
    },
    {
        "title": "Reply to SCN for Cancellation of Registration",
        "category": "Registration",
        "sub_category": "cancellation",
        "stage": "Notice Reply",
        "keywords": ["Cancellation", "SCN", "REG-17", "Reply"],
        "summary": "Reply to a Show Cause Notice proposing the cancellation of GST registration for non-filing of returns.",
        "content": "To,\nThe Proper Officer,\n\nSub: Reply to SCN for Cancellation of Registration (Form GST REG-17)...\n\n[Full draft]"
    },
    {
        "title": "Application for Revocation of Cancellation of Registration",
        "category": "Registration",
        "sub_category": "revocation",
        "stage": "Application",
        "keywords": ["Revocation", "Cancellation", "REG-21"],
        "summary": "Formal application to revoke the cancellation of GST registration after compliance.",
        "content": "FORM GST REG-21\nApplication for Revocation of Cancellation of Registration..."
    },
    {
        "title": "Reply to Notice for Delay in Filing Returns (GSTR-3B)",
        "category": "Returns",
        "sub_category": "delay",
        "stage": "Notice Reply",
        "keywords": ["Delay", "Late Fee", "GSTR-3B", "Penalty"],
        "summary": "Response explaining the reasons for delayed filing of GSTR-3B and requesting waiver of penalty.",
        "content": "To the relevant assessing officer...\nSub: Delay in filing GSTR-3B..."
    },
    {
        "title": "Draft for Filing DRC-03 (Voluntary Payment)",
        "category": "Payment",
        "sub_category": "voluntary",
        "stage": "Intimation",
        "keywords": ["DRC-03", "Voluntary", "Tax Shortfall", "Payment"],
        "summary": "Format for intimating voluntary payment of tax shortfall or interest via DRC-03.",
        "content": "Intimation of payment made voluntarily or made against the SCN..."
    },
    {
        "title": "Appeal against Order imposing Penalty under Section 129",
        "category": "E-way Bill",
        "sub_category": "penalty",
        "stage": "Appeal",
        "keywords": ["Section 129", "Penalty", "E-way Bill", "Detention"],
        "summary": "Appeal memo challenging the detention of goods and imposition of penalty under Sec 129.",
        "content": "Appeal against order dated [Date] passed under Section 129..."
    },
    {
        "title": "Reply to SCN demanding Reversal of ITC for Non-payment to Supplier",
        "category": "ITC",
        "sub_category": "Rule 37",
        "stage": "Notice Reply",
        "keywords": ["Rule 37", "Reversal", "180 days", "Non-payment"],
        "summary": "Draft reply to notice asking for reversal of ITC due to failure to pay supplier within 180 days.",
        "content": "Reply to SCN regarding Rule 37..."
    },
    {
        "title": "Letter Requesting Unblocking of Electronic Credit Ledger",
        "category": "ITC",
        "sub_category": "blocking",
        "stage": "Request",
        "keywords": ["Rule 86A", "Blocked ITC", "Credit Ledger", "Unblocking"],
        "summary": "Application requesting the unblocking of ITC blocked under Rule 86A.",
        "content": "Request for unblocking of Electronic Credit Ledger..."
    },
    {
        "title": "Reply to SCN for Classification Dispute (HSN Code)",
        "category": "Classification",
        "sub_category": "dispute",
        "stage": "Notice Reply",
        "keywords": ["HSN", "Classification", "Rate of Tax", "SCN"],
        "summary": "Defense reply against the department's proposed change in HSN classification and higher tax rate.",
        "content": "Sub: Reply to SCN No. [X] regarding HSN classification..."
    },
    {
        "title": "Application for Advance Ruling (ARA-01)",
        "category": "Advance Ruling",
        "sub_category": "application",
        "stage": "Application",
        "keywords": ["AAR", "Advance Ruling", "ARA-01"],
        "summary": "Standard format for filing an application before the Authority for Advance Ruling.",
        "content": "FORM GST ARA-01\nApplication Form for Advance Ruling..."
    },
    {
        "title": "Reply to Audit Observations (ADT-01)",
        "category": "Audit",
        "sub_category": "observations",
        "stage": "Audit Reply",
        "keywords": ["Audit", "ADT-01", "Observations", "Departmental Audit"],
        "summary": "Detailed point-wise reply to the preliminary audit observations raised during departmental audit.",
        "content": "Point-wise reply to Audit Observations..."
    },
    {
        "title": "Reply to Notice for Transitional Credit Demand",
        "category": "Transitional Credit",
        "sub_category": "demand",
        "stage": "Notice Reply",
        "keywords": ["TRAN-1", "Transitional Credit", "Demand", "SCN"],
        "summary": "Defense reply to a notice demanding reversal or recovery of transitional credit claimed in TRAN-1.",
        "content": "Reply concerning TRAN-1 credit claims..."
    },
    {
        "title": "Appeal to Appellate Tribunal (CESTAT/GSTAT)",
        "category": "Appeal",
        "sub_category": "Tribunal",
        "stage": "Appeal",
        "keywords": ["Tribunal", "GSTAT", "Second Appeal", "APL-05"],
        "summary": "Format for filing a second appeal before the Appellate Tribunal against the Order-in-Appeal.",
        "content": "Appeal before the Hon'ble Tribunal..."
    },
    {
        "title": "Reply to Notice for Mismatch in E-way Bill and GSTR-1",
        "category": "E-way Bill",
        "sub_category": "mismatch",
        "stage": "Notice Reply",
        "keywords": ["E-way bill", "GSTR-1", "mismatch"],
        "summary": "Explanation for discrepancies between the turnover declared in GSTR-1 and E-way bill portal data.",
        "content": "Explanation for differences in GSTR-1 and E-way bill data..."
    }
]

def seed_database():
    print("Initializing Database Seeder...")
    collection = get_template_collection()
    
    if collection is None:
        print("Failed to connect to template collection.")
        return

    # Clear existing mock data to prevent duplicates on multiple runs
    print("Clearing existing templates...")
    collection.delete_many({})
    
    print(f"Seeding {len(MOCK_TEMPLATES)} mock templates...")
    
    docs_to_insert = []
    for t in MOCK_TEMPLATES:
        doc = t.copy()
        # Ensure we add a dummy embedding vector for now (length 3072 to match config)
        # Random noise so they have some vector distance variance
        doc["embedding"] = [random.uniform(-0.1, 0.1) for _ in range(3072)]
        docs_to_insert.append(doc)

    result = collection.insert_many(docs_to_insert)
    print(f"Successfully inserted {len(result.inserted_ids)} templates.")
    print("Database seeding complete!")

if __name__ == "__main__":
    seed_database()
