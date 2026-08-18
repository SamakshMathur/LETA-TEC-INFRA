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
    DATA_DIR,
    PROMPT_VERSION,
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
    cache_key = f"advisory_{PROMPT_VERSION}_{query_hash}"
    
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

        # The prompt no longer uses {subject} — strip it cleanly
        system_prompt = ADVISORY_SYSTEM_PROMPT.format(rules_context=rules_text)

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # 3. Build the user message.
        # The client already provided section (a) — their understanding of the transaction.
        # We only produce section (b): "Our comments from GST perspective."
        # Keep the retrieved context tight (first 6000 chars) so the model focuses
        # on what's directly relevant rather than scanning a wall of text.
        trimmed_context = context[:6000] if len(context) > 6000 else context

        user_message = (
            "RETRIEVED STATUTORY CONTEXT (cite ONLY directly relevant provisions from here):\n"
            f"{trimmed_context}\n\n"
            "══════════════════════════════════════════════════════\n"
            "CLIENT'S QUERY — INCLUDING THEIR FACTUAL UNDERSTANDING:\n"
            "══════════════════════════════════════════════════════\n"
            f"{user_input}\n\n"
            "══════════════════════════════════════════════════════\n"
            "Produce ONLY section b) — 'Our comments from GST perspective:'\n"
            "• One bullet per distinct GST issue, in logical sequence.\n"
            "• Address every issue completely and correctly — do not truncate.\n"
            "• Drop every sentence that does not carry a legal point.\n"
            "• Use a markdown table where a comparison or eligibility matrix is clearer than prose.\n"
            "• End with a ready-to-use draft GST/tax clause or compliance checklist.\n"
            "• Do NOT re-state the facts — the client already wrote section (a).\n"
            "• Cite only provisions directly on point — no tangential padding."
        )

        # 4. Call LLM
        # Token budget: enough for a complete multi-issue advisory without
        # artificial truncation — the prompt enforces conciseness, not a hard cap.
        client = _get_client()
        if LLM_PROVIDER == "anthropic":
            print(f"Calling Claude ({CLAUDE_MAIN_MODEL}) for advisory ({query_type})...")
            response = client.messages.create(
                model=CLAUDE_MAIN_MODEL,
                max_tokens=5000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            advisory_content = response.content[0].text.strip()
        else:
            print(f"Calling OpenAI ({LLM_MODEL}) for advisory ({query_type})...")
            messages.append({"role": "user", "content": user_message})
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                max_completion_tokens=5000,
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
                        max_tokens=5000,
                        system=system_prompt,
                        messages=[
                            {"role": "user", "content": user_message},
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
                        max_completion_tokens=5000,
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
