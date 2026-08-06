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

logger = logging.getLogger(__name__)

# ─── Pool classification — folder patterns per document category ───────────
_CASE_LAW_FOLDERS     = {"high court case laws", "supreme court case laws", "aar", "other app result"}
_STATUTE_FOLDERS      = {"act", "rules", "cgst", "igst", "utgst", "export"}
_NOTIFICATION_FOLDERS = {"notification", "notifications"}
_CIRCULAR_FOLDERS     = {"circulars", "circular", "icai", "brochures", "faqs"}


def _chunk_category(chunk: dict) -> str:
    path = (chunk.get("rel_path") or chunk.get("source") or
            chunk.get("metadata", {}).get("rel_path", "")).lower().replace("\\", "/")
    for folder in _CASE_LAW_FOLDERS:
        if f"/{folder}/" in path or path.startswith(folder + "/"):
            return "case_law"
    for folder in _CIRCULAR_FOLDERS:
        if f"/{folder}/" in path or path.startswith(folder + "/"):
            return "circular"
    for folder in _NOTIFICATION_FOLDERS:
        if f"/{folder}/" in path or path.startswith(folder + "/"):
            return "notification"
    for folder in _STATUTE_FOLDERS:
        if f"/{folder}/" in path or path.startswith(folder + "/"):
            return "statute"
    return "other"

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

# Abbreviation → full-form expansion for BM25 query preprocessing
_GST_ABBREV = [
    (re.compile(r'\bitc\b', re.IGNORECASE), 'input tax credit ITC'),
    (re.compile(r'\brcm\b', re.IGNORECASE), 'reverse charge mechanism RCM'),
    (re.compile(r'\bscn\b', re.IGNORECASE), 'show cause notice SCN'),
    (re.compile(r'\bisd\b', re.IGNORECASE), 'input service distributor ISD'),
    (re.compile(r'\blut\b', re.IGNORECASE), 'letter of undertaking LUT'),
    (re.compile(r'\bsez\b', re.IGNORECASE), 'special economic zone SEZ'),
    (re.compile(r'\bcgst\b', re.IGNORECASE), 'central goods services tax CGST'),
    (re.compile(r'\bigst\b', re.IGNORECASE), 'integrated goods services tax IGST'),
    (re.compile(r'\bsgst\b', re.IGNORECASE), 'state goods services tax SGST'),
    (re.compile(r'\bgstr\b', re.IGNORECASE), 'return GSTR'),
    (re.compile(r'\bfaq\b', re.IGNORECASE), 'frequently asked questions FAQ'),
    (re.compile(r'\baar\b', re.IGNORECASE), 'advance ruling AAR'),
    (re.compile(r'\bpoc\b', re.IGNORECASE), 'place of supply POS'),
    # CBIC expands to full form — circulars/instructions are issued by CBIC
    (re.compile(r'\bcbic\b', re.IGNORECASE), 'CBIC central board indirect taxes customs circular instruction'),
    # Normalize section shorthand: "sec 16", "s.16", "s16" → "section 16"
    (re.compile(r'\bsec\.?\s*(\d)', re.IGNORECASE), r'section \1'),
    (re.compile(r'\bs\.\s*(\d)', re.IGNORECASE), r'section \1'),
]


