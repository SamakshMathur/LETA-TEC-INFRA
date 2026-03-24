from anthropic import Anthropic
from app.config import ANTHROPIC_API_KEY, VISUAL_LLM_MODEL
import json

# Initialize Anthropic Client
client = None
if ANTHROPIC_API_KEY:
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception as e:
        print(f"Failed to initialize Anthropic client: {e}")

def generate_visual_layout(context: str, answer_text: str) -> str:
    """
    Uses Claude 3.5 Sonnet to generate a 'Visual Enhancement' JSON/Markdown block.
    This function analyzes the text answer and decides if a Table, Chart, or Summary is needed.
    """
    if not client:
        return ""

    system_prompt = """
    You are the 'Visual Designer' for the LETA GST AI.
    Your goal is to take a complex legal text answer and create a STRICTLY FORMATTED VISUAL REPRESENTATION if applicable.

    You must output a JSON object with the following structure:
    {
        "has_visual": true/false,
        "visual_type": "table" | "comparison" | "summary_card" | "step_list",
        "title": "Short Title for the Visual",
        "content_markdown": "The markdown content for the visual (e.g. the table itself)"
    }

    RULES:
    1. If the answer contains a comparison (e.g., Old vs New Regime, Rule A vs Rule B), create a "comparison" table.
    2. If the answer describes a process, create a "step_list".
    3. If the answer is just text without structured data, return "has_visual": false.
    4. "content_markdown" must be raw Markdown (e.g., | Col1 | Col2 |...).
    5. Be purely visual. Do not add new legal opinions. Just visualize the provided text.
    """

    user_prompt = f"""
    CONTEXT (Source Data):
    {context[:2000]}... [truncated]

    ANSWER (To Visualize):
    {answer_text}
    """

    try:
        response = client.messages.create(
            model=VISUAL_LLM_MODEL,
            max_tokens=1000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Parse the response
        result_text = response.content[0].text
        # Ensure we get JSON (Claude is usually good, but robust parsing helps)
        try:
            # Find JSON if wrapped in backticks
            if "```json" in result_text:
                json_str = result_text.split("```json")[1].split("```")[0]
            elif "{" in result_text:
                json_str = result_text[result_text.find("{"):result_text.rfind("}")+1]
            else:
                json_str = result_text
            
            data = json.loads(json_str)
            
            if data.get("has_visual"):
                # Format into a nice Markdown block to append to the answer
                visual_block = f"\n\n---\n\n### 🎨 {data.get('title', 'Visual Summary')}\n\n{data.get('content_markdown')}\n\n"
                return visual_block
            else:
                return ""
                
        except json.JSONDecodeError:
            print("Visualizer: Failed to parse JSON from Claude.")
            return ""

    except Exception as e:
        print(f"Visualizer Error: {e}")
        return ""
