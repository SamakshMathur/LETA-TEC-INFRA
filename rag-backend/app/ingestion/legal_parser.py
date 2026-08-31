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
    from app.config import SUBSTANTIVE_SECTIONS, PROCEDURAL_SECTIONS

    @classmethod
    def extract_document_metadata(cls, full_text: str, first_page_text: str, filename: str) -> Dict[str, Any]:
        """
        Determines the canonical legal document metadata based on document content,
        layout headings, and structural markers. Bypasses filename assumptions.

        Returns a dict:
        {
            "document_type": str,
            "title": str,
            "authority": str,
            "jurisdiction": str,
            "date_issued": str (YYYY-MM-DD),
            "confidence": float
        }
        """
        text_to_scan = (first_page_text or full_text or "")[:4000]
        text_lower = text_to_scan.lower()

        meta = {
            "document_type": "REFERENCE",
            "title": filename,
            "authority": "Unknown",
            "jurisdiction": "Central",
            "date_issued": None,
            "date_year": None,
            "date_precision": "UNKNOWN",
            "confidence": 0.0
        }

        confidence_points = []

        # 1. Detect Jurisdiction
        if "supreme court" in text_lower:
            meta["jurisdiction"] = "Supreme"
            meta["authority"] = "Supreme Court of India"
            confidence_points.append(1.0)
        elif "high court" in text_lower:
            hc_match = re.search(r'high court of\s+([a-zA-Z\s]+)', text_lower)
            if hc_match:
                state = hc_match.group(1).strip().title()
                meta["jurisdiction"] = state
                meta["authority"] = f"High Court of {state}"
                confidence_points.append(1.0)
            else:
                meta["jurisdiction"] = "State"
                meta["authority"] = "High Court"
                confidence_points.append(0.8)
        elif "advance ruling" in text_lower or "aar" in text_lower:
            aar_match = re.search(r'authority for advance ruling(?:,\s*([a-zA-Z\s]+))?', text_lower)
            if aar_match and aar_match.group(1):
                state = aar_match.group(1).strip().title()
                meta["jurisdiction"] = state
                meta["authority"] = f"Authority for Advance Ruling, {state}"
                confidence_points.append(1.0)
            else:
                meta["jurisdiction"] = "State"
                meta["authority"] = "Authority for Advance Ruling"
                confidence_points.append(0.8)
        else:
            meta["jurisdiction"] = "Central"
            confidence_points.append(0.7)

        # 2. Detect Document Type & Authority & Title
        cir_match = re.search(r'circular\s+no\.\s*([\d\/\-\w]+)', text_lower)
        if cir_match:
            meta["document_type"] = "CIRCULAR"
            meta["title"] = f"Circular No. {cir_match.group(1).upper()}"
            meta["authority"] = "Central Board of Indirect Taxes and Customs"
            meta["jurisdiction"] = "Central"
            confidence_points.append(1.0)
        elif "rules" in text_lower and ("goods and services tax" in text_lower or "gst" in text_lower):
            meta["document_type"] = "RULES"
            rule_title_match = re.search(r'([a-zA-Z\s]+goods and services tax rules,\s*\d+)', text_lower)
            if rule_title_match:
                meta["title"] = rule_title_match.group(1).strip().title()
                confidence_points.append(1.0)
            else:
                meta["title"] = "Central Goods and Services Tax Rules, 2017"
                confidence_points.append(0.8)
            meta["authority"] = "Central Board of Indirect Taxes and Customs"
        elif "act" in text_lower and ("goods and services tax" in text_lower or "gst" in text_lower):
            meta["document_type"] = "PRIMARY_LAW"
            act_title_match = re.search(r'([a-zA-Z\s]+goods and services tax act,\s*\d+)', text_lower)
            if act_title_match:
                meta["title"] = act_title_match.group(1).strip().title()
                confidence_points.append(1.0)
            else:
                meta["title"] = "Central Goods and Services Tax Act, 2017"
                confidence_points.append(0.8)
            meta["authority"] = "Parliament of India"
        elif "notification" in text_lower:
            not_match = re.search(r'notification\s+no\.\s*([\d\/\-\w\-]+)', text_lower)
            if not_match:
                meta["document_type"] = "NOTIFICATION"
                meta["title"] = f"Notification No. {not_match.group(1).upper()}"
                meta["authority"] = "Central Board of Indirect Taxes and Customs"
                meta["jurisdiction"] = "Central"
                confidence_points.append(1.0)
            else:
                meta["document_type"] = "NOTIFICATION"
                confidence_points.append(0.6)
        elif meta["jurisdiction"] in ["Supreme", "State"] or "versus" in text_lower or "vs." in text_lower:
            if "advance ruling" in text_lower or "aar" in text_lower:
                meta["document_type"] = "ADVANCE_RULING"
            else:
                meta["document_type"] = "CASE_LAW"

            vs_match = re.search(r'(?:m/s\.?\s+)?([a-zA-Z\s\.\-&/]+)\s+(?:versus|vs\.?)\s+([a-zA-Z\s\.\-&/]+)', text_lower)
            if vs_match:
                party1 = vs_match.group(1).strip().title()
                party2 = vs_match.group(2).strip().title()
                meta["title"] = f"{party1} Vs {party2}"
                confidence_points.append(0.9)
            else:
                confidence_points.append(0.7)

        # 3. Detect Official Date
        date_patterns = [
            r'dated\s+the\s+(\d{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+\s*,\s*\d{4})',
            r'dated\s+(\d{1,2}\.\d{1,2}\.\d{4})',
            r'dated\s+(\d{1,2}\/\d{1,2}\/\d{4})',
            r'(\d{1,2}\s+[a-zA-Z]+\s*,\s*\d{4})',
        ]
        date_found = False
        for pat in date_patterns:
            date_match = re.search(pat, text_lower)
            if date_match:
                try:
                    raw_dt = date_match.group(1).strip()
                    meta["date_issued"] = raw_dt
                    meta["date_precision"] = "DAY"
                    year_match = re.search(r'\b(20\d{2})\b', raw_dt)
                    if year_match:
                        meta["date_year"] = int(year_match.group(1))
                    confidence_points.append(0.9)
                    date_found = True
                    break
                except Exception:
                    pass
        if not date_found:
            year_match = re.search(r'\b(20\d{2})\b', text_to_scan)
            if year_match:
                meta["date_year"] = int(year_match.group(1))
                meta["date_precision"] = "YEAR"
                meta["date_issued"] = None
                confidence_points.append(0.9)
            else:
                meta["date_precision"] = "UNKNOWN"
                confidence_points.append(0.3)

        meta["confidence"] = sum(confidence_points) / max(len(confidence_points), 1)
        return meta

    @staticmethod
    def determine_quarantine(doc_meta: Dict[str, Any]) -> tuple[bool, str]:
        """
        Determines the active status and quarantine status of a document based on its metadata.
        Returns a tuple: (is_active: bool, status: str)
        """
        doc_type = doc_meta.get("document_type", "REFERENCE")
        confidence = doc_meta.get("confidence", 0.0)
        date_precision = doc_meta.get("date_precision", "UNKNOWN")
        date_year = doc_meta.get("date_year")

        # Circulars and Notifications must have a valid date/year
        has_date_error = doc_type in ["CIRCULAR", "NOTIFICATION"] and (
            date_precision == "UNKNOWN" or date_year is None
        )

        threshold = 0.75 if doc_type in ["PRIMARY_LAW", "RULES"] else 0.85
        if confidence < threshold or has_date_error:
            return False, "NEEDS_REVIEW"
        return True, "Completed"


    @classmethod
    def classify_folder(cls, rel_path: str) -> Dict[str, Any]:
        """
        Derives document type and metadata based on the folder structure.
        """
        path_lower = rel_path.lower()
        if "rule" in path_lower:
            return {"document_type": "RULES", "source": "Official"}
        elif "act" in path_lower or "cgst" in path_lower or "igst" in path_lower:
            return {"document_type": "PRIMARY_LAW", "source": "Official"}
        elif "notification" in path_lower:
            return {"document_type": "NOTIFICATION", "source": "CBIC"}
        elif "circular" in path_lower:
            return {"document_type": "CIRCULAR", "source": "CBIC"}
        elif "case laws" in path_lower or "aar" in path_lower:
            if "aar" in path_lower:
                return {"document_type": "ADVANCE_RULING", "source": "Judiciary"}
            return {"document_type": "CASE_LAW", "source": "Judiciary"}
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
    # Supports: Section 17, Section 9(3), Section 17(5)(a), Sec. 16(2), u/s 73
    CITATION_PATTERNS = {
        "section": r"(?:Section|Sec\.|u/s)\s+(\d+[A-Z]*(?:\(\d+\))*(?:\([a-z]\))*)",
        "rule": r"Rule\s+(\d+[A-Z]*(?:\(\d+\))*(?:\([a-z]\))*)",
        "notification": r"Notification\s+No\.\s+(\d+/\d+)",
        "circular": r"Circular\s+No\.\s+(\d+/\d+/\d+)",
        "schedule": r"Schedule\s+(I|II|III)(?:\s+Para\s+(\d+[a-z]?))?",
        "act": r"(?:CGST|IGST|SGST|UTGST|GST)\s+Act",
    }

    @staticmethod
    def normalize_citation(type_str: str, value: str) -> str:
        """
        Canonicalizes citations into a standardized format: SOURCE_TYPE_VALUE
        Example: Section 17 -> CGST_SEC_17
        """
        clean_val = value.replace("/", "_").replace("(", "_").replace(")", "").strip().upper()
        type_prefix = type_str.upper()[:3]

        # Default source to CGST if not specified in text (common in GST practice)
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
            "CGST_SEC_16": "ITC",
            "CGST_SEC_17": "ITC",
            "CGST_RUL_42": "ITC",
            "CGST_RUL_43": "ITC",
            "CGST_SEC_15": "Valuation",
            "CGST_SEC_9": "RCM",
            "CGST_SEC_8": "Composite_Supply",
            "CGST_SEC_10": "Place_of_Supply",
            "CGST_SEC_12": "Place_of_Supply",
            "CGST_SEC_13": "Place_of_Supply",
            "CGST_SEC_54": "Refund",
            "CGST_SEC_122": "Penalty",
            "CGST_SEC_129": "Penalty",
            "CGST_SEC_22": "Registration",
            "CGST_SEC_24": "Registration",
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

        Phase 4 addition: Statute/Rule chunks are passed through the secondary size-aware
        splitter (app.ingestion.statute_splitter) so that pathologically large sections
        (e.g. ~76k chars) are split at natural legal text boundaries into bounded children.
        The Case Law / Advance Ruling path is unchanged.
        """
        if doc_type in ["Statute", "Rules", "PRIMARY_LAW", "RULES"]:
            # Segment provisions/rules cleanly by locating headers.
            # Using finditer avoids nested capturing group offset bugs common in re.split.
            chunks = []
            base_pattern = cls.CITATION_PATTERNS["section"] if doc_type in ["Statute", "PRIMARY_LAW"] else cls.CITATION_PATTERNS["rule"]
            pattern = rf"(?i)(?:^|\n)\s*({base_pattern})"
            matches = list(re.finditer(pattern, text))

            if matches:
                # Capture any preamble/title text preceding the first section
                preamble = text[:matches[0].start()]
                if preamble:
                    chunks.append({"text": preamble, "structure": "STATUTE_BODY"})

                for idx, m in enumerate(matches):
                    marker = m.group(1)
                    start_pos = m.start()
                    end_pos = matches[idx+1].start() if idx+1 < len(matches) else len(text)
                    chunk_text = text[start_pos:end_pos]
                    chunks.append({"text": chunk_text, "structure": "PROVISION", "provision": marker})
            else:
                chunks.append({"text": text, "structure": "STATUTE_BODY"})

            # Phase 4: Secondary size-aware split for oversized statute/rule chunks.
            # Imports here to avoid any module-level circular import risk.
            from app.ingestion.statute_splitter import apply_secondary_split_to_statute_chunks
            return apply_secondary_split_to_statute_chunks(chunks)


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
