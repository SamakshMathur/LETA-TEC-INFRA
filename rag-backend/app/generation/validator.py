import re
from typing import List, Dict
from .rules_engine import rules_engine

def validate_logic(content: str) -> List[str]:
    """
    Checks if the content adheres to the 'Truth Rules'.
    If a trigger word (e.g., 'Section 47') is found, it ensures 
    critical concepts (e.g., '5000', 'cap') are also present.
    """
    warnings = []
    rules = rules_engine.rules
    
    for rule_id, rule_data in rules.items():
        triggers = rule_data.get("triggers", [])
        required = rule_data.get("required_concepts", [])
        
        # Check if the rule is triggered by the content
        trigger_hit = next((t for t in triggers if t.lower() in content.lower()), None)
        
        if trigger_hit:
            # Rule applies. Check for required concepts.
            # We require strictly that IF the section is discussed, the key numbers must be there.
            missing = [req for req in required if req.lower() not in content.lower()]
            
            if missing:
                # We flag if ANY significant concept is missing to be safe (CA-Grade)
                warnings.append(f"**{trigger_hit} Logic**: Answer mentions '{trigger_hit}' but misses key statutory details: {', '.join(missing)}")

    return warnings

def validate_logic_strict(advisory_content: str, rules_context: str) -> List[str]:
    """
    Uses LLM to detect logical contradictions and hallucinated numbers.
    Cost: 1 low-cost call (gpt-4o-mini).
    """
    from app.config import LLM_MODEL, OPENAI_API_KEY
    import openai
    
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    system_prompt = """
    You are a Legal Logic Auditor. Review the 'Advisory Opinion' against the provided 'Truth Rules'.
    
    1. Check for CONTRADICTIONS (e.g., Analysis says 'Liable' but Conclusion says 'Not Liable').
    2. Check for RULE VIOLATIONS (e.g., Advisory mentions 'Section 47' but fails to mention 'Rs 5000 Cap' if it's in the Truth Rules).
    3. Check for HALLUCINATIONS (e.g., citing a rate/penalty not in Truth Rules).
    
    Output a JSON list of warning strings. If clean, output [].
    Example: ["Contradiction: Conclusion 'Exempt' contradicts Analysis 'Taxable'", "Missing Cap: Section 47 cited but Rs 5000 limit ignored"]
    """
    
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"TRUTH RULES:\n{rules_context}\n\nADVISORY OPINION:\n{advisory_content}"}
            ],
            response_format={"type": "json_object"}
        )
        import json
        result = json.loads(response.choices[0].message.content)
        # The LLM is instructed to output a JSON list of warning strings.
        # If clean, it should output []. So we expect a list directly.
        # If the LLM wraps it in a key like "warnings", we need to handle that.
        # The example shows a direct list, so let's assume that for now.
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "warnings" in result:
            return result["warnings"]
        else:
            print(f"Unexpected LLM response format: {result}")
            return []
    except Exception as e:
        print(f"Strict Validation Error: {e}")
        return []

def validate_citations(content: str, context: str) -> List[str]:
    """Checks for hallucinated citations."""
    warning_list = []
    citation_patterns = [r"Section\s+(\d+[A-Za-z]*)", r"Rule\s+(\d+[A-Za-z]*)"]
    
    found_citations = set()
    for pattern in citation_patterns:
        found_citations.update(re.findall(pattern, content, re.IGNORECASE))
        
    for match in found_citations:
        # Check if citation exists in context
        if match not in context:
            warning_list.append(f"Missing Source: Section/Rule {match} not found in context documents.")
            
    return warning_list

def validate_advisory(advisory_content: str, context: str) -> str:
    """
    Main validation entry point. Runs Citation, Logic (Keyword), and Strict (LLM) checks.
    Appends warnings to the content if issues are found.
    """
    citation_warnings = validate_citations(advisory_content, context)
    logic_warnings = validate_logic(advisory_content)
    
    # Strict Semantic Check (Optional: Enabled for high-stakes)
    # We pass the relevant rules context or just the raw context? 
    # For now, let's use the rules we loaded in rules_engine.
    # To keep it efficient, we might skip this if basic logic passes, OR run it for extra safety.
    # Let's run it. "Autonomous Logic" implies high safety.
    from .rules_engine import rules_engine
    rules_text = rules_engine.get_all_rules_as_text()
    strict_warnings = validate_logic_strict(advisory_content, rules_text)
    
    all_warnings = citation_warnings + logic_warnings + strict_warnings
    
    if all_warnings:
        # Deduplicate
        all_warnings = list(set(all_warnings))
        
        warning_msg = "\n\n> [!WARNING] **AUTOMATED COMPLIANCE CHECK**\n"
        warning_msg += "> The following potential issues were detected in this drafted opinion:\n"
        for w in all_warnings:
            warning_msg += f"> - {w}\n"
        warning_msg += "> \n> *Please verify these points manually before professional use.*"
        
        return advisory_content + warning_msg
        
    return advisory_content
