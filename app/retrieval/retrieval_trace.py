"""
RetrievalTrace — full pipeline provenance for every LETA query.

Design principles:
  - Zero retrieval-behavior change: recording is purely additive / read-only.
  - Non-failing: every recording method is wrapped; trace errors never surface to callers.
  - Thread-safe for reads after the retrieval thread finishes writing.
  - Two output formats:
      to_log_dict()  → compact single JSON line for CloudWatch
      to_debug_dict() → full detail for /debug/trace/{query_id}

Usage (inside retriever.search()):
    if trace:
        trace.record_faiss(chunks_with_scores)
        ...
    After every transformation:
        trace.snapshot_stage("after_crossencoder", chunks)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _doc_id(rel_path: str) -> str:
    """Stable human-readable document ID from rel_path (filename without ext)."""
    if not rel_path:
        return "unknown"
    return Path(rel_path.replace("\\", "/")).stem


def _doc_type(rel_path: str) -> str:
    """Classify document category from path (mirrors _chunk_category in retriever)."""
    p = rel_path.lower().replace("\\", "/")
    if any(f in p for f in ("high court", "supreme court", "aar", "other app")):
        return "case_law"
    if any(f in p for f in ("notification", "notifications")):
        return "notification"
    if any(f in p for f in ("circulars", "circular", "icai", "brochures", "faqs")):
        return "circular"
    if any(f in p for f in ("act", "rules", "cgst", "igst", "utgst", "export")):
        return "statute"
    return "other"


def _safe(fn):
    """Decorator: silently swallow any exception inside trace recording methods."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.debug(f"RetrievalTrace recording error (non-fatal): {e}")
    return wrapper


# ─── Per-chunk provenance record ──────────────────────────────────────────────

@dataclass
class ChunkRecord:
    chunk_id: str
    document_id: str
    document_type: str
    rel_path: str
    text_preview: str          # first 180 chars

    # Where this chunk first entered the candidate pool
    entered_at: str = "unknown"   # faiss | bm25 | tfidf | taxonomy_pin | quota_fill |
                                  # circular_bm25 | circular_faiss | statute_faiss |
                                  # circular_floor | layer6 | mandatory_inject |
                                  # citation_graph | self_critique

    # Which retrieval signals found this chunk
    retrieval_sources: list = field(default_factory=list)

    # Per-source scores / ranks
    faiss_rank:  Optional[int]   = None
    faiss_score: Optional[float] = None
    bm25_rank:   Optional[int]   = None
    bm25_score:  Optional[float] = None
    tfidf_rank:  Optional[int]   = None
    tfidf_score: Optional[float] = None
    rrf_score:   Optional[float] = None

    # Reranking scores
    cross_encoder_score:  Optional[float] = None
    legal_reranker_score: Optional[float] = None
    authority_boost:      Optional[float] = None
    doc_level_boost:      Optional[float] = None

    # Injection metadata (for non-FAISS/BM25 paths)
    injection_reason: Optional[str]  = None   # e.g. "circular_floor", "layer6_statute"
    injection_score:  Optional[float] = None

    # MMR
    mmr_kept: Optional[bool]  = None
    mmr_similarity: Optional[float] = None  # max Jaccard to already-selected chunks

    # Provision keys from metadata (P2.5 — used by gold matcher)
    provisions: list = field(default_factory=list)

    # Provision Anchoring metadata (P2.5)
    anchor_provision: Optional[str] = None    # which taxonomy provision key pinned this

    # Final outcome
    selected: bool = False
    selection_reasons: list = field(default_factory=list)
    elimination_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "chunk_id":            self.chunk_id,
            "document_id":         self.document_id,
            "document_type":       self.document_type,
            "rel_path":            self.rel_path,
            "text_preview":        self.text_preview,
            "entered_at":          self.entered_at,
            "retrieval_sources":   self.retrieval_sources,
            "faiss_rank":          self.faiss_rank,
            "faiss_score":         self.faiss_score,
            "bm25_rank":           self.bm25_rank,
            "bm25_score":          self.bm25_score,
            "tfidf_rank":          self.tfidf_rank,
            "tfidf_score":         self.tfidf_score,
            "rrf_score":           self.rrf_score,
            "cross_encoder_score": self.cross_encoder_score,
            "legal_reranker_score":self.legal_reranker_score,
            "authority_boost":     self.authority_boost,
            "doc_level_boost":     self.doc_level_boost,
            "injection_reason":    self.injection_reason,
            "injection_score":     self.injection_score,
            "mmr_kept":            self.mmr_kept,
            "mmr_similarity":      self.mmr_similarity,
            "provisions":          self.provisions,
            "anchor_provision":    self.anchor_provision,
            "selected":            self.selected,
            "selection_reasons":   self.selection_reasons,
            "elimination_reason":  self.elimination_reason,
        }