def _expand_for_bm25(query: str) -> str:
    """Expand GST abbreviations in a query string for better BM25 keyword coverage."""
    result = query
    for pattern, replacement in _GST_ABBREV:
        result = pattern.sub(replacement, result)
    return result


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
            for _ref in set(_meta.get("provisions", []) + _meta.get("citations", [])):
                # Skip generic "ACT" citation — matches everything, not useful
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

        # ── TF-IDF matrix (3rd RRF signal) ────────────────────────────────────
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
        logger.info("Building TF-IDF matrix for 3rd RRF signal...")
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            _corpus_texts = [c.get("text", "") for c in self.chunks]
            self._tfidf = TfidfVectorizer(
                max_features=60000,
                ngram_range=(1, 2),
                min_df=1,
                sublinear_tf=True,
                dtype=np.float32,   # halves memory vs float64
            )
            self._tfidf_matrix = self._tfidf.fit_transform(_corpus_texts)
            logger.info(
                f"TF-IDF matrix built: {self._tfidf_matrix.shape[0]} docs × "
                f"{self._tfidf_matrix.shape[1]} features | "
                f"nnz={self._tfidf_matrix.nnz:,}"
            )
        except Exception as _e:
            logger.warning(f"TF-IDF build failed (non-fatal, will skip): {_e}")
            self._tfidf = None
            self._tfidf_matrix = None

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

        logger.info("Loading CrossEncoder reranker (BAAI/bge-reranker-v2-m3)...")
        try:
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder(
                "BAAI/bge-reranker-v2-m3",
                max_length=512,
                device="cpu",
            )
            logger.info("  CrossEncoder loaded: BAAI/bge-reranker-v2-m3")
        except Exception as e:
            logger.error(f"Failed to load CrossEncoder: {e}", exc_info=True)
            self.cross_encoder = None

        # Initialize Layer 1 (Statute-First)
        self.statute_retriever = StatuteRetriever()

        # Initialize Provision Graph
        graph_path = Path(chunks_path).parent.parent / "graph" / "edges.jsonl"
        self.graph_retriever = ProvisionGraphRetriever(graph_path)

        logger.info("Retriever initialized: 3-Layer Architecture + Provision Graph + MMR")

    def _cascade_rerank(self, query: str, candidates: list,
                        stage1_keep: int = 30) -> list:
        """
        Reranks candidates with BAAI/bge-reranker-v2-m3 CrossEncoder.
        Falls back to RRF score order if CrossEncoder is unavailable.
        Uses _rrf_score as a tiebreaker when cross-encoder scores are equal.
        """
        pool = list(candidates)
        if self.cross_encoder and pool:
            try:
                pairs = [
                    (query, (c.get("context_text") or c.get("text", ""))[:512])
                    for c in pool
                ]
                scores = self.cross_encoder.predict(pairs, show_progress_bar=False)
                for chunk, score in zip(pool, scores):
                    # Add RRF score as a small tiebreaker (1% weight) so that
                    # chunks well-ranked by both FAISS and BM25 win ties.
                    rrf_boost = chunk.get("_rrf_score", 0.0) * 0.01
                    chunk["_rerank_score"] = float(score) + rrf_boost
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

    def _direct_ref_lookup(self, refs: list) -> list:
        """
        Returns chunks that explicitly cite any of the given provision keys,
        using the pre-built provision index for O(1) lookup per key.
        CIRCULAR_N keys are resolved via _circular_index (filename-based).
        These chunks are pinned at the top of combined_results with
        _statute_priority=1.0 so they survive FlashRank and LegalReranker.
        Capped at 20 to avoid flooding the reranker with pinned chunks.
        """
        if not refs or not hasattr(self, "_provision_index"):
            return []
        seen_ids: set = set()
        pinned = []

        def _pin(idx: int) -> bool:
            if idx >= len(self.chunks):
                return False
            chunk = self.chunks[idx]
            cid = chunk.get("chunk_id")
            if cid and cid not in seen_ids:
                c = chunk.copy()
                c["_pinned_by_ref"] = True
                c["_statute_priority"] = 1.0
                pinned.append(c)
                seen_ids.add(cid)
                return True
            return False

        for ref in refs:
            # Statutory provisions (CGST_SEC_16, CGST_RUL_89, etc.)
            for idx in self._provision_index.get(ref, []):
                _pin(idx)
                if len(pinned) >= 20:
                    return pinned
            # Circular number keys (CIRCULAR_183) — resolved from filename-based index
            if ref.startswith("CIRCULAR_") and hasattr(self, "_circular_index"):
                for idx in self._circular_index.get(ref, []):
                    _pin(idx)
                    if len(pinned) >= 20:
                        return pinned
        return pinned

    def search(self, query: str, top_k: int = 50, allowed_sources=None, advanced_queries=None, domain_paths=None, is_draft: bool = False, skip_rerank: bool = False):
        if not query or not query.strip():
            logger.warning("search() called with empty query")
            return []

        if not self.index or not self.bm25:
            logger.warning("search() called but retriever is not initialized (missing index/bm25)")
            return []

        # --- 1. Query Topic & Subtopic (from pre-computed advanced_queries, no extra LLM call) ---
        topic = "General"
        subtopic = None
        if advanced_queries:
            topic = advanced_queries.get("topic", "General")
            subtopic = advanced_queries.get("subtopic")

        # --- Direct section/rule reference lookup (pinned, bypasses FAISS ranking) ---
        # Extracts explicit citations from query (e.g. "Section 16 CGST") and pins
        # matching chunks at priority 1.0 so they always reach the top of the pool.
        _query_refs = _extract_query_refs(query)
        _pinned = self._direct_ref_lookup(_query_refs) if _query_refs else []
        if _pinned:
            logger.info(f"Direct ref lookup: {_query_refs} → {len(_pinned)} pinned chunks")

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
                cid = self.chunks[idx].get("chunk_id")
                if cid and cid not in seen_chunk_ids:
                    seen_chunk_ids.add(cid)
                    candidate_pool.append(self.chunks[idx].copy())

        # 1. Vector Search — primary query
        faiss_chunks: list = []
        query_vec = embed_query(query)
        if self.index and query_vec is not None:
            D, I = self.index.search(np.array([query_vec]).astype('float32'), VECTOR_SEARCH_TOP_K)
            for idx in I[0]:
                if 0 <= idx < len(self.chunks):
                    faiss_chunks.append(self.chunks[idx])

        # 1b. Vector Search — expanded queries + HyDE document (added directly to pool,
        #     not merged via RRF because they have no BM25 counterpart ranking)
        if advanced_queries and self.index:
            extra_queries = advanced_queries.get("queries", [])[1:]
            hyde_doc = advanced_queries.get("hyde_document", "")
            if hyde_doc:
                extra_queries.append(hyde_doc)

            for eq in extra_queries:
                if not eq or not eq.strip():
                    continue
                eq_vec = embed_query(eq)
                if eq_vec is not None:
                    D2, I2 = self.index.search(np.array([eq_vec]).astype('float32'), VECTOR_EXPANDED_TOP_K)
                    for idx in I2[0]:
                        _add_to_pool(idx)

        # 2. BM25 Search — expand abbreviations before tokenizing
        bm25_chunks: list = []
        _bm25_tokenized_query = tokenize_text(_expand_for_bm25(query))  # reused below
        if self.bm25:
            bm25_scores = self.bm25.get_scores(_bm25_tokenized_query)
            top_bm25_idxs = np.argsort(bm25_scores)[::-1][:BM25_TOP_K]
            for idx in top_bm25_idxs:
                if 0 <= idx < len(self.chunks):
                    bm25_chunks.append(self.chunks[idx])

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
                if _circ_injected:
                    logger.info(
                        f"Circular BM25 inject: +{_circ_injected} circular/notification "
                        f"chunks (top score={float(_circ_scores[_circ_top_local[0]]):.3f})"
                    )
            except Exception as _ce:
                logger.warning(f"Circular BM25 injection failed (non-fatal): {_ce}")

        # Merge layers: Pinned > Statute-First > Graph > Semantic pool (including any fills).
        # Fills now compete on merit via FlashRank+LegalReranker instead of being force-promoted.
        combined_results = _pinned + statute_results[:40] + graph_results[:20]
        existing_ids = {r.get("chunk_id") for r in combined_results}
        for r in candidate_pool:
            if r.get("chunk_id") not in existing_ids:
                combined_results.append(r)
                existing_ids.add(r.get("chunk_id"))

        # Cap total candidates for reranker (FlashRank OOM above ~300)
        RERANK_MAX = 80
        reranker_input = combined_results[:RERANK_MAX]

        # --- Semantic Reranking (FlashRank) ---
        # skip_rerank=True bypasses the cross-encoder to stay within API Gateway's 29s timeout
        reranked_results = reranker_input
        if reranker_input and not skip_rerank:
            reranked_results = self._cascade_rerank(query, reranker_input)
            if reranked_results:
                logger.info(
                    f"Cascade rerank: {len(reranker_input)} → {len(reranked_results)} | "
                    f"top_score={reranked_results[0].get('_rerank_score', 0):.3f}"
                )

        # --- Layer 3: Legal Reranking (Composite Scoring) ---
        reranked_results = LegalReranker.rerank(query, reranked_results, query_topic=topic, is_draft=is_draft)

        # --- Layer 4: MMR Deduplication ---
        reranked_results = _mmr_deduplicate(reranked_results, top_k=top_k)

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
                for _c in _circ_pool[:_needed]:
                    reranked_results.append(_c)
                    logger.info(
                        f"Circular floor inject: «{(_c.get('rel_path') or _c.get('source',''))[-60:]}» "
                        f"score={_c.get('_final_legal_score', 0.0):.3f}"
                    )

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

        logger.debug(
            f"search() complete: query='{query[:60]}' | "
            f"statute={len(statute_results)} graph={len(graph_results)} "
            f"semantic={len(candidate_pool)} final={len(final_results)}"
        )
        return final_results[:top_k]

    def supplement_and_rerank(self, base_chunks: list, advanced_queries: dict, query: str, top_k: int) -> list:
        """
        Called after fast retrieval (skip_rerank=True) + query expansion finish in parallel.
        Supplements the fast pool with FAISS results from expanded queries, then runs ONE
        FlashRank + LegalReranker + MMR pass on the merged pool capped at 80 chunks.
        This replaces the old pattern of running FlashRank on 200 chunks twice.
        """
        if not advanced_queries:
            return base_chunks[:top_k]

        topic = advanced_queries.get("topic", "General")

        # Direct ref lookup: pin explicitly-cited sections at top of pool
        _query_refs = _extract_query_refs(query)
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
                if not eq or not eq.strip():
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
            reranked = self._cascade_rerank(query, rerank_input)

        reranked = LegalReranker.rerank(query, reranked, query_topic=topic, is_draft=False)

        mmr_results = _mmr_deduplicate(reranked, top_k=top_k)

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

        logger.info(
            f"supplement_and_rerank: pinned={len(_pinned)} base={len(base_chunks)} "
            f"expanded={len(combined)-len(base_chunks)-len(_pinned)} "
            f"reranked={len(reranked)} final={len(final)}"
        )
        return final
