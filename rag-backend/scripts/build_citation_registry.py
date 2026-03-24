import json
import os
import sys
from pathlib import Path
import openai
from pydantic import BaseModel
from typing import List, Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import OPENAI_API_KEY, LLM_MODEL, DATA_DIR, CHUNKS_PATH, LOCAL_DATA_ROOT

client = openai.OpenAI(api_key=OPENAI_API_KEY)

CHUNKS_FILE = Path(LOCAL_DATA_ROOT) / CHUNKS_PATH
REGISTRY_PATH = Path(LOCAL_DATA_ROOT) / "data" / "citation_registry.json"

class CitationEntry(BaseModel):
    Type: str # e.g., "Section", "Notification", "Rule", "Circular"
    Law: Optional[str] = None # e.g., "CGST Act", "IGST Act"
    Citation: str # e.g., "Section 22", "Notification No. 13/2017-Central Tax (Rate)"
    Title: Optional[str] = None # e.g., "Persons liable for registration"
    Text: str # The exact verbatim text

class CitationList(BaseModel):
    citations: List[CitationEntry]

def extract_citations_from_chunk(text: str) -> List[dict]:
    """Uses LLM to extract verbatim statutory text into structured citations."""
    prompt = f"""
    You are an expert Indian Legal Data Engineer. Your task is to extract EVERY SINGLE governing statutory provision, rule, notification, or circular from the provided text verbatim.

    TEXT TO ANALYZE:
    {text}

    EXTRACTION RULES:
    1. Extract the exact, verbatim text of the law. DO NOT summarizing.
    2. Identify the 'Type' (Section, Rule, Notification, Circular, Schedule).
    3. Identify the 'Law' (CGST Act, IGST Act, CGST Rules).
    4. Provide the exact 'Citation' (e.g., Section 22, Rule 43).
    5. Provide the 'Title' if available (e.g., "Persons liable for registration").
    6. Include the exact 'Text' of the provision. Do not truncate to less than the full available clause.
    7. ONLY output structured data for actual legal provisions. Do not extract general commentary or explanations.

    Extract and output strictly according to the requested JSON schema. If no explicit legal provisions are found, return an empty list.
    """

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini", # Use mini for speed/cost on large text processing, but strict schema
            messages=[
                {"role": "system", "content": "You are an automated strict legal text extraction pipeline."},
                {"role": "user", "content": prompt}
            ],
            response_format=CitationList,
            temperature=0.0
        )
        return [c.model_dump() for c in completion.choices[0].message.parsed.citations]
    except Exception as e:
        print(f"Error extracting citations: {e}")
        return []

def run_extraction():
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY required for extraction.")
        return

    if not CHUNKS_FILE.exists():
        print(f"ERROR: No chunks found at {CHUNKS_FILE}. Run ingestion first.")
        return

    registry = []
    processed_citations = set()

    print(f"Reading chunks from: {CHUNKS_FILE}")
    
    with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    print(f"Starting extraction over {len(lines)} chunks...")
    
    for i, line in enumerate(lines):
        try:
            chunk = json.loads(line)
            text = chunk.get("text", "")
            if len(text) < 100:
                continue # Skip very small chunks likely without meat
                
            print(f"  Processing chunk {i+1}/{len(lines)}...")
            new_citations = extract_citations_from_chunk(text)
            
            for cit in new_citations:
                # Basic deduplication by Citation key
                key = f"{cit.get('Law', '')} - {cit.get('Citation', '')}"
                if key not in processed_citations and cit.get("Citation"):
                    registry.append(cit)
                    processed_citations.add(key)
                    print(f"    -> Extracted: {key}")
                    
        except json.JSONDecodeError:
            print(f"  Skipping invalid JSON on line {i+1}")
            continue

    print(f"\nExtraction complete. Found {len(registry)} unique legal provisions.")
    
    # Save to JSON
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=4, ensure_ascii=False)
        
    print(f"Verified Citation Registry saved to: {REGISTRY_PATH}")

if __name__ == "__main__":
    run_extraction()
