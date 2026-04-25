from app.generation.confidence import estimate_confidence
from app.generation.source_formatter import format_sources
from app.generation.synthesizer import synthesize_answer
from app.generation.safety import apply_safety_guards


def build_final_answer(question: str, context: str, chunks: list) -> dict:
    """
    Builds the final, safe, demo-ready answer.
    For legal drafts (notices, replies, etc.), bypasses all extra verification reports 
    to provide a clean document.
    """
    # Detect drafting intent (must match synthesizer logic)
    is_draft = any(kw in question.lower() for kw in ["draft", "notice", "reply", "appeal", "submission", "advisory"])

    raw_answer = synthesize_answer(question, context)
    
    # If it's a draft, return raw content immediately to avoid "Verification Reports" and "Safety Checks"
    if is_draft:
        # Strip internal termination marker if present
        content = raw_answer.replace("[TERMINATE]", "").strip()
        return {
            "content": content,
            "reasoning": None
        }

    confidence = estimate_confidence(context, chunks=chunks)
    sources = format_sources(chunks)

    # Parse Metadata (Reasoning)
    if "---METADATA---" in raw_answer:
        parts = raw_answer.split("---METADATA---")
        content = parts[0].strip()
        try:
            import json
            metadata_str = parts[1].strip()
            reasoning = json.loads(metadata_str)
        except Exception as e:
            print(f"Error parsing metadata: {e}")
            reasoning = None
    else:
        content = raw_answer
        reasoning = None

    result = apply_safety_guards(
        answer=content,
        confidence=confidence,
        sources=sources
    )
    
    return {
        "content": result,
        "reasoning": reasoning
    }
