import re
import ftfy
from fuzzywuzzy import process
from pathlib import Path

class LegalCleaner:
    """
    Multi-layer cleaning for legal documents to reach 9.5/10 RAG quality.
    """
    
    # Common OCR corruptions in GST legal documents
    LEGAL_VOCAB = [
        "contract", "section", "registration", "notification", "circular",
        "authority", "appellant", "applicant", "tribunal", "provision",
        "schedule", "commodity", "exemption", "refund", "penalty",
        "valuation", "classification", "amendment", "liability", "taxable"
    ]
    
    COMMON_FIXES = {
        r"worl<s": "works",
        r"contracl": "contract",
        r"I\(one": "Kone",
        r"secfion": "section",
        r"regisfration": "registration",
        r"notificalion": "notification",
        r"appellanl": "appellant",
        r"fribunal": "tribunal",
        r"l\(iannon": "Gannon",
        r"tr['\"]o[i\]j]+": "FROM",
        r"tr['\"]f[ie]+": "THE",
        r"surji[\\\)\]]+ct['\"]?": "SUBJECT",
        r"wo[i]+k": "WORK",
        r"tli[\[(]*der": "TENDER",
        r"agaII[{yY]*z-": "AGAINST",
        r"i[\])I]*id": "BID",
        r"contracl": "contract",
        r"worl<s": "works",
    }

    @classmethod
    def clean(cls, text: str) -> str:
        if not text:
            return ""
            
        # Layer 1: Character Normalization (Fix mojibake)
        text = ftfy.fix_text(text)
        
        # Standardize quotes and dashes
        text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        text = text.replace("—", "-").replace("–", "-")
        
        # Layer 1.5: Regex Corruption Cleanup (Systematic shapes)
        # Fix common OCR bracket/symbol insertions in words
        text = re.sub(r"(?<=[a-zA-Z])[\(\)\[\]\|\{\}<>](?=[a-zA-Z])", "", text)
        # Fix T'HE -> THE, T'FIE -> THE, etc.
        text = re.sub(r"(?<=[A-Z])'([A-Z])", r"\1", text)
        
        # Layer 2: Denoising (Header/Footer/Metadata removal)
        # Remove "Page X of Y"
        text = re.sub(r"(?i)Page\s+\d+\s+of\s+\d+", "", text)
        # Remove noisy headers (Common in GST docs)
        text = re.sub(r"(?i)GST\s+Council\s+Secretariat", "", text)
        text = re.sub(r"(?i)Confidential", "", text)
        text = re.sub(r"(?i)Signature\s+Not\s+Verified", "", text)
        
        # Layer 3: Legal Word Correction
        # Static fixes first (faster)
        for pattern, replacement in cls.COMMON_FIXES.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            
        # Fuzzy correction for broken legal terms (Layer 2.5)
        # We only run this on words that look like they might be broken 
        # (e.g. contain special chars or are not in a standard dict - simplified here)
        words = text.split()
        cleaned_words = []
        for word in words:
            clean_word = word.strip(".,()[]{}")
            if len(clean_word) > 4 and "<" in clean_word or "(" in clean_word and not clean_word.startswith("("):
                # Try to fuzzy match against legal vocab
                best_match, score = process.extractOne(clean_word.lower(), cls.LEGAL_VOCAB)
                if score > 85:
                    word = word.lower().replace(clean_word.lower(), best_match)
            cleaned_words.append(word)
        
        text = " ".join(cleaned_words)
        
        # Final cleanup: normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        
        return text

    @classmethod
    def get_quality_score(cls, text: str) -> float:
        """
        Returns alphabetic ratio to filter out garbage chunks.
        """
        if not text:
            return 0.0
        alphas = sum(1 for c in text if c.isalpha())
        return alphas / len(text)

    @classmethod
    def is_garbage(cls, text: str, threshold: float = 0.7) -> bool:
        return cls.get_quality_score(text) < threshold
