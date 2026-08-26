import faiss
import json
import logging
import threading
import numpy as np
from pathlib import Path
import re

from rank_bm25 import BM25Okapi
from app.config import (
    EMBEDDING_MODEL, VECTOR_DIM,
    VECTOR_SEARCH_TOP_K, VECTOR_EXPANDED_TOP_K, BM25_TOP_K, MMR_LAMBDA,
)
from app.retrieval.reranker import LegalReranker
from app.retrieval.statute_retriever import StatuteRetriever
from app.retrieval.provision_graph import ProvisionGraphRetriever
from app.retrieval.source_priority import source_priority
from app.retrieval.authority_taxonomy import (
    classify_query_authority, authority_bonus, verify_mandatory_coverage,
    GST_GOVERNING_AUTHORITIES,
)
from app.retrieval.citation_graph import DocumentCitationGraph
from app.retrieval.topic_ontology import expand_query_with_ontology

# ── Retrieval memory logger (lazy singleton — import deferred to avoid startup cost) ──
_mem_logger = None

def _get_mem_logger():
    global _mem_logger
    if _mem_logger is None:
        try:
            from app.retrieval.retrieval_memory import RetrievalLogger
            _mem_logger = RetrievalLogger()
        except Exception as _e:
            logger.warning(f"RetrievalLogger init failed (non-fatal): {_e}")
            _mem_logger = None
    return _mem_logger

logger = logging.getLogger(__name__)

# ─── Pool classification — folder patterns per document category ───────────
# Patterns match both legacy flat names and V2.0 versioned folder names
# (e.g. "circulars(2017-2025)", "CGST Acts", "CGST Rules 10-08-2026").
_CASE_LAW_FOLDERS     = {"high court case laws", "supreme court case laws", "aar", "other app result"}
_STATUTE_FOLDERS      = {"act", "rules", "cgst", "igst", "utgst", "export",
                          "cgst acts", "igst acts", "igst rules"}   # V2.0 folder names
_NOTIFICATION_FOLDERS = {"notification", "notifications",
                          "rate_notifications_2.0"}                 # V2.0 folder name
_CIRCULAR_FOLDERS     = {"circulars", "circular", "icai", "brochures", "faqs",
                          "circulars(2017-2025)"}                   # V2.0 folder name


def _chunk_category(chunk: dict) -> str:
    path = (chunk.get("rel_path") or chunk.get("source") or
            chunk.get("metadata", {}).get("rel_path", "")).lower().replace("\\", "/")
    # Split into components for prefix-based matching (handles versioned names
    # like "cgst rules 10-08-2026" matching the pattern "cgst").
    parts = [p for p in path.split("/") if p]

    def _matches(folders: set) -> bool:
        for folder in folders:
            # Exact path-component match (original logic)
            if f"/{folder}/" in path or path.startswith(folder + "/"):
                return True
            # Prefix match on individual path components — handles versioned
            # folder names, e.g. "cgst rules 10-08-2026".startswith("cgst") → True.
            # Guard: folder must be ≥4 chars to avoid spurious "act" matches.
            if len(folder) >= 4:
                for part in parts:
                    if part.startswith(folder):
                        return True
        return False

    if _matches(_CASE_LAW_FOLDERS):      return "case_law"
    if _matches(_CIRCULAR_FOLDERS):      return "circular"
    if _matches(_NOTIFICATION_FOLDERS):  return "notification"
    if _matches(_STATUTE_FOLDERS):       return "statute"
    return "other"


# ─── Coverage validation: per-query expected authority categories ──────────
# Returns which document categories must appear in the final output.
# Advisory / interpretive queries need statute + circular at minimum.
# Rate / classification queries additionally need notifications.
# Narrow definitional queries (define "supply") need statute only.
_ADVISORY_WORDS = frozenset([
    "what", "whether", "how", "explain", "clarif", "position", "treatment",
    "applicab", "eligible", "liable", "charge", "implication", "cross",
    "isd", "reverse", "works", "import", "export", "exempt", "place",
    "valuat", "time", "registr", "refund", "distinct", "common", "shared",
    "branch", "headquarter", "head office", "proviso",
])
_RATE_WORDS = frozenset([
    "rate", "nil", "hsn", "sac", "12%", "18%", "28%", "5%", "classif",
    "exemption", "exempt supply",
])


def _query_expected_coverage(query: str, topic: str) -> set:
    """
    Returns the set of document categories that MUST appear in the final
    output for a given query.  Drives Layer 6 coverage-fill injection.

    Conservative by design — only injects when a category is truly needed
    AND semantically confirmed by the sub-index search.
    """
    q = query.lower()
    cats = {"statute"}   # statutory foundation is always required

    # Advisory / interpretive / advisory queries need circular clarification
    if any(w in q for w in _ADVISORY_WORDS):
        cats.add("circular")

    # Rate / classification / exemption queries need notifications
    if any(w in q for w in _RATE_WORDS):
        cats.add("notification")

    return cats

# ─── Thread-safe embedding model singleton ─────────────────────────────────
_model = None
_model_lock = threading.Lock()
_model_device = "auto"   # tracks where the model was loaded; "cpu" after GPU fallback


def get_model(force_cpu: bool = False):
    """Returns the embedding model, loading it once with thread safety.

    If force_cpu=True the existing model is discarded and reloaded on CPU.
    This is called automatically after a CUDA error to recover from GPU
    context loss caused by a system sleep / resume cycle.
    """
    global _model, _model_device
    if _model is None or force_cpu:
        with _model_lock:
            if _model is None or force_cpu:
                from sentence_transformers import SentenceTransformer
                device = "cpu" if force_cpu else None   # None = auto-detect
                device_label = "CPU (fallback)" if force_cpu else "auto"
                logger.info(f"Loading embedding model: {EMBEDDING_MODEL} | device={device_label}")
                _model = SentenceTransformer(EMBEDDING_MODEL, device=device)
                _model_device = "cpu" if force_cpu else "auto"
                logger.info(f"Embedding model loaded successfully on {_model_device}")
    return _model


def _is_cuda_error(exc: Exception) -> bool:
    """Returns True for PyTorch CUDA / GPU errors (e.g. after sleep/wake)."""
    name = type(exc).__name__
    msg  = str(exc).lower()
    return (
        "AcceleratorError" in name
        or "CudaError" in name
        or "cuda error" in msg
        or "unknown error" in msg and "cuda" in msg
    )


def embed_query(text: str):
    """
    Embeds a single query string (normalized for cosine similarity with IndexFlatIP).
    Results are cached in Redis by SHA-256(text) — saves 200-400ms per cache hit.

    Automatically recovers from CUDA errors caused by sleep/wake GPU context loss:
    the model is reloaded on CPU and the encode is retried once.
    """
    if not text or not text.strip():
        logger.warning("embed_query called with empty text")
        return None

    # L0: embedding cache (Redis)
    try:
        from app.cache import get_cached_embedding, set_cached_embedding
        cached = get_cached_embedding(text)
        if cached is not None:
            return cached
    except Exception:
        pass  # cache miss or unavailable — proceed to model

    model = get_model()
    try:
        vec = model.encode(text, normalize_embeddings=True)
    except Exception as exc:
        if _is_cuda_error(exc):
            # GPU context lost (sleep/wake cycle) — reload on CPU and retry once
            logger.warning(
                f"CUDA error during embed_query — reloading model on CPU and retrying: {exc}"
            )
            model = get_model(force_cpu=True)
            vec = model.encode(text, normalize_embeddings=True)
        else:
            raise

    # Store for next time
    try:
        set_cached_embedding(text, vec)
    except Exception:
        pass

    return vec


# GST compound phrases used to generate bigram tokens for BM25
_GST_BIGRAMS = frozenset([
    "input tax credit", "reverse charge mechanism", "reverse charge",
    "place of supply", "time of supply", "zero rated supply",
    "show cause notice", "input service distributor", "electronic cash ledger",
    "electronic credit ledger", "inverted duty structure", "composite supply",
    "mixed supply", "works contract", "capital goods", "job work",
    "advance ruling", "high court", "supreme court", "annual return",
    "inter state", "intra state", "e way bill", "transitional credit",
    "input tax", "output tax", "zero rated", "exempt supply",
])

# Abbreviation → full-form expansion for BM25 query preprocessing.
# DESIGN: Each pattern runs on the *original* query (not the accumulated result)
# to prevent cascading double-expansion.  Normalisation patterns (section shorthand)
# run first in-place; synonym expansions are collected separately and appended.
#
# ORGANISATION: patterns are grouped by topic. Within each group, specific phrases
# come before single-word forms so alternation patterns are unambiguous.

_GST_ABBREV_NORM = [
    # Section/Rule shorthand: "sec 16", "s.16" → "section 16"
    (re.compile(r'\bsec\.?\s*(\d)', re.IGNORECASE), r'section \1'),
    (re.compile(r'\bs\.\s*(\d)', re.IGNORECASE), r'section \1'),
]

_GST_ABBREV_EXPAND = [
    # ── Core act abbreviations ─────────────────────────────────────────────
    (re.compile(r'\bitc\b', re.IGNORECASE),   'input tax credit ITC credit'),
    (re.compile(r'\brcm\b', re.IGNORECASE),   'reverse charge mechanism RCM recipient pays'),
    (re.compile(r'\bscn\b', re.IGNORECASE),   'show cause notice SCN demand'),
    (re.compile(r'\bisd\b', re.IGNORECASE),   'input service distributor ISD head office branch distribute'),
    (re.compile(r'\blut\b', re.IGNORECASE),   'letter of undertaking LUT export zero rated bond'),
    (re.compile(r'\bsez\b', re.IGNORECASE),   'special economic zone SEZ zero rated supply'),
    (re.compile(r'\bcgst\b', re.IGNORECASE),  'central goods services tax CGST'),
    (re.compile(r'\bigst\b', re.IGNORECASE),  'integrated goods services tax IGST interstate'),
    (re.compile(r'\bsgst\b', re.IGNORECASE),  'state goods services tax SGST'),
    (re.compile(r'\butgst\b', re.IGNORECASE), 'union territory goods services tax UTGST'),
    (re.compile(r'\bgstr\b', re.IGNORECASE),  'return GSTR filing'),
    (re.compile(r'\bfaq\b', re.IGNORECASE),   'frequently asked questions FAQ'),
    (re.compile(r'\baar\b', re.IGNORECASE),   'advance ruling AAR authority'),
    (re.compile(r'\baaar\b', re.IGNORECASE),  'appellate advance ruling AAAR authority'),
    (re.compile(r'\bpos\b', re.IGNORECASE),   'place of supply POS location'),
    (re.compile(r'\bpoc\b', re.IGNORECASE),   'place of supply POS'),
    (re.compile(r'\bcbic\b', re.IGNORECASE),  'CBIC central board indirect taxes customs circular instruction'),
    (re.compile(r'\bcbec\b', re.IGNORECASE),  'central board excise customs CBEC'),

    # ── Real estate / development vocabulary ──────────────────────────────
    (re.compile(r'\btdr\b', re.IGNORECASE),
        'transfer of development rights TDR development rights promoter land owner'),
    (re.compile(r'\bfsi\b', re.IGNORECASE),
        'floor space index FSI development rights construction'),
    (re.compile(r'\bjda\b', re.IGNORECASE),
        'joint development agreement JDA land owner developer consideration'),
    (re.compile(r'\brera\b', re.IGNORECASE),
        'real estate regulation RERA builder developer project'),
    (re.compile(r'\bunsold\s+flat', re.IGNORECASE),
        'unsold flats un-booked apartments completion certificate OC RCM promoter'),
    (re.compile(r'\bun.?booked\b', re.IGNORECASE),
        'un-booked unsold apartments completion certificate promoter'),
    (re.compile(r'\bcompletion\s+certif', re.IGNORECASE),
        'completion certificate OC occupancy certificate apartment promoter'),
    (re.compile(r'\b(?:builder|promoter)\b', re.IGNORECASE),
        'builder promoter developer real estate residential project apartment'),

    # ── Transport ─────────────────────────────────────────────────────────
    (re.compile(r'\b(?:gta|goods\s+transport\s+agenc)', re.IGNORECASE),
        'goods transport agency GTA freight road transportation carriage'),
    (re.compile(r'\bfreight\b', re.IGNORECASE),
        'freight transport goods carriage road consignment'),
    (re.compile(r'\bconsignment\b', re.IGNORECASE),
        'consignment freight goods transport carriage road'),

    # ── Healthcare ────────────────────────────────────────────────────────
    (re.compile(r'\b(?:hospital|health\s*care|healthcare)\b', re.IGNORECASE),
        'hospital health care services clinical establishment patient exempt medical'),
    (re.compile(r'\bclinical\s+establish', re.IGNORECASE),
        'clinical establishment health care services hospital medical exempt'),
    (re.compile(r'\bdiagnos', re.IGNORECASE),
        'diagnostic test pathology laboratory health care services medical'),

    # ── Finance / banking / guarantee ─────────────────────────────────────
    (re.compile(r'\bpersonal\s+guarantee\b', re.IGNORECASE),
        'personal guarantee director bank surety taxable supply corporate guarantee'),
    (re.compile(r'\bcorporate\s+guarantee\b', re.IGNORECASE),
        'corporate guarantee personal guarantee director bank surety taxable supply'),
    (re.compile(r'\bnbfc\b', re.IGNORECASE),
        'non banking financial company NBFC loan lending RBI'),

    # ── E-commerce / digital ──────────────────────────────────────────────
    (re.compile(r'\b(?:eca|e.?commerce\s+operator)\b', re.IGNORECASE),
        'electronic commerce aggregator ECA e-commerce operator TCS'),
    (re.compile(r'\btcs\b', re.IGNORECASE),
        'tax collected at source TCS e-commerce operator'),
    (re.compile(r'\btds\b', re.IGNORECASE),
        'tax deducted at source TDS deduction'),
    (re.compile(r'\boidar\b', re.IGNORECASE),
        'online information database access retrieval OIDAR digital services foreign'),
    (re.compile(r'\bonline\s+gaming\b', re.IGNORECASE),
        'online gaming actionable claim 28 percent face value virtual digital'),
    (re.compile(r'\bfantasy\s+sports?\b', re.IGNORECASE),
        'fantasy sports online gaming actionable claim 28 percent face value'),
    (re.compile(r'\bvda\b', re.IGNORECASE),
        'virtual digital assets VDA cryptocurrency 28 percent'),
    (re.compile(r'\bcryptocurren', re.IGNORECASE),
        'cryptocurrency virtual digital assets VDA schedule III'),

    # ── Classification / tariff ───────────────────────────────────────────
    (re.compile(r'\bhsn\b', re.IGNORECASE),
        'HSN harmonized system nomenclature tariff heading classification goods'),
    (re.compile(r'\bsac\b', re.IGNORECASE),
        'SAC services accounting code classification services'),
    (re.compile(r'\bworks\s+contract\b', re.IGNORECASE),
        'works contract immovable property construction civil composite supply'),
    (re.compile(r'\bcomposite\s+supply\b', re.IGNORECASE),
        'composite supply principal supply bundled natural'),
    (re.compile(r'\bmixed\s+supply\b', re.IGNORECASE),
        'mixed supply highest tax rate multiple supplies combination'),

    # ── Returns / compliance ──────────────────────────────────────────────
    (re.compile(r'\bgstr.?1\b', re.IGNORECASE),
        'GSTR-1 outward supply return monthly quarterly'),
    (re.compile(r'\bgstr.?3b\b', re.IGNORECASE),
        'GSTR-3B monthly return summary tax'),
    (re.compile(r'\bgstr.?9c?\b', re.IGNORECASE),
        'GSTR-9 annual return reconciliation statement audit'),
    (re.compile(r'\be.?way\b', re.IGNORECASE),
        'e-way bill electronic way bill transport document movement goods'),
    (re.compile(r'\banti.?profiteer', re.IGNORECASE),
        'anti-profiteering section 171 NAA national authority reduction benefit'),

    # ── Supply classification / renting ───────────────────────────────────
    (re.compile(r'\bzero.?rated\b', re.IGNORECASE),
        'zero rated supply export SEZ refund LUT bond'),
    (re.compile(r'\b(?:nil.?rated|exempt\s+supply)\b', re.IGNORECASE),
        'nil rated exempt supply non-taxable'),
    (re.compile(r'\brenting\b', re.IGNORECASE),
        'renting immovable property lessor lessee landlord tenant residential commercial'),
    (re.compile(r'\b(?:landlord|lessor)\b', re.IGNORECASE),
        'landlord lessor renting immovable property owner tenant'),
    (re.compile(r'\btenant\b', re.IGNORECASE),
        'tenant lessee renting immovable property'),

    # ── Schedule references ────────────────────────────────────────────────
    (re.compile(r'\bschedule\s+i\b', re.IGNORECASE),
        'Schedule I deemed supply without consideration'),
    (re.compile(r'\bschedule\s+ii\b', re.IGNORECASE),
        'Schedule II classification composite services goods'),
    (re.compile(r'\bschedule\s+iii\b', re.IGNORECASE),
        'Schedule III neither supply not taxable'),
]


