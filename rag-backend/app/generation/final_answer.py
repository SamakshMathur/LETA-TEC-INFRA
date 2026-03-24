from app.generation.confidence import estimate_confidence
from app.generation.source_formatter import format_sources
from app.generation.synthesizer import synthesize_answer
from app.generation.safety import apply_safety_guards


def build_final_answer(question: str, context: str, chunks: list) -> dict:
    """
    Builds the final, safe, demo-ready answer.
    """

    raw_answer = synthesize_answer(question, context)
    confidence = estimate_confidence(context)
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
    
    # Attach reasoning if available (assuming apply_safety_guards returns a dict, 
    # if it returns a string we might need to adjust app.py instead. 
    # Checking app.py, 'final_answer' is just a string. 
    # We should probably return a tuple or dict here to pass reasoning up.)
    
    return {
        "content": result,
        "reasoning": reasoning
    }