# ─── Main trace object ────────────────────────────────────────────────────────

class RetrievalTrace:
    """
    Accumulates full retrieval provenance for one LETA query.
    Created at /ask entry, passed through retriever.search() and supplement_and_rerank(),
    finalized before CloudWatch logging.

    All recording methods are @_safe — no exception can escape into the retrieval path.
    """

    def __init__(self, query_id: str, query: str):
        self.query_id  = query_id
        self.query     = query
        self.created_at = time.time()

        # Preprocessing (populated from app.py before calling retriever)
        self.preprocessing: dict = {}

        # Per-chunk records — the core provenance store
        self._chunks: dict[str, ChunkRecord] = {}

        # Stage snapshots: ordered list of (chunk_id, score) at each point
        # Key = stage name, value = list of {chunk_id, score, rank}
        self._stages: dict[str, list] = {}

        # Document-level aggregation (populated at finalize())
        self.documents: dict = {}

        # Counts at each stage
        self.stage_counts: dict = {}

        # Validation / coverage
        self.validation: dict = {}

        # Final context + answer
        self.final_context: dict = {}
        self.answer: dict = {}

        # Internal: set of seen chunk_ids to avoid double-recording entered_at
        self._entered: set = set()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get_or_create(self, chunk: dict) -> Optional[ChunkRecord]:
        """Return the ChunkRecord for this chunk, creating it if needed."""
        cid = chunk.get("chunk_id")
        if not cid:
            return None
        if cid not in self._chunks:
            rel = (chunk.get("rel_path") or
                   chunk.get("metadata", {}).get("rel_path", "") or
                   chunk.get("source", ""))
            _meta = chunk.get("metadata", {})
            # P2.5: capture provision keys so gold matcher can identify statute chunks
            # even when the text_preview doesn't explicitly say "Section N"
            _provs = list(set(
                _meta.get("provisions", []) + _meta.get("citations", [])
            ))
            self._chunks[cid] = ChunkRecord(
                chunk_id     = cid,
                document_id  = _doc_id(rel),
                document_type= _doc_type(rel),
                rel_path     = rel,
                text_preview = (chunk.get("text") or "")[:180],
                provisions   = _provs,
                anchor_provision = chunk.get("_anchor_provision"),
            )
        else:
            # Update anchor_provision if newly set (e.g. chunk re-encountered as pinned)
            _rec = self._chunks[cid]
            if not _rec.anchor_provision and chunk.get("_anchor_provision"):
                _rec.anchor_provision = chunk["_anchor_provision"]
        return self._chunks[cid]

    # ── Preprocessing ──────────────────────────────────────────────────────────

    @_safe
    def record_preprocessing(self, *,
                              original_query: str,
                              refined_query: str = "",
                              sub_queries: list = None,
                              hyde_doc: str = "",
                              topic: str = "",
                              subtopic: str = "",
                              detected_refs: list = None,
                              taxonomy: dict = None,
                              domain_route: list = None,
                              complexity_score: float = 0.0,
                              response_mode: str = ""):
        self.preprocessing = {
            "original_query":  original_query,
            "refined_query":   refined_query or original_query,
            "sub_queries":     sub_queries or [],
            "hyde_doc":        hyde_doc[:400] if hyde_doc else "",
            "topic":           topic,
            "subtopic":        subtopic,
            "detected_refs":   detected_refs or [],
            "taxonomy": {
                "topics":      (taxonomy or {}).get("topics", []),
                "sections":    (taxonomy or {}).get("sections", []),
                "rules":       (taxonomy or {}).get("rules", []),
                "circulars":   (taxonomy or {}).get("circulars", []),
                "confidence":  (taxonomy or {}).get("confidence", 0),
                "expected_cats": list((taxonomy or {}).get("expected_cats", set())),
            },
            "domain_route":    domain_route or [],
            "complexity_score": round(complexity_score, 3),
            "response_mode":   response_mode,
        }

    # ── Stage recording ────────────────────────────────────────────────────────

    @_safe
    def record_faiss(self, chunks: list, scores: list):
        """Record FAISS results. chunks[i] ↔ scores[i] (cosine similarities)."""
        snap = []
        for rank, (ch, sim) in enumerate(zip(chunks, scores)):
            rec = self._get_or_create(ch)
            if rec is None:
                continue
            if rec.chunk_id not in self._entered:
                rec.entered_at = "faiss"
                self._entered.add(rec.chunk_id)
            if "faiss" not in rec.retrieval_sources:
                rec.retrieval_sources.append("faiss")
            # Only record if this is the best FAISS rank seen for this chunk
            if rec.faiss_rank is None or rank < rec.faiss_rank:
                rec.faiss_rank  = rank
                rec.faiss_score = round(float(sim), 5)
            snap.append({"chunk_id": rec.chunk_id, "rank": rank, "score": round(float(sim), 5)})
        self._stages["faiss"] = snap
        self.stage_counts["faiss"] = len(snap)

    @_safe
    def record_bm25(self, chunks: list, scores: list):
        """Record BM25 results. chunks[i] ↔ scores[i]."""
        snap = []
        for rank, (ch, score) in enumerate(zip(chunks, scores)):
            rec = self._get_or_create(ch)
            if rec is None:
                continue
            if rec.chunk_id not in self._entered:
                rec.entered_at = "bm25"
                self._entered.add(rec.chunk_id)
            if "bm25" not in rec.retrieval_sources:
                rec.retrieval_sources.append("bm25")
            if rec.bm25_rank is None or rank < rec.bm25_rank:
                rec.bm25_rank  = rank
                rec.bm25_score = round(float(score), 5)
            snap.append({"chunk_id": rec.chunk_id, "rank": rank, "score": round(float(score), 5)})
        self._stages["bm25"] = snap
        self.stage_counts["bm25"] = len(snap)

    @_safe
    def record_tfidf(self, chunks: list, scores: list):
        """Record TF-IDF results."""
        snap = []
        for rank, (ch, score) in enumerate(zip(chunks, scores)):
            rec = self._get_or_create(ch)
            if rec is None:
                continue
            if rec.chunk_id not in self._entered:
                rec.entered_at = "tfidf"
                self._entered.add(rec.chunk_id)
            if "tfidf" not in rec.retrieval_sources:
                rec.retrieval_sources.append("tfidf")
            if rec.tfidf_rank is None or rank < rec.tfidf_rank:
                rec.tfidf_rank  = rank
                rec.tfidf_score = round(float(score), 5)
            snap.append({"chunk_id": rec.chunk_id, "rank": rank, "score": round(float(score), 5)})
        self._stages["tfidf"] = snap
        self.stage_counts["tfidf"] = len(snap)

    @_safe
    def record_rrf(self, chunks: list):
        """Record RRF-merged pool. Each chunk should have _rrf_score set."""
        snap = []
        for rank, ch in enumerate(chunks):
            rec = self._get_or_create(ch)
            if rec is None:
                continue
            rrf_val = ch.get("_rrf_score")
            if rrf_val is not None:
                rec.rrf_score = round(float(rrf_val), 6)
            snap.append({"chunk_id": rec.chunk_id, "rank": rank, "score": rec.rrf_score})
        self._stages["rrf"] = snap
        self.stage_counts["rrf"] = len(snap)

    @_safe
    def record_injected(self, chunk: dict, reason: str, score: float = None):
        """Record a chunk injected by any non-FAISS/BM25 mechanism."""
        rec = self._get_or_create(chunk)
        if rec is None:
            return
        if rec.chunk_id not in self._entered:
            rec.entered_at = reason
            self._entered.add(rec.chunk_id)
        rec.injection_reason = reason
        if score is not None:
            rec.injection_score = round(float(score), 5)
        if reason not in rec.retrieval_sources:
            rec.retrieval_sources.append(reason)

    @_safe
    def snapshot_stage(self, name: str, chunks: list, score_field: str = "_final_legal_score"):
        """Capture an ordered snapshot of (chunk_id, score) at a named stage.

        Used after CrossEncoder, LegalReranker, doc-boost, MMR, circular-floor, Layer 6.
        Also updates the per-chunk record with the score from this stage if it's a
        reranking stage.
        """
        snap = []
        for rank, ch in enumerate(chunks):
            cid = ch.get("chunk_id")
            if not cid:
                continue
            score = ch.get(score_field)
            snap.append({
                "chunk_id": cid,
                "rank":     rank,
                "score":    round(float(score), 5) if score is not None else None,
            })
            # Update per-chunk record with stage-specific scores
            rec = self._chunks.get(cid)
            if rec is None:
                rec = self._get_or_create(ch)
            if rec:
                if name == "after_crossencoder":
                    rec.cross_encoder_score = round(float(score), 5) if score else None
                    # Also capture authority_boost if stored on chunk
                    ab = ch.get("_authority_boost")
                    if ab is not None:
                        rec.authority_boost = round(float(ab), 4)
                elif name in ("after_legalreranker", "after_doc_boost", "after_circular_floor",
                              "after_layer6", "after_mandatory", "final"):
                    rec.legal_reranker_score = round(float(score), 5) if score else None

        self._stages[name] = snap
        self.stage_counts[name] = len(snap)

    @_safe
    def record_crossencoder_scores(self, chunks: list):
        """After _cascade_rerank: read _rerank_score from every chunk."""
        snap = []
        for rank, ch in enumerate(chunks):
            cid = ch.get("chunk_id")
            if not cid:
                continue
            rec = self._chunks.get(cid) or self._get_or_create(ch)
            if rec:
                rs = ch.get("_rerank_score")
                if rs is not None:
                    rec.cross_encoder_score = round(float(rs), 5)
                ab = ch.get("_authority_boost")
                if ab is not None:
                    rec.authority_boost = round(float(ab), 4)
            score = ch.get("_rerank_score")
            snap.append({"chunk_id": cid, "rank": rank,
                         "score": round(float(score), 5) if score else None})
        self._stages["after_crossencoder"] = snap
        self.stage_counts["after_crossencoder"] = len(snap)

    @_safe
    def record_legalreranker_scores(self, chunks: list):
        """After LegalReranker: read _final_legal_score from every chunk."""
        snap = []
        for rank, ch in enumerate(chunks):
            cid = ch.get("chunk_id")
            if not cid:
                continue
            rec = self._chunks.get(cid) or self._get_or_create(ch)
            if rec:
                fs = ch.get("_final_legal_score")
                if fs is not None:
                    rec.legal_reranker_score = round(float(fs), 5)
                db = ch.get("_doc_hit_count")
                if db is not None and db > 1:
                    import math
                    rec.doc_level_boost = round(math.log(db) * 0.02, 5)
            score = ch.get("_final_legal_score")
            snap.append({"chunk_id": cid, "rank": rank,
                         "score": round(float(score), 5) if score else None})
        self._stages["after_legalreranker"] = snap
        self.stage_counts["after_legalreranker"] = len(snap)

    @_safe
    def record_mmr(self, pre_mmr: list, post_mmr: list):
        """Compare pre/post MMR lists to record what was kept vs. removed."""
        kept_ids  = {c.get("chunk_id") for c in post_mmr if c.get("chunk_id")}
        snap_pre  = []
        snap_post = []

        for rank, ch in enumerate(pre_mmr):
            cid = ch.get("chunk_id")
            if not cid:
                continue
            snap_pre.append({"chunk_id": cid, "rank": rank,
                              "score": round(float(ch.get("_final_legal_score", 0)), 5)})
            rec = self._chunks.get(cid) or self._get_or_create(ch)
            if rec:
                if cid in kept_ids:
                    rec.mmr_kept = True
                else:
                    rec.mmr_kept = False
                    rec.elimination_reason = "mmr_removed"

        for rank, ch in enumerate(post_mmr):
            cid = ch.get("chunk_id")
            if not cid:
                continue
            snap_post.append({"chunk_id": cid, "rank": rank,
                               "score": round(float(ch.get("_final_legal_score", 0)), 5)})

        self._stages["pre_mmr"]  = snap_pre
        self._stages["post_mmr"] = snap_post
        self.stage_counts["pre_mmr"]  = len(snap_pre)
        self.stage_counts["post_mmr"] = len(snap_post)
        self.stage_counts["mmr_removed"] = len(snap_pre) - len(snap_post)

    # ── Validation ────────────────────────────────────────────────────────────

    @_safe
    def record_validation(self, *,
                           expected_cats: set = None,
                           present_cats: set = None,
                           missing_cats: set = None,
                           layer6_injections: list = None,
                           mandatory_coverage_pct: float = 100.0,
                           mandatory_missing: list = None):
        self.validation = {
            "expected_categories":    sorted(expected_cats or []),
            "present_categories":     sorted(present_cats or []),
            "missing_categories":     sorted(missing_cats or []),
            "layer6_injections":      layer6_injections or [],
            "mandatory_coverage_pct": mandatory_coverage_pct,
            "mandatory_missing":      mandatory_missing or [],
        }

    # ── Finalization ──────────────────────────────────────────────────────────

    @_safe
    def finalize(self, final_chunks: list, answer_meta: dict = None):
        """
        Called after search() returns. Marks which chunks are selected,
        builds document aggregation, records answer metadata.
        """
        selected_ids = {c.get("chunk_id") for c in final_chunks if c.get("chunk_id")}

        # Mark selected
        for ch in final_chunks:
            cid = ch.get("chunk_id")
            if not cid:
                continue
            rec = self._chunks.get(cid) or self._get_or_create(ch)
            if rec:
                rec.selected = True
                # Build selection_reasons from chunk metadata flags
                reasons = []
                if ch.get("_pinned_by_ref"):       reasons.append("taxonomy_pin")
                if ch.get("_targeted_fill"):        reasons.append("quota_fill")
                if ch.get("_targeted_circ_bm25"):   reasons.append("circular_bm25")
                if ch.get("_targeted_circ_faiss"):  reasons.append("circular_faiss")
                if ch.get("_coverage_fill"):        reasons.append("layer6_coverage")
                if ch.get("_mandatory_inject"):     reasons.append("mandatory_inject")
                if ch.get("_citation_graph_expand"):reasons.append("citation_graph")
                if ch.get("_self_critique_inject"): reasons.append("self_critique")
                # Infer FAISS / BM25 from existing record
                if rec.faiss_rank is not None:  reasons.append("faiss")
                if rec.bm25_rank  is not None:  reasons.append("bm25")
                if rec.tfidf_rank is not None:  reasons.append("tfidf")
                # Deduplicate preserving order
                seen = set()
                rec.selection_reasons = [r for r in reasons if not (r in seen or seen.add(r))]
                # Final score
                fs = ch.get("_final_legal_score") or ch.get("_rerank_score")
                if fs is not None:
                    rec.legal_reranker_score = round(float(fs), 5)

        # Mark non-selected as eliminated (if not already MMR-removed)
        for cid, rec in self._chunks.items():
            if cid not in selected_ids and not rec.selected:
                if rec.elimination_reason is None:
                    rec.elimination_reason = "score_cutoff"

        # Build final stage snapshot
        snap = []
        for rank, ch in enumerate(final_chunks):
            cid = ch.get("chunk_id")
            if not cid:
                continue
            score = ch.get("_final_legal_score") or ch.get("_rerank_score")
            snap.append({"chunk_id": cid, "rank": rank,
                          "score": round(float(score), 5) if score else None,
                          "document_id": _doc_id(ch.get("rel_path") or ""),
                          "document_type": _doc_type(ch.get("rel_path") or "")})
        self._stages["final"] = snap

        # Document aggregation
        doc_data: dict = {}
        for rank, ch in enumerate(final_chunks):
            rel  = ch.get("rel_path") or ""
            did  = _doc_id(rel)
            score = float(ch.get("_final_legal_score") or ch.get("_rerank_score") or 0)
            srcs = self._chunks.get(ch.get("chunk_id"), ChunkRecord("","","","","")).retrieval_sources
            if did not in doc_data:
                doc_data[did] = {
                    "document_id":       did,
                    "document_type":     _doc_type(rel),
                    "rel_path":          rel,
                    "chunks_in_final":   0,
                    "best_chunk_score":  0.0,
                    "mean_chunk_score":  0.0,
                    "_score_sum":        0.0,
                    "retrieval_sources": set(),
                    "final_rank":        rank,
                }
            d = doc_data[did]
            d["chunks_in_final"]  += 1
            d["_score_sum"]       += score
            d["mean_chunk_score"]  = round(d["_score_sum"] / d["chunks_in_final"], 5)
            d["best_chunk_score"]  = round(max(d["best_chunk_score"], score), 5)
            d["retrieval_sources"].update(srcs)

        # Convert sets to lists; remove internal _score_sum
        for did, d in doc_data.items():
            d["retrieval_sources"] = sorted(d["retrieval_sources"])
            del d["_score_sum"]
        self.documents = doc_data

        # Final context metadata
        total_tokens = sum(len((c.get("text") or "").split()) for c in final_chunks)
        self.final_context = {
            "chunk_count":    len(final_chunks),
            "document_count": len(doc_data),
            "approx_tokens":  total_tokens,
            "chunk_ids":      [c.get("chunk_id") for c in final_chunks],
        }

        # Answer metadata (if provided)
        if answer_meta:
            self.answer = answer_meta

        self.stage_counts["final"] = len(final_chunks)

    # ── Serialization ─────────────────────────────────────────────────────────

    def to_log_dict(self) -> dict:
        """
        Compact CloudWatch log dict.
        Logged as a single JSON line with trace_type="retrieval_trace" for
        easy filtering in CloudWatch Logs Insights:
          filter trace_type = "retrieval_trace" | filter query_id = "LETA-..."
        """
        elapsed_ms = round((time.time() - self.created_at) * 1000)
        pre = self.preprocessing

        # Summarize what each stage produced
        stage_summary = {k: v for k, v in self.stage_counts.items()}

        # Per-stage top-3 chunk_ids + scores for quick scanning
        top_per_stage = {}
        for stage_name in ("faiss", "bm25", "rrf", "after_crossencoder",
                           "after_legalreranker", "post_mmr", "final"):
            snap = self._stages.get(stage_name, [])
            top_per_stage[stage_name] = [
                {"chunk_id": s["chunk_id"][:20], "doc": _doc_id(
                    (self._chunks.get(s["chunk_id"]) or ChunkRecord("","","","","")).rel_path
                ), "score": s["score"]}
                for s in snap[:3]
            ]

        # Selected chunk summary
        selected_chunks = [r.to_dict() for r in self._chunks.values() if r.selected]
        selected_summary = [
            {
                "chunk_id":        c["chunk_id"][:20],
                "document_id":     c["document_id"],
                "document_type":   c["document_type"],
                "faiss_rank":      c["faiss_rank"],
                "bm25_rank":       c["bm25_rank"],
                "rrf_score":       c["rrf_score"],
                "cross_encoder":   c["cross_encoder_score"],
                "legal_reranker":  c["legal_reranker_score"],
                "selected_by":     c["selection_reasons"],
            }
            for c in selected_chunks
        ]

        return {
            "trace_type":     "retrieval_trace",
            "query_id":       self.query_id,
            "query":          self.query[:200],
            "elapsed_ms":     elapsed_ms,
            "topic":          pre.get("topic"),
            "complexity":     pre.get("complexity_score"),
            "response_mode":  pre.get("response_mode"),
            "taxonomy_topics":pre.get("taxonomy", {}).get("topics", []),
            "taxonomy_conf":  pre.get("taxonomy", {}).get("confidence", 0),
            "domain_route":   pre.get("domain_route", [])[:4],
            "detected_refs":  pre.get("detected_refs", [])[:6],
            "stage_counts":   stage_summary,
            "top_per_stage":  top_per_stage,
            "selected_chunks":selected_summary,
            "documents_in_final": [
                {"doc_id": d["document_id"], "type": d["document_type"],
                 "chunks": d["chunks_in_final"], "best_score": d["best_chunk_score"]}
                for d in sorted(self.documents.values(),
                                key=lambda x: x["best_chunk_score"], reverse=True)
            ],
            "validation":      self.validation,
            "answer_model":    self.answer.get("model"),
            "answer_latency":  self.answer.get("latency_ms"),
            "cache_hit":       self.answer.get("cache_hit", False),
        }

    def to_debug_dict(self) -> dict:
        """Full detail for /debug/trace/{query_id}."""
        return {
            "query_id":      self.query_id,
            "query":         self.query,
            "created_at":    self.created_at,
            "elapsed_ms":    round((time.time() - self.created_at) * 1000),
            "preprocessing": self.preprocessing,
            "stage_counts":  self.stage_counts,
            "stages":        self._stages,
            "all_chunks":    [r.to_dict() for r in self._chunks.values()],
            "documents":     list(self.documents.values()),
            "validation":    self.validation,
            "final_context": self.final_context,
            "answer":        self.answer,
        }