def _expand_for_bm25(query: str) -> str:
    """
    Expand GST abbreviations and synonyms for better BM25 keyword coverage.

    Two-phase approach to prevent cascading double-expansion:
      1. Normalisation (section shorthand) runs sequentially in-place.
      2. Synonym expansions each run on the *original* query; all unique
         expansions are concatenated so BM25 sees the full term variety.
    """
    # Phase 1 — normalization (in-place, sequential)
    normed = query
    for pattern, replacement in _GST_ABBREV_NORM:
        normed = pattern.sub(replacement, normed)

    # Phase 2 — synonym expansion (each pattern on original query)
    extras: list[str] = []
    for pattern, replacement in _GST_ABBREV_EXPAND:
        expanded = pattern.sub(replacement, query)
        if expanded != query:
            extras.append(expanded)

    if extras:
        return normed + ' ' + ' '.join(extras)
    return normed


# ── GST-domain stopwords for Pseudo-Relevance Feedback ───────────────────────
# These are too common across all GST documents to be discriminative PRF terms.
_PRF_STOP = frozenset({
    # Common English stopwords
    'the', 'of', 'and', 'in', 'to', 'a', 'an', 'is', 'are', 'for', 'on',
    'with', 'or', 'at', 'by', 'from', 'it', 'that', 'this', 'as', 'be',
    'has', 'have', 'was', 'were', 'not', 'but', 'if', 'so', 'its', 'all',
    'any', 'can', 'also', 'such', 'under', 'shall', 'may', 'where', 'which',
    'whether', 'their', 'these', 'those', 'each', 'both', 'said', 'been',
    'will', 'further', 'above', 'below', 'into', 'upon', 'only', 'other',
    'then', 'than', 'when', 'what', 'how', 'they', 'them', 'there', 'do',
    'does', 'did', 'would', 'could', 'should', 'no', 'nor', 'same',
    # GST-domain stopwords (appear in almost every document)
    'gst', 'tax', 'supply', 'taxable', 'goods', 'services', 'registered',
    'person', 'section', 'rule', 'notification', 'circular', 'act',
    'central', 'state', 'order', 'date', 'value', 'amount', 'rate',
    'applicable', 'case', 'provided', 'made', 'given', 'however',
    'pursuant', 'thereof', 'therein', 'thereto', 'mentioned', 'respect',
    'made', 'make', 'para', 'clause', 'sub', 'new', 'prescribed', 'said',
    'time', 'period', 'total', 'per', 'cent', 'percent', 'cgst', 'igst',
    'sgst', 'india', 'government', 'ministry', 'department', 'board',
    'officer', 'authority', 'court',
})


def _prf_expand(query_tokens: list, top_chunk_texts: list, max_terms: int = 8) -> list:
    """
    Pseudo-Relevance Feedback (PRF): extract the most distinctive terms
    from the top BM25 chunks that are NOT already in the query.

    Algorithm:
      - Tokenize each of the top-N chunks (default 3).
      - Count how many distinct chunks each token appears in (document frequency
        within the *top set*, not the whole corpus).
      - Return up to `max_terms` tokens with highest in-top-set DF, excluding
        tokens already in the query and domain/English stopwords.

    This bridges the vocabulary gap when users write plain-English queries but
    legal documents use formal statutory phrasing (e.g. query "unsold flats"
    → PRF adds "un-booked" "completion" "certificate" "promoter" from top chunks).

    Runs two BM25 passes total; BM25 is µs-fast so overhead is negligible.
    """
    if not top_chunk_texts:
        return []

    from collections import Counter
    query_token_set = frozenset(t.lower() for t in query_tokens)
    doc_freq: Counter = Counter()   # token → # of top chunks it appears in

    for text in top_chunk_texts:
        seen_in_doc: set = set()
        for tok in tokenize_text(text):
            tok_l = tok.lower()
            if (
                len(tok_l) >= 4
                and tok_l not in _PRF_STOP
                and tok_l not in query_token_set
                and tok_l not in seen_in_doc
            ):
                doc_freq[tok_l] += 1
                seen_in_doc.add(tok_l)

    if not doc_freq:
        return []

    # Prefer terms that appear in 2+ of the top chunks (multi-doc evidence)
    high_conf = [tok for tok, cnt in doc_freq.most_common(max_terms + 10) if cnt >= 2]
    if len(high_conf) < max_terms:
        # Supplement with top single-occurrence terms
        low_conf = [tok for tok, cnt in doc_freq.most_common(max_terms * 3) if cnt == 1]
        high_conf = (high_conf + low_conf)[:max_terms]

    return high_conf[:max_terms]


# ─── Direct legal reference extraction ────────────────────────────────────────
# Maps lowercase act keywords found near a section/rule citation to canonical codes
_ACT_CODE_MAP = [
    ("cgst", "CGST"), ("igst", "IGST"), ("sgst", "SGST"), ("utgst", "UTGST"),
    ("central goods", "CGST"), ("integrated goods", "IGST"),
    ("union territory", "UTGST"),
]


def _extract_query_refs(query: str) -> list:
    """
    Extracts normalized provision keys from a query, matching the format stored
    in chunk.metadata.provisions (e.g. CGST_SEC_16, IGST_SEC_13, CGST_RUL_89).

    Called before FAISS search so that explicitly-cited sections are pinned at
    the top of the retrieval pool, bypassing ranking uncertainty.
    """
    q = query.lower()
    refs = []
    seen: set = set()

    def _act_codes(ctx: str) -> list:
        found = [code for kw, code in _ACT_CODE_MAP if kw in ctx]
        # Remove duplicates while preserving order
        seen_codes: set = set()
        deduped = []
        for c in found:
            if c not in seen_codes:
                seen_codes.add(c)
                deduped.append(c)
        return deduped if deduped else ["CGST", "IGST"]  # try both when no act named

    # Section references: "section 16", "sec 16", "section 2(13)", "sec.16"
    for m in re.finditer(r'\bsec(?:tion)?\s*\.?\s*(\d+)(?:\s*\([^)]{0,12}\))*', q):
        sec = m.group(1)
        ctx = q[max(0, m.start() - 40): m.end() + 40]
        for code in _act_codes(ctx):
            key = f"{code}_SEC_{sec}"
            if key not in seen:
                seen.add(key)
                refs.append(key)

    # Rule references: "rule 89", "rule 42(2)"
    for m in re.finditer(r'\brule\s+(\d+)(?:\s*\([^)]{0,12}\))*', q):
        rule = m.group(1)
        ctx = q[max(0, m.start() - 40): m.end() + 40]
        for code in _act_codes(ctx):
            key = f"{code}_RUL_{rule}"
            if key not in seen:
                seen.add(key)
                refs.append(key)

    # Schedule references: "schedule ii", "schedule iii", "schedule 1"
    for m in re.finditer(r'\bschedule\s+([ivxlcdm]+|\d+)\b', q):
        sch = m.group(1).upper()
        key = f"CGST_SCH_{sch}"
        if key not in seen:
            seen.add(key)
            refs.append(key)

    # Circular references: "Circular No. 183", "Circular 183/15/2022", "CBIC Circular 183"
    for m in re.finditer(r'\bcircular\s+(?:no\.?\s*)?(\d{2,3})\b', q):
        cir_num = m.group(1)
        key = f"CIRCULAR_{cir_num}"
        if key not in seen:
            seen.add(key)
            refs.append(key)

    return refs


def _expand_context_window(
    selected: list,
    doc_map: dict,
    all_chunks: list,
    max_neighbors: int = 2,
) -> list:
    """
    Full-corpus context window expansion.

    For each selected chunk, looks up its document in the startup-built doc_map
    (rel_path → sorted [(page, chunk_index)]) and fetches adjacent-page neighbors
    directly from all_chunks by index. Neighbors can be anywhere in the full corpus,
    not just the 80-chunk retrieval pool — this is the key improvement over the
    previous pool-only version.

    Stores the enriched text in context_text; original text is preserved for
    scoring, snippet display, and the source panel.
    """
    if not doc_map or not all_chunks:
        return selected

    expanded = []
    for chunk in selected:
        rel = chunk.get("rel_path") or chunk.get("metadata", {}).get("rel_path", "")
        pages = chunk.get("pages") or chunk.get("metadata", {}).get("pages") or []
        page = min(pages) if pages else (
            chunk.get("page") or chunk.get("metadata", {}).get("page") or 0
        )
        cid = chunk.get("chunk_id")

        if rel and rel in doc_map and len(doc_map[rel]) > 1:
            neighbor_chunks = []
            for (p, idx) in doc_map[rel]:
                if abs(p - page) <= 2 and 0 <= idx < len(all_chunks):
                    nbr = all_chunks[idx]
                    if nbr.get("chunk_id") != cid:
                        neighbor_chunks.append(nbr)

            if neighbor_chunks:
                neighbor_chunks = neighbor_chunks[:max_neighbors]
                neighbor_texts = [
                    n.get("text", "").strip()
                    for n in neighbor_chunks
                    if n.get("text", "").strip()
                ]
                if neighbor_texts:
                    chunk = chunk.copy()
                    chunk["context_text"] = (
                        chunk.get("text", "")
                        + "\n\n[ADJACENT CONTEXT FROM SAME DOCUMENT]\n"
                        + "\n\n".join(neighbor_texts)
                    )

        expanded.append(chunk)

    return expanded


def tokenize_text(text: str):
    """
    Enhanced BM25 tokenizer that:
    - Preserves section/rule compound references as additional tokens
    - Keeps form codes (DRC-01, GSTR-3B) with hyphen intact
    - Adds underscore-joined bigrams for critical GST compound phrases
    - Falls back to standard word tokenization for everything else
    """
    text_lower = text.lower()
    tokens = list(re.findall(r'\b\w+\b', text_lower))

    # Preserve section/rule number references as compound tokens
    # e.g. "section 16(2)(b)" → "section_16_2_b"
    for m in re.finditer(
        r'\b(section|rule|schedule|article|clause|sub-section|proviso)\s+(\d+(?:[(\w)]+)*)',
        text_lower
    ):
        compound = re.sub(r'[^a-z0-9]', '_', m.group(0))
        tokens.append(compound)

    # Keep form/notification codes with hyphens as single tokens
    # e.g. "DRC-01", "GSTR-3B", "RFD-01"
    for m in re.finditer(r'\b[a-z]{2,5}-[\w\d]+\b', text_lower):
        tokens.append(m.group(0))

    # Circular/notification number references as compound tokens
    # e.g. "Circular No. 183" → "circular_no_183", "cir-183-15" → "circular_183"
    for m in re.finditer(
        r'\b(?:circular|cir)[-_.\s]*(?:no\.?[-_.\s]*)?(\d{2,3})\b',
        text_lower
    ):
        tokens.append(f"circular_{m.group(1)}")

    # Add bigram tokens for GST compound phrases
    for phrase in _GST_BIGRAMS:
        if phrase in text_lower:
            tokens.append(phrase.replace(' ', '_'))

    return tokens


def _mmr_deduplicate(results, top_k: int, lambda_param: float = MMR_LAMBDA):
    """
    Maximal Marginal Relevance (MMR) deduplication.

    Prevents the top-k being dominated by near-duplicate chunks from the
    same document/paragraph.  Uses token-overlap (Jaccard) as a cheap
    proxy for similarity — avoids a second round of vector encoding.

    lambda_param: 1.0 = pure relevance, 0.0 = pure diversity.
    """
    if not results:
        return results

    selected = []
    remaining = list(results)

    max_score = max(r.get("_final_legal_score", 0) for r in remaining) or 1.0

    def jaccard(a: str, b: str) -> float:
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    while remaining and len(selected) < top_k:
        best_item = None
        best_mmr = -1.0

        for candidate in remaining:
            relevance = candidate.get("_final_legal_score", 0) / max_score

            if selected:
                max_sim = max(
                    jaccard(candidate.get("text", ""), s.get("text", ""))
                    for s in selected
                )
            else:
                max_sim = 0.0

            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim

            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_item = candidate

        if best_item:
            selected.append(best_item)
            remaining.remove(best_item)

    return selected


def _rrf_combine(*ranked_lists: list, k: int = 60) -> list:
    """
    Reciprocal Rank Fusion (Cormack et al. 2009) — N-way variant.

    Accepts any number of pre-ranked lists (FAISS, BM25, TF-IDF, …).
    Each chunk gets: score = Σ  1/(k + rank_in_list_i + 1)  across all lists.

    Outperforms naive set-union because position matters — a chunk ranked #2 in
    both FAISS and BM25 scores higher than one ranked #1 in only one system.
    k=60 is the standard constant; lower k magnifies rank-gap differences.
    Adding a 3rd list (TF-IDF) boosts chunks that appear in all three signals
    (e.g. a circular chunk that is semantically close AND keyword-matches AND
    has an exact citation token match) without penalising chunks that only show
    up in one or two signals.
    """
    scores: dict = {}
    chunk_map: dict = {}

    for ranked_list in ranked_lists:
        for rank, chunk in enumerate(ranked_list):
            cid = chunk.get("chunk_id") or id(chunk)
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            if cid not in chunk_map:
                chunk_map[cid] = chunk

    sorted_ids = sorted(scores, key=lambda x: -scores[x])
    result = []
    for cid in sorted_ids:
        c = chunk_map[cid].copy()
        c["_rrf_score"] = round(scores[cid], 6)
        result.append(c)
    return result


