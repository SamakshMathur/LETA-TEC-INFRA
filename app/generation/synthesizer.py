import openai
from app.config import OPENAI_API_KEY, LLM_MODEL
from app.generation.prompt import SYSTEM_PROMPT

# Initialize OpenAI Client
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not found in environment. Answer generation will fail.")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

def synthesize_answer_stream(question: str, context: str):
    """
    Generates a streaming response using GPT-4o with a Unified Chain-of-Thought approach.
    It yields chunks of text as they are generated.
    """
    if not OPENAI_API_KEY:
        yield "## Error: OpenAI API Key Missing."
        return
    
    formatted_system_prompt = SYSTEM_PROMPT.format(context=context)
    
    # Inject Internal Chain-of-Thought (CoT) instructions for Pass 1 drafting
    cot_instruction = """
    CRITICAL INSTRUCTION - INTERNAL REASONING:
    Before generating your mandatory structured response, you MUST output a <thinking> block.
    Inside this <thinking> block, you must:
    1. Extract all relevant entities, dates, intent, and context from the query.
    2. Map out exactly which statutory sections, rules, and jurisprudence apply in strict Legal Hierarchy.
    3. Identify EVERY SINGLE numeric value (limits, rates, fees) present in the retrieved context.
    4. Formulate the response outline ensuring the 7 mandatory sections and the Operative Rule Extraction block are perfectly covered.
    
    After closing the </thinking> block, immediately begin the structured response.
    """
    
    messages = [
        {"role": "system", "content": formatted_system_prompt + "\n\n" + cot_instruction},
        {"role": "user", "content": question}
    ]

    try:
        # First Pass: Draft Answer (Non-streaming to allow validation)
        draft_response = client.chat.completions.create(
            model=LLM_MODEL, 
            messages=messages,
            temperature=0.1, 
            top_p=0.9,
            max_completion_tokens=1800,
            stream=False
        )
        draft_text = draft_response.choices[0].message.content
        
        # Second Pass: Validation
        validation_prompt = f"""
        Check the following generated GST legal answer against the provided context.
        
        CONTEXT:
        {context}
        
        DRAFT ANSWER:
        {draft_text}
        
        VALIDATION RULES:
        Reject and correct the answer if it has:
        ❌ No verbatim quotation from the context.
        ❌ Fake or incorrect legal quotes.
        ❌ Missing primary notification or fails to prioritize Statute/Rules per the Legal Hierarchy Rule.
        ❌ Incorrect legal reasoning or overgeneralization.
        ❌ Fails to explicitly enumerate ALL statutory clauses/conditions from a governing section before explanatory analysis.
        ❌ Fails to explicitly extract NUMBERS (rates, penalties, late fees, limits) from the text.
        ❌ Missing the mandatory "OPERATIVE RULE EXTRACTION" table/block.
        ❌ DOES NOT MATCH THE MANDATORY 7-POINT RESPONSE STRUCTURE.
        
        If any issue is found:
        - Correct the specific errors.
        - Restructure the answer to match the exact 7-POINT MANDATORY OUTPUT STRUCTURE requested.
        - Ensure numeric extraction and statutory condition enumeration are perfectly pulled from the context.
        
        CRITICAL: Ensure that the final output DOES NOT contain the <thinking> block. It must ONLY contain the clean, validated output following the 7 sections and the Operative Rule Extraction block.
        Return ONLY the validated final answer. Do not include a conversational preamble.
        """
        
        validation_messages = [
            {"role": "system", "content": "You are a senior GST legal validator. Your job is to ensure 100% legal accuracy and citation integrity."},
            {"role": "user", "content": validation_prompt}
        ]
        
        # Stream the validated answer
        valid_stream = client.chat.completions.create(
            model=LLM_MODEL,
            messages=validation_messages,
            temperature=0.1,
            top_p=0.9,
            max_completion_tokens=1800,
            stream=True
        )
        
        for chunk in valid_stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        print(f"Error in synthesize_answer_stream: {e}")
        yield f"Error generating answer: {str(e)}"

# Keep strict non-streaming version just in case, or for other uses
def synthesize_answer(question: str, context: str) -> str:
    chunks = []
    for chunk in synthesize_answer_stream(question, context):
        chunks.append(chunk)
    return "".join(chunks)