# ─── In-memory ring buffer (debug endpoint storage) ───────────────────────────
# Stores the last 500 traces. Access via get_trace(query_id) and list_traces().

_RING_MAX = 500
_ring: deque = deque(maxlen=_RING_MAX)             # ordered list of query_ids (newest last)
_store: dict  = {}                                   # query_id → trace.to_debug_dict()
_store_lock   = threading.Lock()


def store_trace(trace: RetrievalTrace) -> None:
    """Persist trace to in-memory ring buffer. Called once per query."""
    try:
        with _store_lock:
            if len(_ring) == _RING_MAX:
                oldest = _ring[0]
                _store.pop(oldest, None)
            _ring.append(trace.query_id)
            _store[trace.query_id] = trace.to_debug_dict()
    except Exception as e:
        logger.debug(f"store_trace failed (non-fatal): {e}")


def get_trace(query_id: str) -> Optional[dict]:
    with _store_lock:
        return _store.get(query_id)


def list_traces(limit: int = 50) -> list:
    """Return summary of most recent traces (newest first)."""
    with _store_lock:
        ids = list(reversed(list(_ring)))[:limit]
        result = []
        for qid in ids:
            d = _store.get(qid, {})
            result.append({
                "query_id":    qid,
                "query":       d.get("query", "")[:120],
                "elapsed_ms":  d.get("elapsed_ms"),
                "topic":       d.get("preprocessing", {}).get("topic"),
                "final_count": d.get("stage_counts", {}).get("final", 0),
                "cache_hit":   d.get("answer", {}).get("cache_hit", False),
            })
        return result