class Retriever:
    def __init__(self, index_path: Path, chunks_path: Path):
        self.index_path = index_path
        self.chunks_path = chunks_path
        self.chunks = []
        self.metadata = []
        self.index = None
        self.bm25 = None
        self.inactive_paths: set = set()   # paths filtered from search results (empty = all active)

        if not index_path.exists():
            logger.error(f"FAISS index not found at {index_path} — search will return empty results")
            return

        # Load FAISS index
        logger.info("Loading FAISS index...")
        self.index = faiss.read_index(str(index_path))
        logger.info(f"FAISS index loaded: {self.index.ntotal} vectors, dim={self.index.d}")

        # Merge sidecar index if it exists (produced by incremental ingest scripts)
        sidecar_path = index_path.parent / "index_sidecar.faiss"
        if sidecar_path.exists():
            try:
                sidecar = faiss.read_index(str(sidecar_path))
                if sidecar.d == self.index.d and sidecar.ntotal > 0:
                    # Merge: extract all vectors from sidecar and add to main index
                    all_vecs = faiss.rev_swig_ptr(sidecar.get_xb(), sidecar.ntotal * sidecar.d)
                    import numpy as _np
                    all_vecs = _np.array(all_vecs).reshape(sidecar.ntotal, sidecar.d).astype('float32')
                    self.index.add(all_vecs)
                    # Persist merged index and remove sidecar
                    faiss.write_index(self.index, str(index_path))
                    sidecar_path.unlink()
                    logger.info(f"Sidecar merged: +{sidecar.ntotal} vectors → main index now {self.index.ntotal}")
            except Exception as e:
                logger.warning(f"Sidecar merge failed (non-fatal): {e}")

        # Validate dimension
        if self.index.d != VECTOR_DIM:
            logger.error(f"FAISS dimension mismatch: index has {self.index.d}, config expects {VECTOR_DIM}")

        # Load Chunks and Metadata
        logger.info("Loading chunks & building BM25 index...")
        tokenized_corpus = []
        try:
            with open(chunks_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        chunk = json.loads(line)
                        self.chunks.append(chunk)
                        self.metadata.append(chunk.get("metadata", {}))
                        tokenized_corpus.append(tokenize_text(chunk.get("text", "")))
                    except json.JSONDecodeError:
                        logger.warning(f"Malformed JSON at line {line_num} in chunks.jsonl — skipped")
        except FileNotFoundError:
            logger.error(f"Chunks file not found: {chunks_path}")
            return

        # Validate FAISS-chunk alignment
        if self.index.ntotal != len(self.chunks):
            logger.warning(
                f"FAISS/chunk count mismatch: {self.index.ntotal} vectors vs {len(self.chunks)} chunks — "
                "rebuild the index to fix"
            )

        # Initialize BM25
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"BM25 index built: {len(tokenized_corpus)} documents")

        # Backfill missing year metadata from path — checks both subfolder structure
        # (Circulars/circulars/2022/file.pdf) and filename (cir-252-09-2025-cgst.pdf).
        # The reranker's _year_recency() reads this field — without it every circular
        # and notification gets the "unknown year" score of 0.55 regardless of actual age.
        _year_dir_re  = re.compile(r'[/\\](\d{4})[/\\]')       # year as directory component
        _year_fname_re = re.compile(r'[-_](\d{4})[-_.]')        # year embedded in filename
        _year_patched = 0
        for _chunk in self.chunks:
            _meta = _chunk.get("metadata", {})
            if not (_meta.get("year") or _chunk.get("year")):
                _rel_path = _chunk.get("rel_path") or _meta.get("rel_path", "")
                _ym = _year_dir_re.search(_rel_path) or _year_fname_re.search(_rel_path)
                if _ym:
                    _yr = int(_ym.group(1))
                    if 2010 <= _yr <= 2030:
                        _chunk["year"] = _yr
                        _meta["year"] = _yr
                        _year_patched += 1
        logger.info(f"Year backfill: patched {_year_patched} chunks from path/filename")

        # Build provision index for O(1) direct section/rule lookup.
        # Maps citation key (e.g. "CGST_SEC_16") → list of chunk indices.
        # Built once at startup; each query with explicit citations does a
        # dict lookup instead of a linear scan over all chunks.
        self._provision_index: dict = {}
        for _ci, _chunk in enumerate(self.chunks):
            _meta = _chunk.get("metadata", {})
            # Accept both old "provisions"/"citations" schema and new "provision_keys"
            # schema used by the Database_V2.0 corpus (ingested 2026-08-19+).
            _refs = set(
                (_meta.get("provisions") or [])
                + (_meta.get("citations") or [])
                + (_meta.get("provision_keys") or [])
            )
            for _ref in _refs:
                # Skip generic sentinel keys — they match everything, not useful
                if _ref and _ref not in ("ACT", "RULES", "NOTIFICATION"):
                    if _ref not in self._provision_index:
                        self._provision_index[_ref] = []
                    self._provision_index[_ref].append(_ci)
        logger.info(f"Provision index built: {len(self._provision_index)} citation keys")

        # Build circular number index for O(1) direct circular lookup.
        # Maps "CIRCULAR_183" → list of chunk indices from circular filenames.
        # Covers patterns: Circular-No-183, cir-183, circular-cgst-183, circularno-183.
        self._circular_index: dict = {}
        _cir_num_re = re.compile(
            # Handles: "Circular No. 183", "cir-252", "Cir251" (no sep), "circularno-183"
            r'(?:circular[s]?[-_.\s]*(?:[a-z]*[-_.\s]*)?(?:no[-_.\s]*)?'
            r'|cir[-_.](?:cgst[-_.])?'   # cir-252, cir_cgst_183
            r'|cir(?=[0-9])'              # Cir251 — no separator before digits
            r'|circularno[-_.])'
            r'(\d{2,3})',
            re.IGNORECASE,
        )
        _cir_leading_re = re.compile(r'^(\d{2,3})[-_]\d+[-_]\d{4}', re.IGNORECASE)
        for _ci, _chunk in enumerate(self.chunks):
            _meta = _chunk.get("metadata", {})
            _cat = (_meta.get("category") or "").lower()
            _dtype = (_meta.get("document_type") or "").lower()
            _rel = _chunk.get("rel_path") or _meta.get("rel_path", "")
            # Also check rel_path: 1,541 circular-file chunks were tagged document_type="Statute"
            # (because the chunker classified the quoted statutory text, not the container doc).
            if "circular" not in _cat and "circular" not in _dtype and "circular" not in _rel.lower():
                continue
            _fname = _rel.split("/")[-1].split("\\")[-1] if _rel else ""
            _m = _cir_num_re.search(_fname) or _cir_leading_re.match(_fname)
            if _m:
                _key = f"CIRCULAR_{_m.group(1)}"
                if _key not in self._circular_index:
                    self._circular_index[_key] = []
                if _ci not in self._circular_index[_key]:
                    self._circular_index[_key].append(_ci)
        logger.info(f"Circular index built: {len(self._circular_index)} circular numbers indexed")

        # ── TF-IDF matrix (3rd RRF signal) — background build ────────────────
        # TF-IDF assigns ultra-high scores to rare legal tokens — specific circular
        # numbers ("Circular 107"), section codes ("16(2)(c)"), and CBIC trade
        # notice numbers appear in very few chunks, so their IDF weight is huge.
        # When a user's query contains such a term, TF-IDF pulls the exact circular
        # or section to the top of the candidate pool before the CrossEncoder runs.
        # Using sublinear_tf=True prevents very long circular documents from being
        # penalised by their raw term count (log(1+tf) instead of raw tf).
        # ngram_range=(1,2) captures two-word legal phrases ("input credit",
        # "reverse charge", "section 16") as single high-IDF tokens.
        # Memory: sparse matrix ~150-250 MB for 60K chunks — acceptable for ECS.
        #
        # Built in a daemon thread so startup does NOT block FastAPI's health check.
        # search() checks `self._tfidf is not None` before using it — queries that
        # arrive before the build finishes fall back to 2-way RRF (FAISS + BM25)
        # gracefully. Typically ready within 30–90 seconds of container start.
        self._tfidf = None        # sentinel — set last in thread (acts as ready flag)
        self._tfidf_matrix = None

        def _build_tfidf_background(chunks_snapshot: list) -> None:
            try:
                import threading
                logger.info(
                    f"[TF-IDF bg] Building on thread {threading.current_thread().name} ..."
                )
                from sklearn.feature_extraction.text import TfidfVectorizer
                _corpus_texts = [c.get("text", "") for c in chunks_snapshot]
                _vec = TfidfVectorizer(
                    max_features=60000,
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                    dtype=np.float32,
                )
                _mat = _vec.fit_transform(_corpus_texts)
                # Assign matrix BEFORE vectorizer — search() uses vectorizer as
                # the "ready" sentinel (getattr check), so the matrix must already
                # be visible when the sentinel flips. Python GIL makes each attr
                # assignment atomic; ordering here is intentional.
                self._tfidf_matrix = _mat
                self._tfidf = _vec          # ← ready flag flips here
                logger.info(
                    f"[TF-IDF bg] Done: {_mat.shape[0]} docs × {_mat.shape[1]} "
                    f"features | nnz={_mat.nnz:,}"
                )
            except Exception as _e:
                logger.warning(f"[TF-IDF bg] Build failed (non-fatal, will skip): {_e}")

        import threading as _threading
        _t = _threading.Thread(
            target=_build_tfidf_background,
            args=(list(self.chunks),),   # snapshot to avoid concurrent mutation
            daemon=True,
            name="tfidf-builder",
        )
        _t.start()
        logger.info("[TF-IDF bg] Background build thread started — "
                    "3rd RRF signal will be active within ~30-90 s")

        # ── Circular-isolated BM25 index ──────────────────────────────────────
        # The full-corpus BM25 systematically underscores circulars relative to
        # statute chunks: statute chunks are shorter and term-dense, so every
        # query keyword gets a higher BM25 contribution per document-length unit.
        # A separate BM25 index over ONLY circular+notification chunks normalises
        # length within that sub-corpus, surfaces the most keyword-relevant
        # circulars, and injects them unconditionally into the CrossEncoder pool.
        # This is the single most impactful fix for circular recall: it ensures
        # the CrossEncoder SEES the right circulars instead of ranking them after
        # the fact via Layer 5 blind injection.
        logger.info("Building circular-isolated BM25 index...")
        self._bm25_circ_idx_map: list = [
            i for i, c in enumerate(self.chunks)
            if _chunk_category(c) in ("circular", "notification")
        ]
        if self._bm25_circ_idx_map:
            _circ_tok_corpus = [
                tokenize_text(self.chunks[i].get("text", ""))
                for i in self._bm25_circ_idx_map
            ]
            self._bm25_circulars = BM25Okapi(_circ_tok_corpus)
            logger.info(
                f"Circular BM25 built: {len(self._bm25_circ_idx_map)} "
                f"circular/notification chunks indexed"
            )
        else:
            self._bm25_circulars = None
            logger.warning("No circular/notification chunks found — circular BM25 skipped")

        # ── Statute-isolated BM25 index ───────────────────────────────────────
        # The full-corpus BM25 is dominated by case_law (56% of chunks in the
        # Database_V2.0 corpus).  Case law chunks discuss the same statutory
        # keywords ("section 16", "ITC", "reverse charge") but should rank below
        # the actual statute text for tax-law queries.  A statute-only BM25
        # index normalises length within the statute sub-corpus and ensures the
        # most keyword-relevant statute chunk always reaches the CrossEncoder pool.
        logger.info("Building statute-isolated BM25 index...")
        self._bm25_stat_idx_map: list = [
            i for i, c in enumerate(self.chunks)
            if _chunk_category(c) == "statute"
        ]
        if self._bm25_stat_idx_map:
            _stat_tok_corpus = [
                tokenize_text(self.chunks[i].get("text", ""))
                for i in self._bm25_stat_idx_map
            ]
            self._bm25_statutes = BM25Okapi(_stat_tok_corpus)
            logger.info(
                f"Statute BM25 built: {len(self._bm25_stat_idx_map)} statute chunks indexed"
            )
        else:
            self._bm25_statutes = None
            logger.warning("No statute chunks found — statute BM25 skipped")

        # ── Notification-isolated BM25 index ──────────────────────────────────
        # Rate notifications (HSN codes, rate schedules, exemption entries) use
        # very different vocabulary from circulars and statutes.  A combined
        # circular+notification BM25 index is dominated by the 1760 circular
        # chunks; a notification-only index (510 chunks) surfaces the most
        # relevant rate notification for queries about GST rates, SAC codes,
        # exemptions, and schedules.
        logger.info("Building notification-isolated BM25 index...")
        self._bm25_notif_idx_map: list = [
            i for i, c in enumerate(self.chunks)
            if _chunk_category(c) == "notification"
        ]
        if self._bm25_notif_idx_map:
            _notif_tok_corpus = [
                tokenize_text(self.chunks[i].get("text", ""))
                for i in self._bm25_notif_idx_map
            ]
            self._bm25_notifications = BM25Okapi(_notif_tok_corpus)
            logger.info(
                f"Notification BM25 built: {len(self._bm25_notif_idx_map)} notification chunks indexed"
            )
        else:
            self._bm25_notifications = None
            logger.warning("No notification chunks found — notification BM25 skipped")

        # ── Circular-isolated FAISS sub-index ─────────────────────────────────
        # BM25-only circular injection misses circulars that use different
        # terminology from the query ("clarification" vs "interpretation", formal
        # CBIC language vs user query language).  A semantic FAISS search within
        # the circular sub-corpus finds the right circular even when exact keywords
        # don't match — this is the root fix for irrelevant circular injection.
        #
        # Vectors are reconstructed from the main IndexFlatIP — zero re-embedding,
        # zero model calls.  reconstruct() on IndexFlatIP is effectively a memcpy.
        # Reuses _bm25_circ_idx_map for local-to-global index mapping.
        logger.info("Building circular-isolated FAISS sub-index (semantic)...")
        self._faiss_circulars = None
        if self._bm25_circ_idx_map and self.index is not None:
            try:
                _dim = self.index.d
                _n_circ = len(self._bm25_circ_idx_map)
                _circ_vecs = np.empty((_n_circ, _dim), dtype=np.float32)
                for _li, _gi in enumerate(self._bm25_circ_idx_map):
                    self.index.reconstruct(_gi, _circ_vecs[_li])
                _circ_sub = faiss.IndexFlatIP(_dim)
                _circ_sub.add(_circ_vecs)
                self._faiss_circulars = _circ_sub
                logger.info(
                    f"Circular FAISS sub-index: {_n_circ} chunks | "
                    f"~{_n_circ * _dim * 4 // (1024 * 1024):.0f} MB"
                )
            except Exception as _e:
                logger.warning(
                    f"Circular FAISS sub-index failed (non-fatal, BM25 still covers): {_e}"
                )

        # ── Statute-isolated FAISS sub-index ──────────────────────────────────
        # Guarantees statute chunks (Acts, Rules) always reach the CrossEncoder
        # pool even when the main FAISS search is dominated by circular language
        # (e.g. a query about "cross charge" pulls towards Circular 199 language
        # while Section 25(4)/(5) CGST Act chunks rank lower semantically).
        # Zero re-embedding — reconstruct() on IndexFlatIP is a memcpy.
        logger.info("Building statute-isolated FAISS sub-index...")
        self._faiss_statutes = None
        self._statute_idx_map: list = [
            i for i, c in enumerate(self.chunks)
            if _chunk_category(c) == "statute"
        ]
        if self._statute_idx_map and self.index is not None:
            try:
                _dim = self.index.d
                _n_stat = len(self._statute_idx_map)
                _stat_vecs = np.empty((_n_stat, _dim), dtype=np.float32)
                for _li, _gi in enumerate(self._statute_idx_map):
                    self.index.reconstruct(_gi, _stat_vecs[_li])
                _stat_sub = faiss.IndexFlatIP(_dim)
                _stat_sub.add(_stat_vecs)
                self._faiss_statutes = _stat_sub
                logger.info(
                    f"Statute FAISS sub-index: {_n_stat} chunks | "
                    f"~{_n_stat * _dim * 4 // (1024 * 1024):.0f} MB"
                )
            except Exception as _e:
                logger.warning(f"Statute FAISS sub-index failed (non-fatal): {_e}")

        # ── Notification-isolated FAISS sub-index ─────────────────────────────
        # Rate notifications use very different language from circulars and Acts
        # (HS codes, rate schedules, entry numbers) — a shared FAISS pool
        # underserves rate/exemption queries.  Isolated search ensures the most
        # relevant notification chunk always competes in the CrossEncoder pool.
        logger.info("Building notification-isolated FAISS sub-index...")
        self._faiss_notifications = None
        self._notif_idx_map: list = [
            i for i, c in enumerate(self.chunks)
            if _chunk_category(c) == "notification"
        ]
        if self._notif_idx_map and self.index is not None:
            try:
                _dim = self.index.d
                _n_notif = len(self._notif_idx_map)
                _notif_vecs = np.empty((_n_notif, _dim), dtype=np.float32)
                for _li, _gi in enumerate(self._notif_idx_map):
                    self.index.reconstruct(_gi, _notif_vecs[_li])
                _notif_sub = faiss.IndexFlatIP(_dim)
                _notif_sub.add(_notif_vecs)
                self._faiss_notifications = _notif_sub
                logger.info(
                    f"Notification FAISS sub-index: {_n_notif} chunks | "
                    f"~{_n_notif * _dim * 4 // (1024 * 1024):.0f} MB"
                )
            except Exception as _e:
                logger.warning(f"Notification FAISS sub-index failed (non-fatal): {_e}")

        # ── Case-law FAISS sub-index ───────────────────────────────────────────
        # Judgments use very different language (finding facts, ratio decidendi,
        # distinguished / followed) vs statutes and circulars.  Isolated search
        # finds the most semantically relevant HC/SC judgment for litigation and
        # draft-mode queries without competing against statute language.
        logger.info("Building case-law FAISS sub-index...")
        self._faiss_case_laws = None
        self._case_law_idx_map: list = [
            i for i, c in enumerate(self.chunks)
            if _chunk_category(c) == "case_law"
        ]
        if self._case_law_idx_map and self.index is not None:
            try:
                _dim = self.index.d
                _n_cl = len(self._case_law_idx_map)
                _cl_vecs = np.empty((_n_cl, _dim), dtype=np.float32)
                for _li, _gi in enumerate(self._case_law_idx_map):
                    self.index.reconstruct(_gi, _cl_vecs[_li])
                _cl_sub = faiss.IndexFlatIP(_dim)
                _cl_sub.add(_cl_vecs)
                self._faiss_case_laws = _cl_sub
                logger.info(
                    f"Case-law FAISS sub-index: {_n_cl} chunks | "
                    f"~{_n_cl * _dim * 4 // (1024 * 1024):.0f} MB"
                )
            except Exception as _e:
                logger.warning(f"Case-law FAISS sub-index failed (non-fatal): {_e}")

        # Build full-corpus document map for context window expansion.
        # Maps rel_path → sorted list of (page_num, chunk_index).
        # Built once at startup so every query can fetch neighbors from the
        # entire corpus by index, not just from the 80-chunk retrieval pool.
        self._doc_map: dict = {}
        for _ci, _chunk in enumerate(self.chunks):
            _meta = _chunk.get("metadata", {})
            _rel = _chunk.get("rel_path") or _meta.get("rel_path", "")
            if not _rel:
                continue
            _pages = _chunk.get("pages") or _meta.get("pages") or []
            _page = min(_pages) if _pages else (
                _chunk.get("page") or _meta.get("page") or 0
            )
            if _rel not in self._doc_map:
                self._doc_map[_rel] = []
            self._doc_map[_rel].append((_page, _ci))
        for _rel in self._doc_map:
            self._doc_map[_rel].sort(key=lambda x: x[0])
        logger.info(
            f"Doc map built: {len(self._doc_map)} documents, "
            f"{len(self.chunks)} total chunks"
        )

        # ms-marco-MiniLM-L-6-v2: trained for passage ranking (single float per pair,
        # higher = more relevant).  CPU-fast: ~150-400ms for 50 pairs at 512 tokens.
        # Replaced cross-encoder/nli-deberta-v3-large which is an NLI model that
        # outputs 3-class probability arrays — float(score) always threw, leaving
        # _rerank_score unset and making all chunks score identically.
        logger.info("Loading CrossEncoder reranker (cross-encoder/ms-marco-MiniLM-L-6-v2)...")
        try:
            import torch as _torch
            _ce_device = "cuda" if _torch.cuda.is_available() else "cpu"
            logger.info(f"  CrossEncoder device: {_ce_device}")
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder(
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
                max_length=512,
                device=_ce_device,
            )
            logger.info("  CrossEncoder loaded: cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            logger.error(f"Failed to load CrossEncoder: {e}", exc_info=True)
            self.cross_encoder = None

        # Initialize Layer 1 (Statute-First) and pre-build its citation lookup so
        # search_statutes() uses O(unique_citations) instead of O(n_chunks) per request.
        self.statute_retriever = StatuteRetriever()
        self.statute_retriever.build_lookup(self.chunks)

        # Initialize Provision Graph
        graph_path = Path(chunks_path).parent.parent / "graph" / "edges.jsonl"
        self.graph_retriever = ProvisionGraphRetriever(graph_path)

        # ── Citation Graph (Priority 2+5) ─────────────────────────────────────
        # Two-layer graph of provision relationships.
        # Layer 1: seeded from authority taxonomy (Circular 199 ↔ Rule 28 ↔ Section 25)
        # Layer 2: co-citation edges mined from chunk metadata (zero re-embedding)
        # Used at query time: when a provision is retrieved, graph neighbours are
        # automatically fetched as additional candidates.
        logger.info("Building citation graph (taxonomy + corpus co-citations)...")
        try:
            self._citation_graph = DocumentCitationGraph(GST_GOVERNING_AUTHORITIES)
            self._citation_graph.build_from_chunks(self.chunks)
            _cg_stats = self._citation_graph.stats()
            logger.info(
                f"Citation graph ready: {_cg_stats['nodes']} nodes | "
                f"{_cg_stats['documents_indexed']} docs | "
                f"{_cg_stats['unique_provisions_cited']} provision keys"
            )
        except Exception as _cge:
            logger.warning(f"Citation graph build failed (non-fatal): {_cge}")
            self._citation_graph = None

        logger.info("Retriever initialized: 3-Layer Architecture + Provision Graph + Citation Graph + MMR")

    def _cascade_rerank(self, query: str, candidates: list,
                        stage1_keep: int = 30,
                        taxonomy: dict | None = None) -> list:
        """
        Reranks candidates with cross-encoder/nli-deberta-v3-large CrossEncoder.
        Falls back to RRF score order if CrossEncoder is unavailable.

        taxonomy: result of classify_query_authority() — when provided, authority
        bonuses are adjusted per query intent (e.g. notifications get a larger
        bonus for rate queries; circulars get a larger bonus for cross-charge
        advisory queries).
        """
        _taxonomy = taxonomy or {}
        pool = list(candidates)
        if self.cross_encoder and pool:
            try:
                pairs = [
                    (query, (c.get("context_text") or c.get("text", ""))[:512])
                    for c in pool
                ]
                scores = self.cross_encoder.predict(pairs, show_progress_bar=False)
                for chunk, score in zip(pool, scores):
                    # RRF tiebreaker: chunk ranked high in both FAISS and BM25
                    rrf_boost = chunk.get("_rrf_score", 0.0) * 0.01
                    # Intent-dependent authority bonus:
                    #   base = source_priority × 0.03 (Acts=0.15, Circulars=0.12…)
                    #   multiplied by per-category weight from authority taxonomy
                    #   so for rate queries notifications get 1.6× and Acts 0.8×,
                    #   for cross-charge circulars get 1.4×, etc.
                    _rel = chunk.get("rel_path") or chunk.get("metadata", {}).get("rel_path", "")
                    _pri = source_priority(_rel)
                    _auth_bonus = authority_bonus(_rel, _taxonomy, _pri)
                    chunk["_rerank_score"] = float(score) + rrf_boost + _auth_bonus
                pool.sort(key=lambda c: c["_rerank_score"], reverse=True)
                logger.debug(
                    f"CrossEncoder reranked {len(pool)} chunks | "
                    f"top={pool[0]['_rerank_score']:.3f}"
                )
            except Exception as e:
                logger.warning(f"CrossEncoder rerank failed: {e}")
        return pool

    def _enforce_pool_quotas(self, pool: list, query: str, quotas: dict) -> list:
        """
        Guarantee minimum chunks from each document category — BUT ONLY from
        chunks that actually score above the BM25 relevance threshold.

        Statutes (Acts/Rules) get an unconditional floor because they are
        the legal foundation for every GST answer.  Circulars/notifications
        only fill the quota if the BM25 cross-encoder agrees they are
        topically relevant — this prevents irrelevant circulars being forced
        into a pure statutory answer (e.g. "define supply") and displacing
        better-ranked Acts chunks from the 80-candidate reranker window.

        min_bm25_by_cat: per-category BM25 score floor.
          statute / case_law = 0.0  (always include to ensure legal foundation)
          circular / notification = 1.5 (only add if there is real keyword overlap)
        """
        MIN_BM25 = {"statute": 0.0, "case_law": 0.0, "circular": 1.5, "notification": 1.5}

        by_cat = {"statute": [], "case_law": [], "circular": [], "notification": [], "other": []}
        for chunk in pool:
            by_cat[_chunk_category(chunk)].append(chunk)

        seen_ids = {c.get("chunk_id") for c in pool}
        result = list(pool)  # start with the full pool

        if self.bm25:
            tokenized_query = tokenize_text(_expand_for_bm25(query))
            bm25_scores = self.bm25.get_scores(tokenized_query)

            for cat, quota in quotas.items():
                have = len(by_cat[cat])
                if have >= quota:
                    continue  # already enough — no action needed

                needed = quota - have
                min_score = MIN_BM25.get(cat, 0.0)

                # Build sorted list of (chunk_index, score) for this category,
                # filtered by the per-category BM25 floor.
                cat_indices = [
                    (i, bm25_scores[i])
                    for i, c in enumerate(self.chunks)
                    if _chunk_category(c) == cat and bm25_scores[i] >= min_score
                ]
                cat_indices.sort(key=lambda x: x[1], reverse=True)

                added = 0
                for idx, score in cat_indices:
                    if added >= needed:
                        break
                    chunk = self.chunks[idx].copy()
                    cid = chunk.get("chunk_id")
                    if cid and cid not in seen_ids:
                        chunk["_targeted_fill"] = True
                        chunk["_fill_category"] = cat
                        result.append(chunk)
                        seen_ids.add(cid)
                        added += 1

                if added:
                    logger.info(
                        f"Pool quota fill: +{added} {cat} chunks "
                        f"(had {have}, needed {quota}, min_bm25={min_score})"
                    )
                elif have < quota:
                    logger.debug(
                        f"Pool quota fill: no relevant {cat} chunks above "
                        f"BM25={min_score} — query may not need {cat} documents"
                    )

        return result

    def _direct_ref_lookup(self, refs: list, anchor_score: float = 0.05) -> list:
        """
        Returns chunks that explicitly cite any of the given provision keys,
        using the pre-built provision index for O(1) lookup per key.
        CIRCULAR_N keys are resolved via _circular_index (filename-based).
        These chunks are pinned at the top of combined_results.

        P2.5 (Provision Anchoring 2026-08-11):
          anchor_score: every pinned chunk receives this as _debug_score so that
          after source-type weighting (statute × 1.5) it beats typical AAR/ICAI
          chunks (RRF ~0.04 × 0.75 = 0.030) in the _final_legal_score sort.
          Without this, pinned chunks have _base=0 and are cut by MMR.

          IGST alias: IGST chunks were ingested with CGST_SEC_* provision keys
          (ingestion bug).  When IGST_SEC_X is not found in _provision_index,
          we also try CGST_SEC_X but only return chunks from paths containing
          'igst' so CGST Act sections are not confused with IGST ones.

          P2.5b (Provision Index Priority 2026-08-11):
          Each provision key may have hundreds of entries (CGST_SEC_9 has 709).
          Without sorting, the first 30 pinned chunks are dominated by case_law
          and ICAI commentary that merely cite the section. We need the actual
          statute text chunks first. Priority order:
            0 = statute path (Act/, igst/, cgst/, rules/, etc.)
            1 = ICAI bare-law mega-PDF (actual statute/rule text despite icai/ path)
            2 = circulars / notifications (official but secondary)
            3 = AAR / HC / SC / other commentary (should not be primary statute anchor)

        Capped at 30 to allow full provision coverage across 5-6 taxonomy refs.
        """
        # IGST Act chunks were ingested with CGST_SEC_* keys (ingestion bug).
        # Map IGST_SEC_X → also search CGST_SEC_X limited to igst/ path chunks.
        _IGST_ALIAS = {
            f"IGST_SEC_{n}": f"CGST_SEC_{n}"
            for n in range(1, 30)
        }

        if not refs or not hasattr(self, "_provision_index"):
            return []
        seen_ids: set = set()
        pinned = []

        # P2.5b: Priority-sort indices so statute text chunks are pinned first.
        # NOTE: "export/" intentionally removed — the export/ folder contains CBIC
        # circulars (e.g. Circular_161, Circular 202).  Giving them priority 0 (same
        # as Act text) caused Export circulars to crowd out shorter-but-substantive
        # statute chunks (e.g. CGST Act Section 8, len=496) from the _PER_KEY_CAP=3
        # slots.  Export circulars now fall to priority 2 (official), which is correct.
        # Paths that identify actual statute text (Acts, Rules).
        # Covers both legacy flat folder names and Database_V2.0 versioned names
        # ("Database_V2.0/CGST Acts/", "Database_V2.0/CGST Rules 10-08-2026/", etc.)
        _STATUTE_PATH_PREFIXES = (
            "act/", "igst/", "cgst/", "rules/", "utgst/",  # legacy
            "database_v2.0/cgst acts/", "database_v2.0/igst acts/",  # V2.0 Acts
            "database_v2.0/cgst rules", "database_v2.0/igst rules",  # V2.0 Rules
        )
        _OFFICIAL_PATH_PREFIXES = ("circular", "notification")

        def _idx_sort_key(idx: int):
            """Lower = pinned first.
            Primary: statute text > ICAI bare-law > circulars/notifs > AAR.
            Secondary: longer text wins within the same priority tier — this ensures
            content-rich chunks (section 9(3) with 'reverse charge' text) are pinned
            before near-empty section headers ('section 9 9').
            """
            if idx >= len(self.chunks):
                return (9, 0)
            c = self.chunks[idx]
            _rp = (c.get("rel_path") or
                   c.get("metadata", {}).get("rel_path", "")).replace("\\", "/").lower()
            if any(_rp.startswith(p) for p in _STATUTE_PATH_PREFIXES):
                pri = 0   # actual statute text
            elif "icai" in _rp and "bare law" in _rp:
                pri = 1   # ICAI bare-law mega-PDF — contains actual rules text
            else:
                first = _rp.split("/")[0] if "/" in _rp else _rp[:20]
                if any(first.startswith(p) for p in _OFFICIAL_PATH_PREFIXES):
                    pri = 2   # official circular / notification
                else:
                    pri = 3   # AAR, HC, SC, ICAI commentary — low priority for statute pin
            _tlen = len(c.get("content") or c.get("text") or "")
            return (pri, -_tlen)   # negative so longer text sorts first within tier

        # Keep backward-compat alias used outside this function
        def _idx_priority(idx: int) -> int:
            return _idx_sort_key(idx)[0]

        def _pin(idx: int, provision_key: str, is_alias: bool = False) -> bool:
            if idx >= len(self.chunks):
                return False
            chunk = self.chunks[idx]
            # If this is an IGST alias lookup, only accept chunks from igst/ path
            if is_alias:
                _rp = (chunk.get("rel_path") or
                       chunk.get("metadata", {}).get("rel_path", "")).replace("\\", "/").lower()
                if not _rp.startswith("igst/"):
                    return False
            cid = chunk.get("chunk_id")
            if cid and cid not in seen_ids:
                c = chunk.copy()
                c["_pinned_by_ref"]    = True
                c["_statute_priority"] = 1.0
                c["_anchor_provision"] = provision_key   # which provision key found this
                c["_debug_score"]      = anchor_score    # P2.5: ensures survival past MMR
                pinned.append(c)
                seen_ids.add(cid)
                return True
            return False

        # P2.5b: per-key cap limits how many chunks a single provision key can pin.
        # Without this, CGST_SEC_9 (709 entries, 104 statute) fills all 30 slots
        # with Section 9 statute chunks (text="section 9 9"), crowding out FAISS
        # results that supply notifications, keywords, and sub-section content.
        # A per-key cap of 3 leaves semantic search results room in the final context.
        _PER_KEY_CAP   = 3    # max chunks pinned per provision key
        _GLOBAL_CAP    = 20   # max total pinned chunks across all keys

        for ref in refs:
            _ref_count = 0  # track per-key count

            # Primary lookup: metadata provision keys (CGST_SEC_16, CGST_RUL_89, etc.)
            # P2.5b: sort by statute-path priority so Act/ chunks are pinned before AAR/ICAI
            _raw_indices = self._provision_index.get(ref, [])
            _sorted_indices = sorted(_raw_indices, key=_idx_sort_key)
            for idx in _sorted_indices:
                if _ref_count >= _PER_KEY_CAP:
                    break
                if _pin(idx, ref):
                    _ref_count += 1
                if len(pinned) >= _GLOBAL_CAP:
                    return pinned

            # IGST alias: when IGST_SEC_X is absent (ingestion labelled it CGST_SEC_X),
            # find the CGST-keyed entry but filter to igst/ path only.
            if ref in _IGST_ALIAS and not self._provision_index.get(ref):
                alias_key = _IGST_ALIAS[ref]
                _alias_indices = sorted(
                    self._provision_index.get(alias_key, []), key=_idx_sort_key
                )
                for idx in _alias_indices:
                    if _ref_count >= _PER_KEY_CAP:
                        break
                    if _pin(idx, ref, is_alias=True):
                        _ref_count += 1
                    if len(pinned) >= _GLOBAL_CAP:
                        return pinned

            # Circular number keys (CIRCULAR_183) — resolved from filename-based index
            if ref.startswith("CIRCULAR_") and hasattr(self, "_circular_index"):
                for idx in self._circular_index.get(ref, []):
                    if _ref_count >= _PER_KEY_CAP:
                        break
                    if _pin(idx, ref):
                        _ref_count += 1
                    if len(pinned) >= _GLOBAL_CAP:
                        return pinned
        return pinned

    def search(self, query: str, top_k: int = 50, allowed_sources=None, advanced_queries=None, domain_paths=None, is_draft: bool = False, skip_rerank: bool = False, trace=None):
        # trace: Optional[RetrievalTrace] — full pipeline provenance recorder.
        # Passing None (default) disables all recording; zero retrieval-behavior change.
        if not query or not query.strip():
            logger.warning("search() called with empty query")
            return []

        if not self.index or not self.bm25:
            logger.warning("search() called but retriever is not initialized (missing index/bm25)")
            return []

        import time
        from app.ai_logger import update_ai_log
        t_start = time.monotonic()

        # --- 1. Query Topic & Subtopic (from pre-computed advanced_queries, no extra LLM call) ---
        topic = "General"
        subtopic = None
        if advanced_queries:
            topic = advanced_queries.get("topic", "General")
            subtopic = advanced_queries.get("subtopic")

        # --- Topic Ontology expansion (Priority 8) ---
        # Adds keywords from parent/sibling ontology nodes.
        # Example: "ISD mechanism" → also includes "cross charge", "distinct person",
        # "input tax credit" so BM25 surfaces broader context.
        # FAISS uses the original query (ontology expansion degrades cosine sim);
        # BM25 uses the ontology-expanded query for wider keyword coverage.
        _ontology_expanded_query, _ontology_added = expand_query_with_ontology(query)
        if _ontology_added:
            logger.info(f"Ontology expansion: +{len(_ontology_added)} terms {_ontology_added[:5]}")
        # bm25_query is the expanded version; faiss_query stays as raw query
        _bm25_query = _ontology_expanded_query

        # --- Governing-Authority Prediction ---
        # Classifies the query into the GST authority taxonomy and predicts WHICH
        # specific sections, rules, and circulars govern this topic — without waiting
        # for retrieval to find them.  This is the "practitioner knowledge graph":
        # a cross-charge question → immediately know Section 25(4)/(5), Rule 28,
        # Rule 39, Section 20, Circular 199 must all be in the pool.
        _taxonomy = classify_query_authority(query)
        if _taxonomy["confidence"] > 0:
            logger.info(
                f"Authority taxonomy: topics={_taxonomy['topics']} "
                f"sections={_taxonomy['sections']} rules={_taxonomy['rules']} "
                f"circulars={_taxonomy['circulars']} conf={_taxonomy['confidence']}"
            )

        # --- Direct section/rule reference lookup (pinned, bypasses FAISS ranking) ---
        # Combines: (a) explicit citations from the query text itself, and
        #           (b) predicted governing authorities from the taxonomy.
        # These chunks are pinned so they always reach the CrossEncoder.
        _explicit_refs = _extract_query_refs(query)

        # --- Priority 13: LLM-based Generic Provision Resolver ---
        # resolve_provisions() was removed; taxonomy + explicit refs cover this role.
        # Kept as an empty list so downstream code that unions _llm_refs is unaffected.
        _llm_refs: list[str] = []

        _taxonomy_refs = (
            _taxonomy["sections"] + _taxonomy["rules"] +
            [f"CIRCULAR_{c.split('_')[-1]}" if c.startswith("CIRCULAR_") else c
             for c in _taxonomy["circulars"]]
        )
        # Order: explicit (highest confidence) → LLM-resolved → taxonomy (fallback)
        _query_refs = list(dict.fromkeys(_explicit_refs + _llm_refs + _taxonomy_refs))  # dedup, preserve order
        _pinned = self._direct_ref_lookup(_query_refs) if _query_refs else []
        if _pinned:
            logger.info(
                f"Direct ref lookup (explicit={len(_explicit_refs)} llm={len(_llm_refs)} "
                f"taxonomy={len(_taxonomy_refs)}): {_query_refs[:8]} → {len(_pinned)} pinned chunks"
            )

        # --- Layer 1: Statute-First Retrieval (Deterministic) ---
        statute_results = self.statute_retriever.search_statutes(self.chunks, topic, subtopic)

        # --- Provision Graph Expansion ---
        graph_results = []
        if statute_results:
            matched_provisions = []
            for res in statute_results:
                matched_provisions.extend(res.get("_matched_provisions", []))

            if matched_provisions:
                graph_results = self.graph_retriever.expand_results(self.chunks, matched_provisions)
                for res in graph_results:
                    res["_is_graph_expanded"] = True
                    res["_statute_priority"] = 0.8

        # --- Layer 2: Broad Semantic Retrieval (Vector + BM25) ---
        candidate_pool = []
        seen_chunk_ids = set()

        def _add_to_pool(idx):
            """Add chunk by index if not already in pool and index is valid."""
            if 0 <= idx < len(self.chunks):
                chunk = self.chunks[idx]
                rel_path = chunk.get("rel_path") or chunk.get("metadata", {}).get("rel_path", "")
                if rel_path in self.inactive_paths:
                    return
                cid = chunk.get("chunk_id")
                if cid and cid not in seen_chunk_ids:
                    seen_chunk_ids.add(cid)
                    candidate_pool.append(chunk.copy())

        # 1. Vector Search — primary query
        faiss_chunks: list = []
        query_vec = embed_query(query)
        if self.index and query_vec is not None:
            D, I = self.index.search(np.array([query_vec]).astype('float32'), VECTOR_SEARCH_TOP_K)
            for idx in I[0]:
                if 0 <= idx < len(self.chunks):
                    faiss_chunks.append(self.chunks[idx])
        # ── TRACE: FAISS results ────────────────────────────────────────────────
        if trace is not None and faiss_chunks and query_vec is not None:
            try:
                _faiss_sims = [float(D[0][i]) for i in range(len(faiss_chunks))]
                trace.record_faiss(faiss_chunks, _faiss_sims)
            except Exception:
                pass

        # 1b. Vector Search — expanded queries + HyDE document (added directly to pool,
        #     not merged via RRF because they have no BM25 counterpart ranking)
        if advanced_queries and self.index:
            extra_queries = advanced_queries.get("queries", [])[1:]
            hyde_doc = advanced_queries.get("hyde_document", "")
            if hyde_doc:
                extra_queries.append(hyde_doc)

            for eq in extra_queries:
                if not eq or not isinstance(eq, str) or not eq.strip():
                    continue
                eq_vec = embed_query(eq)
                if eq_vec is not None:
                    D2, I2 = self.index.search(np.array([eq_vec]).astype('float32'), VECTOR_EXPANDED_TOP_K)
                    for idx in I2[0]:
                        _add_to_pool(idx)

        # 2. BM25 Search — ontology-expanded query + abbreviation expansion for wider keyword coverage.
        # Ontology expansion adds parent/sibling concept keywords; abbrev expansion adds full forms.
        # FAISS uses the original query (cosine sim is more precise without expansion).
        bm25_chunks: list = []
        _bm25_tokenized_query = tokenize_text(_expand_for_bm25(_bm25_query))  # ontology + abbrev expanded; reused below
        if self.bm25:
            bm25_scores = self.bm25.get_scores(_bm25_tokenized_query)

            # ── Pseudo-Relevance Feedback (PRF) — free vocabulary gap bridge ──────
            # Pass 1: take top-3 BM25 chunks, extract their most distinctive terms
            # that aren't already in the query, and append them.
            # Pass 2: re-score with the augmented token list.
            # Effect: if the user says "unsold flats" but docs say "un-booked
            # apartments completion certificate", the PRF terms from pass-1 top
            # chunks pull the right documents up in pass-2.  BM25 is µs-fast so
            # two passes add < 1 ms on a 7 k-chunk corpus.
            try:
                _prf_top3_idxs = np.argsort(bm25_scores)[::-1][:3]
                _prf_texts = [
                    self.chunks[i].get('text', '')
                    for i in _prf_top3_idxs
                    if 0 <= i < len(self.chunks)
                ]
                _prf_extra = _prf_expand(_bm25_tokenized_query, _prf_texts)
                if _prf_extra:
                    logger.debug(f"PRF added {len(_prf_extra)} terms: {_prf_extra}")
                    _bm25_tokenized_query = _bm25_tokenized_query + _prf_extra
                    bm25_scores = self.bm25.get_scores(_bm25_tokenized_query)
            except Exception as _prf_err:
                logger.debug(f"PRF step failed (non-fatal): {_prf_err}")
            # ─────────────────────────────────────────────────────────────────────

            top_bm25_idxs = np.argsort(bm25_scores)[::-1][:BM25_TOP_K]
            for idx in top_bm25_idxs:
                if 0 <= idx < len(self.chunks):
                    bm25_chunks.append(self.chunks[idx])
        # ── TRACE: BM25 results ────────────────────────────────────────────────
        if trace is not None and bm25_chunks:
            try:
                _bm25_sims = [float(bm25_scores[top_bm25_idxs[i]]) for i in range(len(bm25_chunks))]
                trace.record_bm25(bm25_chunks, _bm25_sims)
            except Exception:
                pass

        # 2b. TF-IDF Search — 3rd RRF signal for exact legal citation matching.
        # TF-IDF assigns near-1.0 cosine similarity to chunks that contain the
        # exact rare legal terms from the query (specific circular numbers, section
        # references like "16(2)(c)", trade notice codes).  These chunks rise in
        # the RRF pool BEFORE the CrossEncoder, so the CrossEncoder sees the right
        # candidates — rather than discovering them only via Layer 5 blind injection.
        # Failure is non-fatal: if sklearn is unavailable, we fall back to 2-way RRF.
        tfidf_chunks: list = []
        if getattr(self, "_tfidf", None) is not None:
            try:
                from sklearn.metrics.pairwise import cosine_similarity as _cos_sim
                _q_vec = self._tfidf.transform([_expand_for_bm25(query)])
                _sims = _cos_sim(_q_vec, self._tfidf_matrix).flatten()
                # top-50 by TF-IDF similarity; skip zero-score chunks (no shared terms)
                _top_tfidf = np.argsort(_sims)[::-1][:50]
                tfidf_chunks = [
                    self.chunks[i]
                    for i in _top_tfidf
                    if _sims[i] > 0.0 and 0 <= i < len(self.chunks)
                ]
                logger.debug(
                    f"TF-IDF search: {len(tfidf_chunks)} candidates | "
                    f"top_sim={_sims[_top_tfidf[0]]:.4f}" if tfidf_chunks else
                    "TF-IDF search: 0 candidates"
                )
                # ── TRACE: TF-IDF results ──────────────────────────────────────
                if trace is not None and tfidf_chunks:
                    try:
                        _tfidf_sc = [float(_sims[i]) for i in _top_tfidf if _sims[i] > 0.0 and 0 <= i < len(self.chunks)]
                        trace.record_tfidf(tfidf_chunks, _tfidf_sc)
                    except Exception:
                        pass
            except Exception as _te:
                logger.warning(f"TF-IDF search failed (non-fatal): {_te}")

        # 2c. Reciprocal Rank Fusion — 3-way: FAISS + BM25 + TF-IDF.
        # A chunk present in all three ranked lists (semantically close, keyword-
        # matching, AND exact-citation-match) accumulates the highest composite RRF
        # score and reaches the CrossEncoder with high priority.  Chunks that only
        # appear in one list still contribute — this is additive, not eliminative.
        rrf_results = _rrf_combine(faiss_chunks, bm25_chunks, tfidf_chunks)
        for chunk in rrf_results:
            cid = chunk.get("chunk_id")
            if cid and cid not in seen_chunk_ids:
                seen_chunk_ids.add(cid)
                candidate_pool.append(chunk)
        # ── TRACE: RRF-merged pool ─────────────────────────────────────────────
        if trace is not None:
            try:
                trace.record_rrf(rrf_results)
            except Exception:
                pass

        # Filter by allowed_sources (file extension)
        if allowed_sources:
            candidate_pool = [
                c for c in candidate_pool
                if any(src.lower() in c.get("rel_path", c.get("metadata", {}).get("rel_path", "")).lower()
                       for src in allowed_sources)
            ]

        # Filter by domain_paths (RAG_INFORMATION_DATABASE sub-folder names).
        # Only applied when the router detected a specific domain; empty = no filter.
        if domain_paths:
            full_path_key = "source"
            filtered = [
                c for c in candidate_pool
                if any(
                    dp.lower() in c.get(full_path_key, "").lower()
                    or dp.lower() in c.get("rel_path", c.get("metadata", {}).get("rel_path", "")).lower()
                    for dp in domain_paths
                )
            ]
            # Only apply the domain filter when it keeps a meaningful subset;
            # fall back to the unfiltered pool if the filter is too aggressive.
            if len(filtered) >= max(3, top_k // 3):
                candidate_pool = filtered
            else:
                logger.debug(
                    f"domain_paths filter too aggressive ({len(filtered)} results) — skipping"
                )

        # ── Phase 2A: Enforce pool quotas — guarantee representation from all source types ──
        # Statutes always get a floor (Acts/Rules are the foundation of every GST answer).
        # Circulars/notifications only fill in when BM25 confirms topical relevance (see
        # _enforce_pool_quotas min_bm25 threshold) — prevents irrelevant circulars being
        # forced into a pure statutory answer and displacing better-ranked Acts chunks.
        _quotas = (
            {"statute": 10, "case_law": 8, "circular": 4, "notification": 3}
            if is_draft else
            {"statute": 6,  "case_law": 4, "circular": 4, "notification": 3}
        )
        candidate_pool = self._enforce_pool_quotas(candidate_pool, query, _quotas)

        # ── 2d. Circular-isolated BM25 injection (unconditional) ──────────────
        # Phase 2A (_enforce_pool_quotas) only injects circulars when full-corpus
        # BM25 score > 1.5 — a threshold that systematically excludes circulars
        # whose vocabulary differs from the query (e.g. the circular uses
        # "clarification" where the query uses "interpretation").
        # This step runs the circular-only BM25 — where length normalisation is
        # computed within the circular sub-corpus — and injects the top-N results
        # unconditionally.  No BM25 floor applies: we trust the circular-BM25
        # ranking to surface the best circular candidates for this query.
        # The CrossEncoder then scores them alongside statute chunks on equal footing.
        _CIRC_BM25_TOP_N = 8
        if getattr(self, "_bm25_circulars", None) is not None:
            try:
                _circ_scores = self._bm25_circulars.get_scores(_bm25_tokenized_query)
                _circ_top_local = np.argsort(_circ_scores)[::-1][:_CIRC_BM25_TOP_N]
                _circ_injected = 0
                for _local_idx in _circ_top_local:
                    _score = float(_circ_scores[_local_idx])
                    if _score <= 0.0:
                        continue   # no keyword overlap at all — skip
                    _global_idx = self._bm25_circ_idx_map[_local_idx]
                    if not (0 <= _global_idx < len(self.chunks)):
                        continue
                    _c = self.chunks[_global_idx].copy()
                    _cid = _c.get("chunk_id")
                    if _cid and _cid not in seen_chunk_ids:
                        _c["_circ_bm25_inject"] = True
                        _c["_circ_bm25_score"] = _score
                        candidate_pool.append(_c)
                        seen_chunk_ids.add(_cid)
                        _circ_injected += 1
                        # ── TRACE ────────────────────────────────────────────
                        if trace is not None:
                            try:
                                trace.record_injected(_c, "circular_bm25", score=_score)
                            except Exception:
                                pass
                if _circ_injected:
                    logger.info(
                        f"Circular BM25 inject: +{_circ_injected} circular/notification "
                        f"chunks (top score={float(_circ_scores[_circ_top_local[0]]):.3f})"
                    )
            except Exception as _ce:
                logger.warning(f"Circular BM25 injection failed (non-fatal): {_ce}")

        # ── 2d2. Statute-isolated BM25 injection (unconditional) ─────────────
        # Mirrors 2d above for statutes.  The full-corpus BM25 is dominated by
        # case_law (4274 of 7631 chunks = 56%) whose judgments discuss every
        # statutory section by name — so for a query about "Section 16 ITC" the
        # BM25 top-35 is mostly case_law rather than the CGST Act text itself.
        # Running BM25 within the statute sub-corpus (1087 chunks, length-
        # normalised within that set) ensures the most keyword-relevant statute
        # chunk always enters the CrossEncoder pool alongside the circular results.
        _STAT_BM25_TOP_N = 10
        if getattr(self, "_bm25_statutes", None) is not None:
            try:
                _stat_scores = self._bm25_statutes.get_scores(_bm25_tokenized_query)
                _stat_top_local = np.argsort(_stat_scores)[::-1][:_STAT_BM25_TOP_N]
                _stat_bm25_injected = 0
                for _local_idx in _stat_top_local:
                    _score = float(_stat_scores[_local_idx])
                    if _score <= 0.0:
                        continue   # no keyword overlap — skip
                    _global_idx = self._bm25_stat_idx_map[_local_idx]
                    if not (0 <= _global_idx < len(self.chunks)):
                        continue
                    _c = self.chunks[_global_idx].copy()
                    _cid = _c.get("chunk_id")
                    if _cid and _cid not in seen_chunk_ids:
                        _c["_stat_bm25_inject"] = True
                        _c["_stat_bm25_score"] = _score
                        candidate_pool.append(_c)
                        seen_chunk_ids.add(_cid)
                        _stat_bm25_injected += 1
                        if trace is not None:
                            try:
                                trace.record_injected(_c, "statute_bm25", score=_score)
                            except Exception:
                                pass
                if _stat_bm25_injected:
                    logger.info(
                        f"Statute BM25 inject: +{_stat_bm25_injected} statute chunks "
                        f"(top score={float(_stat_scores[_stat_top_local[0]]):.3f})"
                    )
            except Exception as _se:
                logger.warning(f"Statute BM25 injection failed (non-fatal): {_se}")

        # ── 2d3. Notification-isolated BM25 injection (unconditional) ─────────
        # Rate notifications use vocabulary (HSN codes, schedule entry numbers,
        # "per cent" rate figures) that is under-represented in the full-corpus
        # BM25 relative to the 1760-chunk circular corpus.  A notification-only
        # BM25 index ensures the most rate-relevant notification chunk always
        # reaches the CrossEncoder for rate and exemption queries.
        _NOTIF_BM25_TOP_N = 8
        if getattr(self, "_bm25_notifications", None) is not None:
            try:
                _notif_scores = self._bm25_notifications.get_scores(_bm25_tokenized_query)
                _notif_top_local = np.argsort(_notif_scores)[::-1][:_NOTIF_BM25_TOP_N]
                _notif_bm25_injected = 0
                for _local_idx in _notif_top_local:
                    _score = float(_notif_scores[_local_idx])
                    if _score <= 0.0:
                        continue
                    _global_idx = self._bm25_notif_idx_map[_local_idx]
                    if not (0 <= _global_idx < len(self.chunks)):
                        continue
                    _c = self.chunks[_global_idx].copy()
                    _cid = _c.get("chunk_id")
                    if _cid and _cid not in seen_chunk_ids:
                        _c["_notif_bm25_inject"] = True
                        _c["_notif_bm25_score"] = _score
                        candidate_pool.append(_c)
                        seen_chunk_ids.add(_cid)
                        _notif_bm25_injected += 1
                        if trace is not None:
                            try:
                                trace.record_injected(_c, "notification_bm25", score=_score)
                            except Exception:
                                pass
                if _notif_bm25_injected:
                    logger.info(
                        f"Notification BM25 inject: +{_notif_bm25_injected} notification chunks "
                        f"(top score={float(_notif_scores[_notif_top_local[0]]):.3f})"
                    )
            except Exception as _ne:
                logger.warning(f"Notification BM25 injection failed (non-fatal): {_ne}")

        # ── 2e. Circular FAISS injection — semantic search within circular sub-corpus ──
        # BM25 (step 2d) finds circulars by keyword overlap; FAISS finds them by
        # embedding similarity.  Together they cover both exact-term and paraphrase
        # queries.  Only injects circulars that meet a minimum cosine similarity
        # threshold so the CrossEncoder pool stays clean — no noise injection.
        _CIRC_FAISS_TOP_N = 12
        _CIRC_FAISS_MIN_SIM = 0.25   # cosine similarity floor — below this is noise
        if getattr(self, "_faiss_circulars", None) is not None and query_vec is not None:
            try:
                _q_circ = np.array([query_vec]).astype("float32")
                _circ_D, _circ_I = self._faiss_circulars.search(_q_circ, _CIRC_FAISS_TOP_N)
                _circ_faiss_injected = 0
                for _sim, _local_idx in zip(_circ_D[0], _circ_I[0]):
                    if _local_idx < 0 or float(_sim) < _CIRC_FAISS_MIN_SIM:
                        continue
                    _global_idx = self._bm25_circ_idx_map[_local_idx]
                    if not (0 <= _global_idx < len(self.chunks)):
                        continue
                    _c = self.chunks[_global_idx].copy()
                    _cid = _c.get("chunk_id")
                    if _cid and _cid not in seen_chunk_ids:
                        _c["_circ_faiss_inject"] = True
                        _c["_circ_faiss_score"] = round(float(_sim), 4)
                        candidate_pool.append(_c)
                        seen_chunk_ids.add(_cid)
                        _circ_faiss_injected += 1
                        # ── TRACE ────────────────────────────────────────────
                        if trace is not None:
                            try:
                                trace.record_injected(_c, "circular_faiss", score=float(_sim))
                            except Exception:
                                pass
                if _circ_faiss_injected:
                    logger.info(
                        f"Circular FAISS inject: +{_circ_faiss_injected} semantic "
                        f"circular chunks | top_sim={float(_circ_D[0][0]):.4f}"
                    )
            except Exception as _cfe:
                logger.warning(f"Circular FAISS injection failed (non-fatal): {_cfe}")

        # ── Step 2f: Statute-targeted FAISS injection ─────────────────────────
        # The main FAISS search can miss key statutory provisions when the query
        # language is closer to circular/notification language than Act language.
        # Example: "cross charge between distinct persons" → main FAISS retrieves
        # circular-style chunks; Section 25(4)/(5) CGST Act (formal statute prose)
        # ranks lower semantically despite being the governing provision.
        # Isolated statute FAISS ensures Acts/Rules always compete in the pool.
        _STAT_FAISS_TOP_N = 15
        _STAT_FAISS_MIN_SIM = 0.20
        _stat_faiss_injected = 0
        if getattr(self, "_faiss_statutes", None) is not None and query_vec is not None:
            try:
                _q_stat = np.array([query_vec]).astype("float32")
                _stat_D, _stat_I = self._faiss_statutes.search(_q_stat, _STAT_FAISS_TOP_N)
                for _sim, _local_idx in zip(_stat_D[0], _stat_I[0]):
                    if _local_idx < 0 or float(_sim) < _STAT_FAISS_MIN_SIM:
                        continue
                    _global_idx = self._statute_idx_map[_local_idx]
                    _c = self.chunks[_global_idx].copy()
                    _cid = _c.get("chunk_id")
                    if _cid and _cid not in seen_chunk_ids:
                        _c["_stat_faiss_inject"] = True
                        _c["_stat_faiss_score"] = round(float(_sim), 4)
                        candidate_pool.append(_c)
                        seen_chunk_ids.add(_cid)
                        _stat_faiss_injected += 1
                if _stat_faiss_injected:
                    logger.info(
                        f"Statute FAISS inject: +{_stat_faiss_injected} statute chunks "
                        f"| top_sim={float(_stat_D[0][0]):.4f}"
                    )
            except Exception as _sfe:
                logger.warning(f"Statute FAISS injection failed (non-fatal): {_sfe}")

        # ── Step 2g: Notification-targeted FAISS injection ────────────────────
        # Rate notifications use HS code / rate-schedule language that clusters
        # away from main FAISS results for advisory queries.  Top notification
        # chunks are injected so the CrossEncoder can confirm/reject relevance
        # rather than never seeing them.
        _NOTIF_FAISS_TOP_N = 8
        _NOTIF_FAISS_MIN_SIM = 0.22
        _notif_faiss_injected = 0
        if getattr(self, "_faiss_notifications", None) is not None and query_vec is not None:
            try:
                _q_notif = np.array([query_vec]).astype("float32")
                _notif_D, _notif_I = self._faiss_notifications.search(_q_notif, _NOTIF_FAISS_TOP_N)
                for _sim, _local_idx in zip(_notif_D[0], _notif_I[0]):
                    if _local_idx < 0 or float(_sim) < _NOTIF_FAISS_MIN_SIM:
                        continue
                    _global_idx = self._notif_idx_map[_local_idx]
                    _c = self.chunks[_global_idx].copy()
                    _cid = _c.get("chunk_id")
                    if _cid and _cid not in seen_chunk_ids:
                        _c["_notif_faiss_inject"] = True
                        _c["_notif_faiss_score"] = round(float(_sim), 4)
                        candidate_pool.append(_c)
                        seen_chunk_ids.add(_cid)
                        _notif_faiss_injected += 1
                if _notif_faiss_injected:
                    logger.info(
                        f"Notification FAISS inject: +{_notif_faiss_injected} notification chunks "
                        f"| top_sim={float(_notif_D[0][0]):.4f}"
                    )
            except Exception as _nfe:
                logger.warning(f"Notification FAISS injection failed (non-fatal): {_nfe}")

        # Merge layers: Pinned > Statute-First > Graph > Semantic pool (including any fills).
        # Fills now compete on merit via FlashRank+LegalReranker instead of being force-promoted.
        combined_results = _pinned + statute_results[:40] + graph_results[:20]
        existing_ids = {r.get("chunk_id") for r in combined_results}
        for r in candidate_pool:
            if r.get("chunk_id") not in existing_ids:
                combined_results.append(r)
                existing_ids.add(r.get("chunk_id"))

        # --- P2.2: Exclude generated_reports from retrieval corpus ---
        # These 206 LETA-generated Advisory PDFs create a feedback loop: the model can
        # retrieve its own prior outputs as if they were authoritative legal sources.
        # Authoritative corpus must not contain generated material.
        # Evidence: regression run 2026-08-11 confirmed these contaminate final context.
        combined_results = [
            r for r in combined_results
            if not (r.get("rel_path") or r.get("metadata", {}).get("rel_path", ""))
               .lower().replace("\\", "/").startswith("generated_reports")
        ]

        # Cap total candidates for reranker (FlashRank OOM above ~300)
        RERANK_MAX = 80
        reranker_input = combined_results[:RERANK_MAX]

        t_retrieval_end = time.monotonic()
        # Log retrieval timing so ai_logger shows real retrieval_ms (not always 0).
        update_ai_log(retrieval_time_ms=round((t_retrieval_end - t_start) * 1000, 2))
        t_rerank_start = time.monotonic()

        # --- Semantic Reranking (FlashRank) ---
        # skip_rerank=True bypasses the cross-encoder to stay within API Gateway's 29s timeout
        reranked_results = reranker_input
        if reranker_input and not skip_rerank:
            reranked_results = self._cascade_rerank(query, reranker_input, taxonomy=_taxonomy)
            if reranked_results:
                logger.info(
                    f"Cascade rerank: {len(reranker_input)} → {len(reranked_results)} | "
                    f"top_score={reranked_results[0].get('_rerank_score', 0):.3f}"
                )
        # ── TRACE: CrossEncoder scores ────────────────────────────────────────
        if trace is not None and not skip_rerank:
            try:
                trace.record_crossencoder_scores(reranked_results)
            except Exception:
                pass

        # --- Layer 3: Legal Reranking (Composite Scoring) ---
        # P2.1 EXPERIMENT — LegalReranker disabled (2026-08-11)
        # Evidence from 57-query regression: gold avg rank 7.5 after CrossEncoder → 45.4
        # after LegalReranker.  EXP-001: rank 1 → 49, REF-001: rank 1 → 50.
        # The composite scorer is learning the wrong relevance function: it boosts AAR /
        # ICAI / Q&A chunks that share vocabulary with the query over the actual statutes.
        # Disabled until source-authority weighting is added to the scoring model.
        # To re-enable: uncomment the line below and delete the score-propagation loop.
        #
        # reranked_results = LegalReranker.rerank(query, reranked_results, query_topic=topic, is_draft=is_draft)
        #
        # Propagate CrossEncoder / RRF score as _final_legal_score so all downstream
        # stages (doc-hit boost, MMR, circular floor, circular pool sort) still have
        # meaningful per-chunk scores.
        #
        # P2.2 — Source-type authority weighting (2026-08-11)
        # Problem: vocabulary similarity alone lets company-specific AAR documents
        # (Thyssenkrupp ×390, Hindustan Pencils ×95) dominate over the CGST Act.
        # Fix: apply a static authority multiplier calibrated by source directory.
        #
        # STATIC weights (Phase 1) — query-independent.
        # Next step (Phase 2): route multiplier by query intent (statutory vs. case-specific).
        #   Statutory queries   → statute ×2.0, circular ×1.3, AAR ×0.5
        #   Case-specific queries → AAR ×1.5, statute ×1.0, circular ×1.0
        # These static weights are a conservative first step in that direction.
        _SRC_WEIGHTS = {
            # Primary legislation — always prefer
            "statute":       1.50,
            # Authoritative CBIC interpretations
            "notification":  1.20,
            "circular":      1.10,
            # Case law — relevant but case-specific; not controlling for statutory queries
            "case_law":      0.75,
            # Secondary explanatory material
            "other":         0.80,
        }
        for _ch in reranked_results:
            _base = float(_ch.get("_rerank_score", _ch.get("_debug_score", 0.0)))
            _cat  = _chunk_category(_ch)
            _ch["_source_type"]      = _cat
            _ch["_final_legal_score"] = _base * _SRC_WEIGHTS.get(_cat, 1.0)
        # ── TRACE: LegalReranker scores ───────────────────────────────────────
        if trace is not None:
            try:
                trace.record_legalreranker_scores(reranked_results)
            except Exception:
                pass

        # --- Layer 3b: Document-Level Ranking ---
        # Problem: we may retrieve chunk 7 and chunk 19 from Circular 199 while
        # missing chunk 12 (the actual clarification paragraph).  Document-level
        # ranking fixes this by boosting ALL chunks from a document that appears
        # multiple times — rewarding documents that are clearly highly relevant.
        #
        # Algorithm: count how many chunks from each document reached this pool;
        # give each chunk a bonus proportional to log(n_from_same_doc).
        # Documents appearing 3+ times get a +0.03 per-chunk boost; this causes
        # the re-sort to surface the best chunk from the highest-relevance document
        # rather than mixing low-ranked chunks from many documents.
        import math as _math
        _doc_hits: dict = {}
        for _ch in reranked_results:
            _dr = _ch.get("rel_path") or _ch.get("metadata", {}).get("rel_path", "__?__")
            _doc_hits[_dr] = _doc_hits.get(_dr, 0) + 1
        for _ch in reranked_results:
            _dr = _ch.get("rel_path") or _ch.get("metadata", {}).get("rel_path", "__?__")
            _n  = _doc_hits.get(_dr, 1)
            if _n > 1:
                _ch["_final_legal_score"] = _ch.get("_final_legal_score", 0) + _math.log(_n) * 0.02
                _ch["_doc_hit_count"] = _n
        reranked_results.sort(key=lambda x: x.get("_final_legal_score", 0), reverse=True)

        # --- Layer 4: MMR Deduplication ---
        _pre_mmr = list(reranked_results)   # snapshot before MMR for trace
        reranked_results = _mmr_deduplicate(reranked_results, top_k=top_k)
        # ── TRACE: MMR ────────────────────────────────────────────────────────
        if trace is not None:
            try:
                trace.record_mmr(_pre_mmr, reranked_results)
            except Exception:
                pass

        # --- Layer 5: Post-MMR Circular Floor ---
        # Pre-rank quota fills (Phase 2A) get overridden by CrossEncoder + LegalReranker
        # + MMR — all three can push circular chunks below the top_k cutoff.
        # This layer re-injects the best-scored circular/notification chunks AFTER MMR
        # so the LLM always receives CBIC clarification material to cite.
        # Draft mode is exempt — drafts cite case law more than circulars.
        _MIN_CIRCULARS_IN_OUTPUT = 3
        if not is_draft:
            _circ_in_final = sum(
                1 for c in reranked_results
                if _chunk_category(c) in ("circular", "notification")
            )
            if _circ_in_final < _MIN_CIRCULARS_IN_OUTPUT:
                _existing_ids = {c.get("chunk_id") for c in reranked_results}
                # Prefer circular chunks from the 80-chunk reranker pool
                # (they already have _final_legal_score from LegalReranker Layer 3)
                _circ_pool = [
                    c for c in reranker_input
                    if _chunk_category(c) in ("circular", "notification")
                    and c.get("chunk_id") not in _existing_ids
                ]
                _circ_pool.sort(key=lambda x: x.get("_final_legal_score", 0), reverse=True)

                # Fallback: pull from full BM25 corpus if reranker pool had no circulars
                if not _circ_pool and self.bm25:
                    _tokenized = tokenize_text(_expand_for_bm25(query))
                    _bm25_scores = self.bm25.get_scores(_tokenized)
                    _fallback = [
                        (i, _bm25_scores[i])
                        for i, c in enumerate(self.chunks)
                        if _chunk_category(c) in ("circular", "notification")
                        and _bm25_scores[i] > 0
                        and self.chunks[i].get("chunk_id") not in _existing_ids
                    ]
                    _fallback.sort(key=lambda x: x[1], reverse=True)
                    _circ_pool = [self.chunks[i].copy() for i, _ in _fallback[:6]]

                _needed = _MIN_CIRCULARS_IN_OUTPUT - _circ_in_final
                _circ_floor_injected = 0
                for _c in _circ_pool:
                    if _circ_floor_injected >= _needed:
                        break
                    _score = _c.get("_final_legal_score", 0.0)
                    if _score < 0.10:
                        # Skip: circular scored below relevance threshold.
                        # Injecting it would add noise the LLM correctly ignores —
                        # better to send clean statute context than a wrong circular.
                        logger.info(
                            f"Circular floor SKIP (score {_score:.3f} < 0.10): "
                            f"«{(_c.get('rel_path') or _c.get('source', ''))[-60:]}»"
                        )
                        continue
                    _c["_circ_floor_inject"] = True   # needed by injection-aware top_k cutoff
                    reranked_results.append(_c)
                    _circ_floor_injected += 1
                    logger.info(
                        f"Circular floor inject: «{(_c.get('rel_path') or _c.get('source',''))[-60:]}» "
                        f"score={_score:.3f}"
                    )
                    # ── TRACE ────────────────────────────────────────────────
                    if trace is not None:
                        try:
                            trace.record_injected(_c, "circular_floor", score=_score)
                        except Exception:
                            pass

        # --- Layer 6: Authority Coverage Validation ---
        # Check that every category required by this query type is present in the
        # final output.  If a category is missing (e.g. circular not found after
        # all earlier layers), fire a targeted sub-index search and inject the best
        # semantically-confirmed chunk of that type.
        #
        # This is the "coverage validation" stage from the professional legal research
        # architecture: "Have we retrieved Act? Rules? Circular? Notification?"
        # Unlike Layer 5 (which injects any circular above a score floor), Layer 6
        # checks WHICH categories are structurally missing and fills each one
        # with the most semantically relevant chunk from the dedicated sub-index.
        if not is_draft and query_vec is not None:
            # Use taxonomy-predicted expected categories when available (more precise),
            # fall back to keyword-heuristic _query_expected_coverage otherwise.
            _expected = (
                _taxonomy["expected_cats"]
                if _taxonomy.get("confidence", 0) > 0
                else _query_expected_coverage(query, topic)
            )
            _present  = {_chunk_category(c) for c in reranked_results}
            _missing  = _expected - _present
            if _missing:
                _l6_existing_ids = {c.get("chunk_id") for c in reranked_results}
                # Sub-index registry: category → (faiss_sub_index, idx_map, min_sim)
                _sub_registry = {
                    "statute": (
                        getattr(self, "_faiss_statutes", None),
                        getattr(self, "_statute_idx_map", []),
                        0.18,
                    ),
                    "circular": (
                        getattr(self, "_faiss_circulars", None),
                        getattr(self, "_bm25_circ_idx_map", []),
                        0.20,
                    ),
                    "notification": (
                        getattr(self, "_faiss_notifications", None),
                        getattr(self, "_notif_idx_map", []),
                        0.18,
                    ),
                    "case_law": (
                        getattr(self, "_faiss_case_laws", None),
                        getattr(self, "_case_law_idx_map", []),
                        0.20,
                    ),
                }
                _qv = np.array([query_vec]).astype("float32")
                # How many chunks to inject per missing category.
                # Notifications need up to 3 because top FAISS hits may already be
                # in the MMR results (injected earlier by notation sub-search), so
                # we look deeper to find a genuinely new, correctly-categorised chunk.
                _L6_CAP = {"notification": 3, "circular": 2, "statute": 1, "case_law": 1}
                for _mcat in sorted(_missing):   # deterministic order
                    _sub_idx, _sub_map, _min_sim = _sub_registry.get(_mcat, (None, [], 0.20))
                    if _sub_idx is None or not _sub_map:
                        continue
                    _SRC_W_L6 = {"statute": 1.50, "notification": 1.20,
                                 "circular": 1.10, "case_law": 0.75, "other": 0.80}
                    _l6_added = 0
                    _l6_cap   = _L6_CAP.get(_mcat, 1)
                    try:
                        _cv_D, _cv_I = _sub_idx.search(_qv, 15)   # search wider pool
                        for _sim, _li in zip(_cv_D[0], _cv_I[0]):
                            if _l6_added >= _l6_cap:
                                break
                            if _li < 0 or float(_sim) < _min_sim:
                                continue
                            _gi = _sub_map[_li]
                            _c  = self.chunks[_gi].copy()
                            # Guard: chunk must actually be the expected category.
                            # _sub_map is built at init from _chunk_category; verify
                            # after copy in case metadata was mutated.
                            _actual_cat = _chunk_category(_c)
                            if _actual_cat != _mcat:
                                continue   # skip mis-classified chunks in sub-index
                            _cid = _c.get("chunk_id")
                            if _cid and _cid not in _l6_existing_ids:
                                _c["_coverage_fill"]        = True
                                _c["_coverage_cat"]         = _mcat
                                _c["_coverage_sim"]         = round(float(_sim), 4)
                                # P2.5: anchor score — injected after MMR so Layer 3 already ran;
                                # set _final_legal_score directly so this chunk survives top_k cut.
                                _c["_final_legal_score"] = 0.05 * _SRC_W_L6.get(_mcat, 1.0)
                                reranked_results.append(_c)
                                _l6_existing_ids.add(_cid)
                                _l6_added += 1
                                logger.info(
                                    f"Layer 6 coverage fill: +1 {_mcat} chunk "
                                    f"(sim={float(_sim):.3f}) — "
                                    f"«{_c.get('rel_path','')[-60:]}»"
                                )
                                # ── TRACE ────────────────────────────────────
                                if trace is not None:
                                    try:
                                        trace.record_injected(_c, f"layer6_{_mcat}", score=float(_sim))
                                    except Exception:
                                        pass
                    except Exception as _l6e:
                        logger.warning(f"Layer 6 coverage fill ({_mcat}) failed: {_l6e}")

        # --- Mandatory Authority Engine ---
        # Priority 1+3 from the legal RAG architecture:
        # "Retrieval is verified, not guessed."
        #
        # Unlike Layer 5 (circular floor) and Layer 6 (category coverage), this
        # layer checks for SPECIFIC named authorities — not just "a circular" but
        # "Circular 199", not just "a statute" but "Section 25(4) CGST Act".
        #
        # The answer literally cannot be generated until every mandatory authority
        # is confirmed present or explicitly declared missing.
        _coverage_result = {"coverage_pct": 100, "missing": [], "total_mandatory": 0}
        if not is_draft and _taxonomy.get("confidence", 0) > 0:
            _coverage_result = verify_mandatory_coverage(reranked_results, _taxonomy)
            _missing_mandatory = _coverage_result["missing"]

            if _missing_mandatory:
                logger.warning(
                    f"Mandatory Authority Engine: {_coverage_result['coverage_pct']}% coverage | "
                    f"MISSING: {_missing_mandatory}"
                )
                _mae_existing_ids = {c.get("chunk_id") for c in reranked_results}
                _mae_injected = 0

                # MAE anchor scores — set _final_legal_score directly on late-injected
                # chunks (after CrossEncoder and MMR have already run).
                # Calibrated for ms-marco-MiniLM-L-6-v2 CrossEncoder score range (-5 to +5):
                # • Naturally retrieved, highly relevant: fin ≈ 2.0–5.0
                # • Naturally retrieved, partial match:   fin ≈ 0.3–2.0
                # • Irrelevant / noise:                   fin < 0
                # MAE chunks are mandatory legal authorities — they should appear in the
                # top half of results (visible to LLM) but not override the best naturally
                # retrieved chunks.  Target: fin ≈ 1.2–1.8 → always visible, never #1.
                _MAE_STATUTE_SCORE  = 1.50   # statute (critical legal foundation)
                _MAE_CIRCULAR_SCORE = 1.20   # CBIC circular (authoritative interpretation)
                _MAE_NOTIF_SCORE    = 1.35   # rate / exemption notification

                # Step 1: Direct provision-index lookup for missing sections/rules
                _sec_rule_refs = (
                    _coverage_result["missing_sections"] + _coverage_result["missing_rules"]
                )
                if _sec_rule_refs:
                    _forced = self._direct_ref_lookup(_sec_rule_refs)
                    for _fc in _forced:
                        _fid = _fc.get("chunk_id")
                        if _fid and _fid not in _mae_existing_ids:
                            _fc["_mandatory_inject"]    = True
                            _fc["_mandatory_ref"]       = True
                            _fc["_final_legal_score"]   = _MAE_STATUTE_SCORE
                            reranked_results.append(_fc)
                            _mae_existing_ids.add(_fid)
                            _mae_injected += 1

                # Step 2: Circular-index lookup for missing circulars
                for _mc in _coverage_result["missing_circulars"]:
                    _mc_key = _mc if _mc.startswith("CIRCULAR_") else f"CIRCULAR_{_mc.split('_')[-1]}"
                    for _ci in self._circular_index.get(_mc_key, [])[:3]:
                        _c = self.chunks[_ci].copy()
                        _cid = _c.get("chunk_id")
                        if _cid and _cid not in _mae_existing_ids:
                            _c["_mandatory_inject"]  = True
                            _c["_mandatory_circular"] = _mc_key
                            _c["_final_legal_score"] = _MAE_CIRCULAR_SCORE
                            reranked_results.append(_c)
                            _mae_existing_ids.add(_cid)
                            _mae_injected += 1

                # Step 3: Sub-index semantic search as fallback for any still-missing
                if _mae_injected < len(_missing_mandatory) and query_vec is not None:
                    _still_missing_cats = {
                        "statute"      if any(s.startswith(("CGST_SEC", "IGST_SEC")) for s in _missing_mandatory) else None,
                        "circular"     if _coverage_result["missing_circulars"]   else None,
                        "notification" if any(r.startswith("CGST_RUL") for r in _coverage_result["missing_rules"]) else None,
                    } - {None}
                    _sub_reg = {
                        "statute":      (getattr(self, "_faiss_statutes",     None), getattr(self, "_statute_idx_map",   []), 0.15),
                        "circular":     (getattr(self, "_faiss_circulars",    None), getattr(self, "_bm25_circ_idx_map", []), 0.15),
                        "notification": (getattr(self, "_faiss_notifications", None), getattr(self, "_notif_idx_map",    []), 0.15),
                    }
                    _mae_qv = np.array([query_vec]).astype("float32")
                    for _cat in _still_missing_cats:
                        _sidx, _smap, _smin = _sub_reg.get(_cat, (None, [], 0.15))
                        if _sidx is None or not _smap:
                            continue
                        try:
                            _D, _I = _sidx.search(_mae_qv, 3)
                            for _sim, _li in zip(_D[0], _I[0]):
                                if _li < 0 or float(_sim) < _smin:
                                    continue
                                _c = self.chunks[_smap[_li]].copy()
                                _cid = _c.get("chunk_id")
                                if _cid and _cid not in _mae_existing_ids:
                                    _c["_mandatory_inject"] = True
                                    _c["_mandatory_cat_fill"] = _cat
                                    # Set score so these appear in visible range
                                    # (CrossEncoder already ran — set _final_legal_score directly)
                                    _cat_score = {
                                        "statute":      _MAE_STATUTE_SCORE,
                                        "circular":     _MAE_CIRCULAR_SCORE,
                                        "notification": _MAE_NOTIF_SCORE,
                                    }
                                    _c["_final_legal_score"] = _cat_score.get(_cat, 1.0)
                                    reranked_results.append(_c)
                                    _mae_existing_ids.add(_cid)
                                    _mae_injected += 1
                                    break
                        except Exception:
                            pass

                if _mae_injected:
                    logger.info(f"Mandatory Authority Engine injected {_mae_injected} chunks")

            # Citation Graph Expansion (Priority 2+5) — graph traversal from confirmed authorities.
            # When the engine confirms Circular 199 is present, the graph knows its neighbours:
            # Rule 28, Section 25 — fetch those too so the LLM has the full citation chain.
            if getattr(self, "_citation_graph", None) is not None and _coverage_result.get("found"):
                try:
                    _confirmed_keys = set(_coverage_result["found"])
                    _graph_extras   = self._citation_graph.expand_provision_keys(
                        _confirmed_keys, depth=1, max_additions=8
                    )
                    if _graph_extras:
                        _graph_pinned   = self._direct_ref_lookup(_graph_extras)
                        _graph_existing = {c.get("chunk_id") for c in reranked_results}
                        _graph_added    = 0
                        for _gc in _graph_pinned[:5]:
                            _gid = _gc.get("chunk_id")
                            if _gid and _gid not in _graph_existing:
                                _gc["_citation_graph_expand"] = True
                                reranked_results.append(_gc)
                                _graph_existing.add(_gid)
                                _graph_added += 1
                        if _graph_added:
                            logger.info(
                                f"Citation graph expansion: +{_graph_added} related-provision chunks "
                                f"from {list(_confirmed_keys)[:4]}"
                            )
                except Exception as _cge:
                    logger.debug(f"Citation graph expansion failed (non-fatal): {_cge}")

            # Priority 6: Authority Completeness Score — logged for monitoring
            logger.info(
                f"AUTHORITY COMPLETENESS: {_coverage_result['coverage_pct']}% | "
                f"topic={_taxonomy['topics']} | "
                f"mandatory={_coverage_result['total_mandatory']} | "
                f"found={len(_coverage_result.get('found', []))} | "
                f"missing={_coverage_result['missing']}"
            )
            # ── TRACE: validation coverage ───────────────────────────────────
            if trace is not None:
                try:
                    _present_cats = {_chunk_category(c) for c in reranked_results}
                    _expected_cats = _taxonomy.get("expected_cats", set()) or set()
                    trace.record_validation(
                        expected_cats=_expected_cats,
                        present_cats=_present_cats,
                        missing_cats=_expected_cats - _present_cats,
                        mandatory_coverage_pct=float(_coverage_result.get("coverage_pct", 100)),
                        mandatory_missing=_coverage_result.get("missing", []),
                    )
                except Exception:
                    pass

            # Priority 7: Retrieval Self-Critique (only when coverage < 70% or unknown topic)
            # Asks Haiku: "Have we missed any governing authority?"
            # Conditional — not called on every query to avoid latency on known topics.
            if _coverage_result["coverage_pct"] < 70:
                try:
                    from app.retrieval.query_refiner import retrieval_self_critique
                    _src_paths = list({
                        c.get("rel_path") or c.get("metadata", {}).get("rel_path", "")
                        for c in reranked_results if c.get("rel_path") or c.get("metadata", {}).get("rel_path")
                    })
                    _critique = retrieval_self_critique(query, _src_paths, _taxonomy)
                    if _critique.get("missing"):
                        logger.warning(
                            f"Self-Critique flagged missing: {_critique['missing']} "
                            f"(conf={_critique.get('confidence')})"
                        )
                        # Attempt to retrieve self-critique-identified authorities
                        for _sc_auth in _critique["missing"][:3]:
                            # Try to extract section/rule number and look up
                            _sc_refs = _extract_query_refs(_sc_auth)
                            if _sc_refs:
                                _sc_pinned = self._direct_ref_lookup(_sc_refs)
                                _sc_existing = {c.get("chunk_id") for c in reranked_results}
                                for _scp in _sc_pinned[:2]:
                                    _scid = _scp.get("chunk_id")
                                    if _scid and _scid not in _sc_existing:
                                        _scp["_self_critique_inject"] = True
                                        _scp["_self_critique_authority"] = _sc_auth
                                        reranked_results.append(_scp)
                                        _sc_existing.add(_scid)
                except Exception as _sce:
                    logger.warning(f"Self-critique failed (non-fatal): {_sce}")

        # --- Context Window Expansion ---
        # Enrich each selected chunk with adjacent-page neighbors from the full
        # corpus (self._doc_map covers all chunks, not just the 80-chunk pool).
        reranked_results = _expand_context_window(reranked_results, self._doc_map, self.chunks)

        # Flatten metadata for final output (safe merge avoiding key collisions)
        final_results = []
        for res in reranked_results:
            if "metadata" in res:
                meta = res.pop("metadata")
                for key, val in meta.items():
                    if key not in res:  # don't overwrite existing keys
                        res[key] = val
            final_results.append(res)

        final_results = [r for r in final_results if r.get("rel_path") not in self.inactive_paths]

        logger.debug(
            f"search() complete: query='{query[:60]}' | "
            f"statute={len(statute_results)} graph={len(graph_results)} "
            f"semantic={len(candidate_pool)} final={len(final_results)}"
        )

        # Retrieval Memory logging (Priority 9) — fire-and-forget via background thread
        try:
            _ml = _get_mem_logger()
            if _ml:
                _ml.log(
                    query        = query,
                    topics       = _taxonomy.get("topics", []),
                    retrieved    = [c.get("rel_path", "") for c in final_results[:15]],
                    coverage_pct = _coverage_result.get("coverage_pct", 100),
                    missing      = _coverage_result.get("missing", []),
                )
        except Exception:
            pass   # logging failures must never affect retrieval

        # ── Injection-aware top_k cutoff ──────────────────────────────────────
        # Layer 5/6/7 injections (coverage_fill, mandatory_inject, self_critique)
        # are appended AFTER MMR, so they appear at positions >= top_k in
        # final_results.  A naive [:top_k] slice silently drops them.
        # Fix: keep exactly top_k core (non-injected) chunks PLUS all injected
        # chunks unconditionally so the LLM always receives required authorities.
        _INJECT_FLAGS = ("_coverage_fill", "_mandatory_inject", "_self_critique_inject",
                         "_circ_floor_inject")
        _core     = [c for c in final_results if not any(c.get(f) for f in _INJECT_FLAGS)]
        _injected = [c for c in final_results if any(c.get(f) for f in _INJECT_FLAGS)]

        # ── Source-diversity cap (case-law only) ──────────────────────────────
        # AAR/HC/SC documents can monopolise 4-5 slots via broad CGST section
        # references even when the query is unrelated to that ruling. Cap case-law
        # chunks at 2 per source file. Statutes, circulars and notifications are
        # NOT capped — a long circular may legitimately supply 3+ relevant chunks.
        # Injected chunks bypass this cap entirely.
        _CASELAW_CAP = 2
        _caselaw_counts: dict = {}
        _core_capped = []
        for _sc in _core:
            _sc_cat = _chunk_category(_sc)
            if _sc_cat == "case_law":
                _sc_meta = _sc.get("metadata", {}) or {}
                _sc_rel  = (_sc.get("rel_path") or _sc_meta.get("rel_path", "")).replace("\\", "/").lower()
                if _caselaw_counts.get(_sc_rel, 0) >= _CASELAW_CAP:
                    continue   # drop this AAR/HC chunk — slot reserved for statute/circular
                _caselaw_counts[_sc_rel] = _caselaw_counts.get(_sc_rel, 0) + 1
            _core_capped.append(_sc)
        _core = _core_capped

        final_slice = _core[:top_k] + _injected

        # ── Late notification safety net ───────────────────────────────────────
        # If taxonomy expects "notification" but none appear in final_slice
        # (Layer 6 exhausted its search without finding an unclaimed chunk),
        # do a last-resort injection: take the highest-similarity FAISS hit
        # from _faiss_notifications that (a) passes category guard and (b) has
        # at least partial content, ignoring existing-id dedup.  This prevents
        # single-FAIL cases where one file monopolises the notification sub-index.
        # ── Gate: taxonomy expects notification OR FAISS has a strong hit ──────
        _notif_taxonomy_expects = "notification" in _taxonomy.get("expected_cats", set())
        _notif_absent = not any(_chunk_category(c) == "notification" for c in final_slice)
        # Also fire when a notification IS present but has zero query-word coverage
        # (e.g. a GSTR-return notification retrieved for an RCM query). In that case
        # we inject a second, topic-relevant notification alongside the irrelevant one.
        _notif_q_words = set(
            w for w in query.lower().split()
            if len(w) > 4 and w not in {
                "under", "about", "where", "which", "their",
                "would", "could", "should", "shall", "does",
                "what", "when", "how", "this", "that", "from",
            }
        )
        _notif_best_cov = 0
        for _nc in final_slice:
            if _chunk_category(_nc) == "notification":
                _nt = (_nc.get("content") or _nc.get("text") or "").lower()
                _notif_best_cov = max(_notif_best_cov,
                                      sum(1 for w in _notif_q_words if w in _nt))
        # _notif_irrelevant: taxonomy expects notification but existing one has weak/no overlap
        # threshold <=1 catches wrong notifications that score 1 generic word (e.g. "payable", "goods")
        _notif_irrelevant = _notif_taxonomy_expects and _notif_best_cov <= 1 and not _notif_absent
        if (not is_draft and query_vec is not None
                and (_notif_absent or _notif_irrelevant)
                and getattr(self, "_faiss_notifications", None) is not None):
            try:
                _qv_ln = np.array([query_vec]).astype("float32")
                _ln_D, _ln_I = self._faiss_notifications.search(_qv_ln, 20)
                # Only force-inject if: (a) taxonomy expects notification, OR
                # (b) top notification hit has very high similarity (≥ 0.72) even if
                # the taxonomy didn't predict it.  This handles queries where
                # multi-topic merging dropped "notification" from expected_cats.
                _top_notif_sim = float(_ln_D[0][0]) if len(_ln_D[0]) > 0 and _ln_I[0][0] >= 0 else 0.0
                _should_inject = _notif_taxonomy_expects or _top_notif_sim >= 0.72
                if _should_inject:
                    if _notif_irrelevant:
                        logger.info(
                            f"Notification safety-net: existing notification irrelevant "
                            f"(<=1 query-word hits, cov={_notif_best_cov}), injecting topic-relevant one"
                        )
                    # Score candidates by (a) FAISS sim + (b) query-term coverage.
                    # A chunk that mentions the query's key nouns ranks above a chunk
                    # that is only FAISS-similar but topic-agnostic.
                    _q_words = _notif_q_words
                    _best_score = -1.0
                    _best_chunk = None
                    _best_sim   = 0.0
                    for _lsim, _lli in zip(_ln_D[0], _ln_I[0]):
                        if _lli < 0 or float(_lsim) < 0.15:
                            break
                        _lgi = self._notif_idx_map[_lli]
                        _lc  = self.chunks[_lgi].copy()
                        if _chunk_category(_lc) != "notification":
                            continue
                        _ltext = _lc.get("text", "") or _lc.get("metadata", {}).get("text", "")
                        if len(_ltext) < 30:
                            continue
                        _ltext_l = _ltext.lower()
                        _kw_hits = sum(1 for w in _q_words if w in _ltext_l)
                        # Combined score: query coverage dominates, FAISS sim breaks ties
                        _score = _kw_hits * 10.0 + float(_lsim)
                        if _score > _best_score:
                            _best_score = _score
                            _best_chunk = _lc
                            _best_sim   = float(_lsim)
                    if _best_chunk is not None:
                        _best_chunk["_notif_safety_net"] = True
                        _best_chunk["_coverage_fill"]    = True
                        _best_chunk["_final_legal_score"] = 0.05 * 1.20
                        final_slice.append(_best_chunk)
                        logger.info(
                            f"Notification safety-net inject: sim={_best_sim:.3f} "
                            f"score={_best_score:.1f} tax_exp={_notif_taxonomy_expects} "
                            f"«{_best_chunk.get('metadata',{}).get('rel_path','')[-60:]}»"
                        )
            except Exception as _lne:
                logger.debug(f"Notification safety net failed (non-fatal): {_lne}")

        # ── TRACE: finalize ───────────────────────────────────────────────────
        if trace is not None:
            try:
                trace.finalize(final_slice)
            except Exception:
                pass

        return final_slice

    def supplement_and_rerank(self, base_chunks: list, advanced_queries: dict, query: str, top_k: int, trace=None) -> list:
        """
        Called after fast retrieval (skip_rerank=True) + query expansion finish in parallel.
        Supplements the fast pool with FAISS results from expanded queries, then runs ONE
        FlashRank + LegalReranker + MMR pass on the merged pool capped at 80 chunks.
        This replaces the old pattern of running FlashRank on 200 chunks twice.
        """
        if not advanced_queries:
            return base_chunks[:top_k]

        topic = advanced_queries.get("topic", "General")

        # Authority taxonomy: predicts governing authorities from query intent
        _sr_taxonomy = classify_query_authority(query)
        if _sr_taxonomy["confidence"] > 0:
            logger.info(
                f"S&R taxonomy: topics={_sr_taxonomy['topics']} "
                f"sections={_sr_taxonomy['sections']} circulars={_sr_taxonomy['circulars']}"
            )

        # Direct ref lookup: pin explicit citations + taxonomy-predicted authorities
        _explicit_refs = _extract_query_refs(query)
        _tax_refs = (
            _sr_taxonomy["sections"] + _sr_taxonomy["rules"] +
            [f"CIRCULAR_{c.split('_')[-1]}" if c.startswith("CIRCULAR_") else c
             for c in _sr_taxonomy["circulars"]]
        )
        _query_refs = list(dict.fromkeys(_explicit_refs + _tax_refs))
        _pinned = self._direct_ref_lookup(_query_refs) if _query_refs else []

        existing_ids = {c.get("chunk_id") for c in base_chunks}
        for c in _pinned:
            existing_ids.add(c.get("chunk_id"))

        extra_queries = list(advanced_queries.get("queries", [])[1:])
        hyde = advanced_queries.get("hyde_document", "")
        if hyde:
            extra_queries.append(hyde)

        combined = _pinned + list(base_chunks)
        if self.index:
            for eq in extra_queries:
                if not eq or not isinstance(eq, str) or not eq.strip():
                    continue
                vec = embed_query(eq)
                if vec is not None:
                    D, I = self.index.search(np.array([vec]).astype('float32'), VECTOR_EXPANDED_TOP_K)
                    for idx in I[0]:
                        if 0 <= idx < len(self.chunks):
                            chunk = self.chunks[idx].copy()
                            cid = chunk.get("chunk_id")
                            if cid and cid not in existing_ids:
                                existing_ids.add(cid)
                                combined.append(chunk)

        # Enforce category quotas — circulars/notifications only fill in when BM25
        # confirms topical relevance; statutes always get their floor.
        _sr_quotas = {"statute": 6, "case_law": 4, "circular": 4, "notification": 3}
        combined = self._enforce_pool_quotas(combined, query, _sr_quotas)
        # No priority-front promotion — fills compete on merit via FlashRank + LegalReranker.

        RERANK_CAP = 80
        rerank_input = combined[:RERANK_CAP]
        reranked = rerank_input

        if rerank_input:
            reranked = self._cascade_rerank(query, rerank_input, taxonomy=_sr_taxonomy)
        # ── TRACE: CrossEncoder (supplement_and_rerank path) ──────────────────
        if trace is not None:
            try:
                trace.record_crossencoder_scores(reranked)
            except Exception:
                pass

        # P2.1 EXPERIMENT: LegalReranker disabled — same reason as search() above.
        # reranked = LegalReranker.rerank(query, reranked, query_topic=topic, is_draft=False)
        # P2.2 source-type weighting (mirrors search() block — same multipliers).
        _SRC_WEIGHTS_SR = {
            "statute": 1.50, "notification": 1.20, "circular": 1.10,
            "case_law": 0.75, "other": 0.80,
        }
        for _ch in reranked:
            _base = float(_ch.get("_rerank_score", _ch.get("_debug_score", 0.0)))
            _cat  = _chunk_category(_ch)
            _ch["_source_type"]       = _cat
            _ch["_final_legal_score"] = _base * _SRC_WEIGHTS_SR.get(_cat, 1.0)
        # ── TRACE: LegalReranker (supplement_and_rerank path) ─────────────────
        if trace is not None:
            try:
                trace.record_legalreranker_scores(reranked)
            except Exception:
                pass

        # Document-level ranking boost (mirrors search() Layer 3b)
        import math as _math_sr
        _sr_doc_hits: dict = {}
        for _ch in reranked:
            _dr = _ch.get("rel_path") or _ch.get("metadata", {}).get("rel_path", "__?__")
            _sr_doc_hits[_dr] = _sr_doc_hits.get(_dr, 0) + 1
        for _ch in reranked:
            _dr = _ch.get("rel_path") or _ch.get("metadata", {}).get("rel_path", "__?__")
            _n  = _sr_doc_hits.get(_dr, 1)
            if _n > 1:
                _ch["_final_legal_score"] = _ch.get("_final_legal_score", 0) + _math_sr.log(_n) * 0.02
        reranked.sort(key=lambda x: x.get("_final_legal_score", 0), reverse=True)

        _pre_mmr_sr = list(reranked)   # snapshot for trace
        mmr_results = _mmr_deduplicate(reranked, top_k=top_k)
        # ── TRACE: MMR (supplement_and_rerank path) ───────────────────────────
        if trace is not None:
            try:
                trace.record_mmr(_pre_mmr_sr, mmr_results)
            except Exception:
                pass

        # Coverage validation — same as Layer 6 in search()
        # Ensures the fast-path also fills missing authority categories.
        _sr_query_vec = embed_query(query)
        if _sr_query_vec is not None:
            _sr_expected = (
                _sr_taxonomy["expected_cats"]
                if _sr_taxonomy.get("confidence", 0) > 0
                else _query_expected_coverage(query, topic)
            )
            _sr_present  = {_chunk_category(c) for c in mmr_results}
            _sr_missing  = _sr_expected - _sr_present
            if _sr_missing:
                _sr_existing = {c.get("chunk_id") for c in mmr_results}
                _sr_sub = {
                    "statute":      (getattr(self, "_faiss_statutes",     None), getattr(self, "_statute_idx_map",    []), 0.18),
                    "circular":     (getattr(self, "_faiss_circulars",    None), getattr(self, "_bm25_circ_idx_map",  []), 0.20),
                    "notification": (getattr(self, "_faiss_notifications", None), getattr(self, "_notif_idx_map",     []), 0.18),
                    "case_law":     (getattr(self, "_faiss_case_laws",    None), getattr(self, "_case_law_idx_map",   []), 0.20),
                }
                _sr_qv = np.array([_sr_query_vec]).astype("float32")
                for _mcat in sorted(_sr_missing):
                    _idx, _map, _msim = _sr_sub.get(_mcat, (None, [], 0.20))
                    if _idx is None or not _map:
                        continue
                    try:
                        _D, _I = _idx.search(_sr_qv, 5)
                        for _sim, _li in zip(_D[0], _I[0]):
                            if _li < 0 or float(_sim) < _msim:
                                continue
                            _c = self.chunks[_map[_li]].copy()
                            _cid = _c.get("chunk_id")
                            if _cid and _cid not in _sr_existing:
                                _c["_coverage_fill"] = True
                                _c["_coverage_cat"]  = _mcat
                                mmr_results.append(_c)
                                _sr_existing.add(_cid)
                                logger.info(f"S&R coverage fill: +1 {_mcat} (sim={float(_sim):.3f})")
                                break
                    except Exception:
                        pass

        # Context window expansion using the full-corpus doc map
        mmr_results = _expand_context_window(mmr_results, self._doc_map, self.chunks)

        final = []
        for res in mmr_results:
            if "metadata" in res:
                meta = res.pop("metadata")
                for key, val in meta.items():
                    if key not in res:
                        res[key] = val
            final.append(res)

        # Mandatory coverage verification for supplement_and_rerank path
        _sr_coverage = {"coverage_pct": 100, "missing": [], "total_mandatory": 0}
        if _sr_taxonomy.get("confidence", 0) > 0:
            _sr_coverage = verify_mandatory_coverage(final, _sr_taxonomy)
            if _sr_coverage["missing"]:
                logger.warning(
                    f"S&R mandatory coverage: {_sr_coverage['coverage_pct']}% | "
                    f"MISSING: {_sr_coverage['missing']}"
                )
                # Force-inject missing mandatory authorities via direct ref lookup
                _sr_mae_refs = _sr_coverage["missing_sections"] + _sr_coverage["missing_rules"]
                _sr_cir_refs = [
                    f"CIRCULAR_{c.split('_')[-1]}" for c in _sr_coverage["missing_circulars"]
                ]
                _sr_all_refs = _sr_mae_refs + _sr_cir_refs
                if _sr_all_refs:
                    _sr_forced = self._direct_ref_lookup(_sr_all_refs)
                    _sr_existing = {c.get("chunk_id") for c in final}
                    for _fc in _sr_forced:
                        _fid = _fc.get("chunk_id")
                        if _fid and _fid not in _sr_existing:
                            _fc["_mandatory_inject"] = True
                            final.append(_fc)
                            _sr_existing.add(_fid)

            logger.info(
                f"S&R AUTHORITY COMPLETENESS: {_sr_coverage['coverage_pct']}% | "
                f"mandatory={_sr_coverage['total_mandatory']} | missing={_sr_coverage['missing']}"
            )

        # Store taxonomy + coverage for answer verification (Priority 10)
        # stream_and_save reads these via get_retriever()._last_taxonomy
        self._last_taxonomy = _sr_taxonomy
        self._last_coverage  = _sr_coverage

        logger.info(
            f"supplement_and_rerank: pinned={len(_pinned)} base={len(base_chunks)} "
            f"expanded={len(combined)-len(base_chunks)-len(_pinned)} "
            f"reranked={len(reranked)} final={len(final)}"
        )

        # Retrieval Memory logging (Priority 9)
        try:
            _ml = _get_mem_logger()
            if _ml:
                _ml.log(
                    query        = query,
                    topics       = _sr_taxonomy.get("topics", []),
                    retrieved    = [c.get("rel_path", "") for c in final[:15]],
                    coverage_pct = _sr_coverage.get("coverage_pct", 100),
                    missing      = _sr_coverage.get("missing", []),
                )
        except Exception:
            pass

        # ── TRACE: finalize (supplement_and_rerank path) ──────────────────────
        if trace is not None:
            try:
                trace.finalize(final)
            except Exception:
                pass

        return final
