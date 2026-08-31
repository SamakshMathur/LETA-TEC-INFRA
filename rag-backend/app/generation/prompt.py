# Load Master System Prompt from file
import os

PROMPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(PROMPT_DIR, "master_prompt.txt"), "r", encoding="utf-8") as f:
    MASTER_SYSTEM_PROMPT = f.read()

BRIEF_PROMPT = MASTER_SYSTEM_PROMPT
STANDARD_PROMPT = MASTER_SYSTEM_PROMPT
SYSTEM_PROMPT = MASTER_SYSTEM_PROMPT
DRAFTING_PROMPT = MASTER_SYSTEM_PROMPT
