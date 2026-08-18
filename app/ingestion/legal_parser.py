import re
from typing import List, Dict, Any
import hashlib

class LegalParser:
    """
    Overhauled parser for high-precision legal RAG (9.5/10 quality).
    Handles structural parsing, provision-level chunking, and topic classification.
    """
    
    # Controlled Taxonomy for GST Topics (Sourced from User Request)
    TOPIC_TAXONOMY = [
        "ITC", "RCM", "Place_of_Supply", "Works_Contract", "Exemption", 
        "Refund", "Registration", "Composite_Supply", "Export", "Penalty",
        "Classification", "Supply", "Time_of_Supply", "Valuation", "Import", 
        "Appeals", "Returns", "Payment"
    ]

    # Substantive vs Procedural Laws
    SUBSTANTIVE_SECTIONS = ["7", "8", "9", "10", "11", "12", "13", "15", "16", "17", "54"]
    PROCEDURAL_SECTIONS = ["97", "98", "100", "101", "107", "112"]
    
    @classmethod
    def classify_folder(cls, rel_path: str) -> Dict[str, Any]:
        """
        Derives document type and metadata based on the folder structure.
        """
        path_lower = rel_path.lower()
        if "act" in path_lower or "cgst" in path_lower or "igst" in path_lower:
            return {"document_type": "Statute", "source": "Official"}
        elif "rule" in path_lower:
            return {"document_type": "Rules", "source": "Official"}
        elif "notification" in path_lower:
            return {"document_type": "Notification", "source": "CBIC"}
        elif "circular" in path_lower:
            return {"document_type": "Circular", "source": "CBIC"}
        elif "case laws" in path_lower or "aar" in path_lower:
            return {"document_type": "Case Law", "source": "Judiciary"}
        elif "faq" in path_lower:
            return {"document_type": "FAQ", "source": "Official"}
        return {"document_type": "Other", "source": "General"}

    # Structural Headers for Semantic Segmentation (Judgments/AARs)
    STRUCTURE_PATTERNS = {
        "FACTS": r"(?:Brief\s+)?Facts(?:\s+of\s+the\s+case)?|Background",
        "ISSUE": r"Issue[s]?\s+for\s+determination|Question[s]?\s+presented|Point[s]?\s+for\s+determination|Questions\s+for\s+which\s+advance\s+ruling\s+is\s+sought",
        "ARGUMENTS_APPLICANT": r"Arguments?\s+of\s+the\s+applicant|Submissions?\s+of\s+the\s+applicant|Applicant's\s+Submission",
        "ARGUMENTS_REVENUE": r"Arguments?\s+of\s+the\s+revenue|Submissions?\s+of\s+the\s+department|Respondent's\s+Submission",
        "LAW": r"Relevant\s+Legal\s+Provisions|Statutory\s+Framework|Legal\s+Position",
        "ANALYSIS": r"Analysis|Findings|Discussion|Observations|Reasoning",
        "RULING": r"Ruling|Order|Held|Conclusion|Ratio\s+Decidendi"
    }

    # High-Precision Citation Patterns
    # Supports statute-style and case-law shorthand citation formats:
    #   Section 17, Sec. 16(2), u/s 73, S.16, s. 9(3)
    #   Rule 42, u/r 96
    #   Notification No. N/YYYY, Circular No. N/NN/YYYY
    #   Schedule I / II / III
    CITATION_PATTERNS = {
        # Statute-style: Section N, Sec. N — and case-law: u/s N, S.N
        "section": (
            r"(?:Section|Sec\.|u/s|(?<!\w)S\.)\s*"
            r"(\d+[A-Z]*(?:\(\d+\))*(?:\([a-z]\))*)"
        ),
        "rule": (
            r"(?:Rule|u/r)\s+"
            r"(\d+[A-Z]*(?:\(\d+\))*(?:\([a-z]\))*)"
        ),
        "notification": r"Notification\s+No\.?\s*(\d+[/-]\d+)",
        "circular": r"Circular\s+No\.?\s*(\d+[/-]\d+[/-]\d+)",
        "schedule": r"Schedule\s+(I{1,3}|IV|V|VI|[1-6])(?:\s+Para\s+(\d+[a-z]?))?",
        "act": r"(?:CGST|IGST|SGST|UTGST|GST)\s+Act",
    }

    # Maps citation type names to canonical key prefixes (consistent with ingest_v2_database.py)
    _TYPE_PREFIX_MAP = {
        "section":      "SEC",
        "rule":         "RULE",
        "notification": "NOTIF",
        "circular":     "CIRC",
        "schedule":     "SCHED",
    }

    @classmethod
    def normalize_citation(cls, type_str: str, value: str) -> str:
        """
        Canonicalizes citations into a standardized format: CGST_TYPE_VALUE
        Examples:
          Section 17   -> CGST_SEC_17
          Rule 42      -> CGST_RULE_42   (was: CGST_RUL_42)
          Schedule II  -> CGST_SCHED_II
        """
        clean_val  = value.replace("/", "_").replace("(", "_").replace(")", "").strip().upper()
        type_lower = type_str.lower()
        # Use explicit map so "rule" → "RULE", not "RUL"
        type_prefix = cls._TYPE_PREFIX_MAP.get(type_lower, type_lower.upper()[:4])
        return f"CGST_{type_prefix}_{clean_val}"

    @classmethod
    def classify_topic(cls, text: str) -> str:
        """
        Classify chunk into controlled taxonomy based on high-precision keywords and NORMALIZED CITATIONS.
        """
        text_lower = text.lower()
        topic_scores = {}
        
        keyword_map = {
            "ITC": ["input tax credit", "itc", "blocked credit"],
            "RCM": ["reverse charge", "rcm", "9(3)", "9(4)", "reverse charge mechanism"],
            "Works_Contract": ["works contract", "immovable property", "construction", "erection", "commissioning"],
            "Place_of_Supply": ["place of supply", "inter-state", "intra-state"],
            "Exemption": ["exemption", "exempt", "not taxable", "nil rated"],
            "Refund": ["refund", "zero rated", "inverted duty"],
            "Export": ["export", "sez", "lut", "zero rated", "high seas sale", "bill of lading", "shipping bill"],
            "Penalty": ["penalty", "confiscation", "fine", "detention"],
            "Registration": ["registration", "gstin", "cancellation"],
            "Valuation": ["valuation", "transaction value", "open market value"],
            "Composite_Supply": ["composite supply", "mixed supply", "natural bundle"]
        }
        
        for topic, keywords in keyword_map.items():
            count = sum(2 if k in text_lower else 0 for k in keywords) 
            if count > 0:
                topic_scores[topic] = count
                
        # Primary check: Normalized Provision mapping (High Weight)
        normalized_citations = cls.extract_citations(text, normalize=True)
        provision_map = {
            "CGST_SEC_16":   "ITC",
            "CGST_SEC_17":   "ITC",
            "CGST_RULE_42":  "ITC",
            "CGST_RULE_43":  "ITC",
            "CGST_SEC_15":   "Valuation",
            "CGST_SEC_9":    "RCM",
            "CGST_SEC_8":    "Composite_Supply",
            "CGST_SEC_10":   "Place_of_Supply",
            "CGST_SEC_12":   "Place_of_Supply",
            "CGST_SEC_13":   "Place_of_Supply",
            "CGST_SEC_54":   "Refund",
            "CGST_SEC_122":  "Penalty",
            "CGST_SEC_129":  "Penalty",
            "CGST_SEC_22":   "Registration",
            "CGST_SEC_24":   "Registration",
            "CGST_SCHED_I":  "Supply",         # Schedule I → deemed supply (related parties)
            "CGST_SCHED_II": "Supply",
        }
        
        for cit in normalized_citations:
            # Match base section (e.g., CGST_SEC_17_5 matches CGST_SEC_17)
            for prov, topic in provision_map.items():
                if cit.startswith(prov):
                    topic_scores[topic] = topic_scores.get(topic, 0) + 10

        if not topic_scores:
            return "General"
            
        return max(topic_scores, key=topic_scores.get)

    @classmethod
    def extract_citations(cls, text: str, normalize: bool = False) -> List[str]:
        citations = []
        for key, pattern in cls.CITATION_PATTERNS.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for m in matches:
                groups = m.groups()
                if not groups:
                    citations.append(key.upper())
                    continue
                
                if key == "schedule":
                    sched_num = groups[0]
                    para_num = groups[1] if len(groups) > 1 and groups[1] else ""
                    raw = f"Schedule {sched_num}" + (f" Para {para_num}" if para_num else "")
                    if normalize:
                        citations.append(f"CGST_SCHED_{sched_num}_PARA_{para_num}".strip("_"))
                    else:
                        citations.append(raw.upper())
                else:
                    val = groups[0]
                    if normalize:
                        citations.append(cls.normalize_citation(key, val))
                    else:
                        citations.append(f"{key.upper()} {val}")
                    
        return list(dict.fromkeys(citations))

    @classmethod
    def structural_split(cls, text: str, doc_type: str) -> List[Dict[str, Any]]:
        """
        Elite Segmenter: Splits by legal component headers and then sub-chunks large sections.
        Ensures strict section isolation by checking for line-start headers.
        """
        if doc_type in ["Statute", "Rules"]:
            # Preserve existing provision-based logic for statutes
            chunks = []
            pattern = cls.CITATION_PATTERNS["section"] if doc_type == "Statute" else cls.CITATION_PATTERNS["rule"]
            parts = re.split(f"({pattern})", text, flags=re.IGNORECASE)
            
            if len(parts) > 1:
                for i in range(1, len(parts), 2):
                    marker = parts[i]
                    content = parts[i+1] if i+1 < len(parts) else ""
                    chunks.append({"text": f"{marker} {content}", "structure": "PROVISION", "provision": marker})
            else:
                chunks.append({"text": text, "structure": "STATUTE_BODY"})
            return chunks

        # Case Law / Advance Ruling Semantic Segmentation
        header_names = list(cls.STRUCTURE_PATTERNS.keys())
        # Use ^ or \n to ensure headers are at start of logical blocks
        patterns = [f"(?P<{name}>(?:^|\\n)\\s*{cls.STRUCTURE_PATTERNS[name]})" for name in header_names]
        master_pattern = "|".join(patterns)
        
        segments = []
        last_end = 0
        current_type = "BACKGROUND"
        
        for match in re.finditer(master_pattern, text, re.IGNORECASE):
            # Capture the content before the current match
            content = text[last_end:match.start()].strip()
            if content and len(content) > 50:
                segments.append({"text": content, "structure": current_type})
            
            # Update current type based on which named group matched
            for name in header_names:
                if match.group(name):
                    current_type = name
                    break
            last_end = match.end()
            
        # Capture the final segment
        final_content = text[last_end:].strip()
        if final_content:
            segments.append({"text": final_content, "structure": current_type})
            
        # Recursive sub-chunking if segments are too large (Gold standard: ~1000-1500 chars)
        final_chunks = []
        for seg in segments:
            if len(seg["text"]) > 2000:
                # Split large paragraphs
                paras = re.split(r'\n\n|\.\s+(?=[A-Z])', seg["text"])
                current_chunk = ""
                for p in paras:
                    if len(current_chunk) + len(p) < 1500:
                        current_chunk += (" " if current_chunk else "") + p
                    else:
                        if current_chunk:
                            final_chunks.append({"text": current_chunk, "structure": seg["structure"]})
                        current_chunk = p
                if current_chunk:
                    final_chunks.append({"text": current_chunk, "structure": seg["structure"]})
            else:
                final_chunks.append(seg)
                
        return final_chunks

    @staticmethod
    def generate_chunk_id(metadata: Dict[str, Any], structure: str, text: str, index: int) -> str:
        rel_path = metadata.get("rel_path", "unknown")
        name_match = re.search(r'([^\\/]+)\.(?:pdf|docx|xlsx)', rel_path, re.IGNORECASE)
        name = name_match.group(1).upper()[:20] if name_match else "DOC"
        
        doc_type_short = metadata.get("document_type", "DOC")[:3].upper()
        content_hash = hashlib.md5(text.encode()).hexdigest()[:6].upper()
        
        return f"{doc_type_short}_{name}_{structure}_{content_hash}".upper()
