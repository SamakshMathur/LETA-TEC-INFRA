import openai
from app.config import OPENAI_API_KEY, LLM_MODEL

client = openai.OpenAI(api_key=OPENAI_API_KEY)

def refine_query(raw_query: str) -> str:
    """
    Uses LLM to correct spelling, expand acronyms, and clarify incomplete queries
    BEFORE retrieving documents.
    """
    system_prompt = """
    You are a GST Search Optimizer.
    Your task is to REWRITE the user's search query for better retrieval.
    
    RULES:
    1. Correct spelling mistakes (e.g., "reverce charge" -> "reverse charge").
    2. Expand standard GST acronyms (e.g., "ITC" -> "Input Tax Credit").
    3. If the query is incomplete but intent is clear, complete it (e.g., "rate for mobile" -> "GST rate for mobile phones").
    4. Do NOT answer the question. Only output the CLEANED query.
    5. Maintain the original intent strictness.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Fast & Cheap for simple rewriting
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_query}
            ],
            temperature=0
        )
        refined_query = response.choices[0].message.content.strip()
        # Fallback if empty
        if not refined_query:
            return raw_query
        return refined_query
    except Exception as e:
        print(f"Query Refinement Failed: {e}")
        return raw_query

import json
def generate_advanced_queries(raw_query: str) -> dict:
    """
    Generates 3 diverse query angles for Multi-Query Expansion and
    1 Hypothetical Document Embedding (HyDE) string for dense vector matching.
    """
    system_prompt = """
    You are an advanced expert in Indian GST Law.
    Your objective is to optimize a user query for a vector database search.
    Output a valid JSON object with EXACTLY two keys:
    1. "queries": A list of exactly 3 distinct, highly technical search queries derived from the user's raw query. Cover different angles (e.g., Section numbers, specific rules, terminology).
    2. "hyde_document": A 3 to 4 sentence hypothetical, perfect legal answer to the user's query. It should use the dense, formal vocabulary and phrasing of official GST Acts, Rules, or Notifications.

    Return ONLY the raw JSON object. Do not include markdown formatting like ```json ... ```.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_query}
            ],
            temperature=0.2,
            response_format={ "type": "json_object" }
        )
        content = response.choices[0].message.content.strip()
        result = json.loads(content)
        
        # Ensure correct structure
        if "queries" not in result or not isinstance(result["queries"], list):
            result["queries"] = [raw_query]
        if "hyde_document" not in result:
            result["hyde_document"] = ""
            
        return result
    except Exception as e:
        print(f"Advanced Query Generation Failed: {e}")
        return {"queries": [raw_query], "hyde_document": ""}
