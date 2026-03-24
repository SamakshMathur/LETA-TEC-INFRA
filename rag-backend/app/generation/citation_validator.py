import re
from typing import List, Dict, Any

class CitationValidator:
    """
    Performs post-synthesis validation of legal citations.
    Ensures that every Section/Rule cited by the LLM exists in the retrieved context.
    """

    @staticmethod
    def validate_citations(answer: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
        """
        Scans the answer for citations and compares them against the chunks.
        Appends a verification report to the answer.
        """
        # Find all mentions of "Section X" or "Sec X" or "Rule X"
        citation_pattern = r"(Section|Sec|Rule)\s*(\d+[A-Z]?(\(\d+\))?)"
        found_in_answer = re.findall(citation_pattern, answer, re.IGNORECASE)
        
        # Unique normalized citations from answer
        citations_to_verify = set()
        for type_pref, num, _ in found_in_answer:
            citations_to_verify.add(f"{type_pref.capitalize()} {num}")

        # Extract all available provisions from retrieved chunks
        available_provisions = set()
        for chunk in retrieved_chunks:
            prov = chunk.get("provision", "")
            if prov:
                available_provisions.add(prov.strip())

            # Search the FULL chunk text for section/rule markers
            chunk_text = chunk.get("text", "")
            for text_match in re.finditer(citation_pattern, chunk_text, re.IGNORECASE):
                available_provisions.add(f"{text_match.group(1).capitalize()} {text_match.group(2)}")

        # Cross-reference
        verified = []
        hallucinated = []
        
        for cit in citations_to_verify:
            # Loose matching: if "Section 17" is checked, "Section 17(5)" in available is a match
            matches = [avail for avail in available_provisions if cit.lower() in avail.lower() or avail.lower() in cit.lower()]
            if matches:
                verified.append(cit)
            else:
                hallucinated.append(cit)

        # Build Report
        report = "\n\n" + "="*40 + "\n"
        report += "LETA LEGAL VERIFICATION REPORT\n"
        report += "="*40 + "\n"
        
        if not citations_to_verify:
            report += "STATUS: NO CITATIONS DETECTED FOR VALIDATION.\n"
        elif not hallucinated:
            report += "STATUS: ALL CITATIONS VERIFIED AGAINST RECORDED STATUTES.\n"
            report += f"VERIFIED: {', '.join(verified)}\n"
        else:
            report += "STATUS: WARNING - UNVERIFIED CITATIONS DETECTED.\n"
            report += f"VERIFIED: {', '.join(verified) if verified else 'None'}\n"
            report += f"Hallucinated/Unverified: {', '.join(hallucinated)}\n"
            report += "CAUTION: Please cross-reference unverified sections with official Gazette copies.\n"
        
        report += "="*40 + "\n"
        
        return answer + report
