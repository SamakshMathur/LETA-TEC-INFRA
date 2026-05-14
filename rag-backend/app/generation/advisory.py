import os
import hashlib
import json
from diskcache import Cache
from app.config import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    LLM_PROVIDER,
    LLM_MODEL,
    CLAUDE_MAIN_MODEL,
    CACHE_DIR,
    DATA_DIR
)
from app.generation.prompts.advisory_prompt import ADVISORY_SYSTEM_PROMPT
from app.generation.pdf_report import PDFReportGenerator
from app.routing.intent_classifier import classify_intent

# Initialize Cache
cache = Cache(CACHE_DIR)

# Initialize PDF Generator
# Reports go to RAG_INFORMATION_DATABASE/generated_reports for easy serving
REPORTS_DIR = os.path.join(DATA_DIR, "generated_reports")
pdf_gen = PDFReportGenerator(output_dir=REPORTS_DIR)

# Client setup — respect configured LLM provider
_client = None

def _get_client():
    global _client
    if _client is not None:
        return _client
    if LLM_PROVIDER == "anthropic":
        import anthropic
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    else:
        import openai
        _client = openai.OpenAI(api_key=OPENAI_API_KEY)
    return _client

def generate_legal_advisory(user_input: str, context: str, subject: str = "GST Query") -> dict:
    """
    Generates a formal Legal Advisory Opinion using GPT-4o-mini + Caching + PDF.
    Returns: {"content": str, "pdf_url": str}
    """
    
    # 1. Check Cache (Speed Engine)
    # Create a unique key based on the input
    query_hash = hashlib.md5((user_input + context[:100]).encode()).hexdigest()
    cache_key = f"advisory_{query_hash}"
    
    if cache_key in cache:
        print(f"Serving from Cache: {cache_key}")
        return cache[cache_key]

    # 1b. Classify Query (Autonomous Logic)
    intent_info = classify_intent(user_input)
    query_type = intent_info["intent"] # definition, section_advisory, rate_classification, comparison
    print(f"Query Classification: {query_type}")

    # 2. Format Prompt & Choose Template
    try:
        # Load Rules Engine
        from .rules_engine import rules_engine
        rules_text = rules_engine.get_all_rules_as_text()

        # Select Template - Always use the full detailed Advisory template as requested by the user
        base_prompt = ADVISORY_SYSTEM_PROMPT.format(
            subject=subject,
            rules_context=rules_text
        )
        
        system_prompt = base_prompt
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nUSER QUERY:\n{user_input}"}
        ]
        
        # 3. Call LLM (Intelligence Engine)
        client = _get_client()
        if LLM_PROVIDER == "anthropic":
            print(f"Calling Claude ({CLAUDE_MAIN_MODEL}) for {query_type}...")
            response = client.messages.create(
                model=CLAUDE_MAIN_MODEL,
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": f"CONTEXT:\n{context}\n\nUSER QUERY:\n{user_input}"}],
            )
            advisory_content = response.content[0].text.strip()
        else:
            print(f"Calling OpenAI ({LLM_MODEL}) for {query_type}...")
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                max_completion_tokens=4000,
            )
            advisory_content = response.choices[0].message.content.strip()

        # 4. Post-Processing Validation & Re-Generation (Self-Correction Layer)
        # Run validation for ALL query types to maximize accuracy
        if True:  # Always validate
            from .validator import validate_advisory, validate_logic_strict, validate_citations, validate_logic
            
            # We run the consolidated validator which now includes strict checks
            # But we need to separate the warning message from the content to check if we should regenerate.
            # Let's inspect validate_advisory again. It RETURNS content + warnings.
            # For the loop, we want the RAW warnings first.
            
            # Let's re-implement the granular check here for control.
            # A. Basic Checks
            citation_warnings = validate_citations(advisory_content, context)
            logic_warnings = validate_logic(advisory_content)
            strict_warnings = validate_logic_strict(advisory_content, rules_text)
            
            all_warnings = list(set(citation_warnings + logic_warnings + strict_warnings))
            
            if all_warnings:
                # Critical Step: Self-Correction Loop
                print(f"xx Validation Failed with {len(all_warnings)} issues. Attempting Auto-Correction...")
                
                correction_prompt = "Your previous draft had the following compliance issues:\n"
                for w in all_warnings:
                    correction_prompt += f"- {w}\n"
                correction_prompt += "\nPlease regenerate the Legal Advisory Opinion correcting these specific issues. Ensure NO contradictions and ALL statutory limits are respected."
                
                # Retry Call with self-correction
                if LLM_PROVIDER == "anthropic":
                    response_v2 = client.messages.create(
                        model=CLAUDE_MAIN_MODEL,
                        max_tokens=4000,
                        system=system_prompt,
                        messages=[
                            {"role": "user", "content": f"CONTEXT:\n{context}\n\nUSER QUERY:\n{user_input}"},
                            {"role": "assistant", "content": advisory_content},
                            {"role": "user", "content": correction_prompt},
                        ],
                    )
                    advisory_content = response_v2.content[0].text.strip()
                else:
                    messages.append({"role": "assistant", "content": advisory_content})
                    messages.append({"role": "user", "content": correction_prompt})
                    response_v2 = client.chat.completions.create(
                        model=LLM_MODEL,
                        messages=messages,
                        max_completion_tokens=4000,
                    )
                    advisory_content = response_v2.choices[0].message.content.strip()
                print(">> Auto-Correction Complete. Using V2 Draft.")

        # 5. Generate PDF (Output Engine)
        filename = f"Advisory_{query_hash[:8]}.pdf"
        pdf_path = pdf_gen.generate_report(advisory_content, filename=filename)
        
        # 5. Construct Result
        result = {
            "content": advisory_content,
            "pdf_url": f"/api/documents/view?category=reports&filename={filename}",
            "cached": False
        }

        # 6. Save to Cache
        if advisory_content and len(advisory_content) > 100:
            cache[cache_key] = {**result, "cached": True} # Mark as cached for next time
        else:
             print(f"DEBUG: Content too short/empty ({len(advisory_content)}). NOT CACHING.")
        
        return result

    except Exception as e:
        print(f"Error generating advisory: {e}")
        return {
            "content": f"## Error Generating Advisory\n\nWe encountered an issue: {str(e)}",
            "pdf_url": None
        }
