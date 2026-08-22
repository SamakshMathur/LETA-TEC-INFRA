"""
quick_score.py — BM25-only accuracy scan.
Runs all 57 regression tests using only BM25 (no embedding model needed).
Uses the FIXED evaluate_result logic (provision_keys, V2.0 folder names).
"""
import json, re, sys, time, collections
from pathlib import Path
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).parent.parent
CHUNKS_PATH  = ROOT / "data/chunks/chunks.jsonl"
SUITE_PATH   = ROOT / "data/regression/gst_regression_suite.json"

TOP_K        = 12   # return top-12 from full-corpus BM25
STAT_INJECT  = 6    # also inject top-6 from statute-isolated BM25
CIRC_INJECT  = 5    # also inject top-5 from circular-isolated BM25
NOTIF_INJECT = 5    # also inject top-5 from notification-isolated BM25

# ── Tokeniser ─────────────────────────────────────────────────────────────────
_STOP = frozenset("""a an the and or of in to is for are be this that with by
                     on at from as it its any all not no shall be been being
                     have has had do does did will would could should may might
                     must can the a""".split())

def tokenize(text: str) -> list:
    tokens = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in _STOP]

# ── Fixed _chunk_category ──────────────────────────────────────────────────────
_CASE_LAW_FOLDERS     = {"high court case laws", "supreme court case laws", "aar", "other app result"}
_CIRCULAR_FOLDERS     = {"circulars", "circular", "icai", "brochures", "faqs", "circulars(2017-2025)"}
_NOTIF_FOLDERS        = {"notification", "notifications", "rate_notifications_2.0"}
_STATUTE_FOLDERS      = {"act", "rules", "cgst", "igst", "utgst", "export",
                          "cgst acts", "igst acts", "igst rules", "cgst rules"}

def _chunk_category(chunk: dict) -> str:
    meta = chunk.get("metadata", {})
    rel  = (chunk.get("rel_path") or meta.get("rel_path", "")).replace("\\", "/").lower()
    parts = set(rel.split("/"))
    def _match(folder_set):
        for f in folder_set:
            for p in parts:
                if p == f or p.startswith(f):
                    return True
        return False
    if _match(_CASE_LAW_FOLDERS):     return "case_law"
    if _match(_CIRCULAR_FOLDERS):     return "circular"
    if _match(_NOTIF_FOLDERS):        return "notification"
    if _match(_STATUTE_FOLDERS):      return "statute"
    return "other"

# ── Circular key ──────────────────────────────────────────────────────────────
_CIR_RE = re.compile(
    r'(?:circular[s]?[-_.\s]*(?:[a-z]*[-_.\s]*)?(?:no[-_.\s]*)?'
    r'|cir[-_.](?:cgst[-_.])?|cir(?=[0-9])|circularno[-_.])'
    r'(\d{2,3})',
    re.IGNORECASE,
)
_CIR_LEAD = re.compile(r'^(\d{2,3})[-_]\d+[-_]\d{4}', re.IGNORECASE)

def _circular_key(rel: str):
    fname = rel.replace("\\", "/").split("/")[-1]
    m = _CIR_RE.search(fname) or _CIR_LEAD.match(fname)
    return f"CIRCULAR_{m.group(1)}" if m else None

# ── Fixed evaluate_result ──────────────────────────────────────────────────────
def _kw_present(kw: str, text: str) -> bool:
    kl = kw.lower()
    if kl in text:
        return True
    m = re.match(r'^(\d+(?:\.\d+)?)%$', kl)
    if m:
        n = float(m.group(1))
        ns = str(int(n)) if n == int(n) else str(n)
        h  = n / 2
        hs = str(int(h)) if h == int(h) else str(h)
        for form in (f"{ns} per cent", f"{hs} per cent", f"{ns}%", f"{hs}%"):
            if form in text:
                return True
    return False

def evaluate_result(test: dict, chunks: list) -> dict:
    req_cats  = set(test.get("required_cats", []))
    req_auths = list(test.get("required_authorities", []))
    req_kws   = list(test.get("required_keywords", []))

    present_cats:  set = set()
    present_provs: set = set()
    present_circs: set = set()
    all_text = ""

    for chunk in chunks:
        meta = chunk.get("metadata", {}) or {}
        present_cats.add(_chunk_category(chunk))
        # Accept both old "provisions" schema and new "provision_keys" schema
        for p in ((meta.get("provisions") or [])
                  + (meta.get("citations") or [])
                  + (meta.get("provision_keys") or [])):
            if p:
                present_provs.add(p)
        _ap = chunk.get("_anchor_provision")
        if _ap:
            present_provs.add(_ap)
        for p in (chunk.get("provisions") or []) + (chunk.get("citations") or []):
            if p:
                present_provs.add(p)
        rel = chunk.get("rel_path") or meta.get("rel_path", "")
        ck  = _circular_key(rel)
        if ck:
            present_circs.add(ck)
        all_text += " " + (chunk.get("content") or chunk.get("text") or "").lower()

    cats_missing  = sorted(req_cats - present_cats)
    cats_found    = sorted(req_cats & present_cats)
    auths_found:   list = []
    auths_missing: list = []
    for auth in req_auths:
        if auth in present_circs:
            auths_found.append(auth)
        elif auth in present_provs or any(p.startswith(auth + "_") for p in present_provs):
            auths_found.append(auth)
        else:
            auths_missing.append(auth)

    kws_found   = [kw for kw in req_kws if _kw_present(kw, all_text)]
    kws_missing = [kw for kw in req_kws if not _kw_present(kw, all_text)]
    kw_cov = len(kws_found) / len(req_kws) if req_kws else 1.0
    KW_THRESH = 0.70

    verdict = "pass"
    reasons = []
    if cats_missing:
        verdict = "fail"
        reasons.append(f"cats missing: {cats_missing}")
    if auths_missing:
        verdict = "fail"
        reasons.append(f"auths missing: {auths_missing}")
    if kw_cov < KW_THRESH:
        verdict = "fail" if verdict == "pass" else verdict
        reasons.append(f"kw_cov={kw_cov:.0%} ({len(kws_found)}/{len(req_kws)})")
    return {
        "verdict": verdict,
        "cats_missing": cats_missing,
        "auths_missing": auths_missing,
        "kw_coverage": kw_cov,
        "reasons": reasons,
    }

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    print("Loading chunks…")
    chunks = []
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    print(f"  {len(chunks)} chunks loaded ({time.time()-t0:.1f}s)")

    print("Building BM25 indexes…")
    corpus_tok = [tokenize(c.get("text", "")) for c in chunks]
    bm25 = BM25Okapi(corpus_tok)

    # Statute-isolated BM25
    stat_idx_map = [i for i, c in enumerate(chunks) if _chunk_category(c) == "statute"]
    bm25_stat = BM25Okapi([tokenize(chunks[i].get("text","")) for i in stat_idx_map]) if stat_idx_map else None

    # Circular-isolated BM25 (circulars only, no notifications)
    circ_idx_map = [i for i, c in enumerate(chunks) if _chunk_category(c) == "circular"]
    bm25_circ = BM25Okapi([tokenize(chunks[i].get("text","")) for i in circ_idx_map]) if circ_idx_map else None

    # Notification-isolated BM25 (rate notifications — HS codes, schedules, rates)
    notif_idx_map = [i for i, c in enumerate(chunks) if _chunk_category(c) == "notification"]
    bm25_notif = BM25Okapi([tokenize(chunks[i].get("text","")) for i in notif_idx_map]) if notif_idx_map else None

    print(f"  Full BM25: {len(chunks)}, Statute: {len(stat_idx_map)}, Circular: {len(circ_idx_map)}, Notification: {len(notif_idx_map)} ({time.time()-t0:.1f}s)")

    tests = json.loads(SUITE_PATH.read_text(encoding="utf-8"))["tests"]
    print(f"Running {len(tests)} tests (full top-{TOP_K} + stat top-{STAT_INJECT} + circ top-{CIRC_INJECT} + notif top-{NOTIF_INJECT})…\n")

    results = []
    topic_pass = collections.Counter()
    topic_total = collections.Counter()

    for i, test in enumerate(tests):
        query = test["query"]
        q_tok = tokenize(query)

        # Full-corpus BM25 top-K
        scores = bm25.get_scores(q_tok)
        top_k  = sorted(range(len(scores)), key=lambda x: -scores[x])[:TOP_K]
        seen   = set(top_k)
        top_chunks = [chunks[j] for j in top_k]

        # Statute-isolated BM25 injection
        if bm25_stat is not None:
            s_scores = bm25_stat.get_scores(q_tok)
            s_top    = sorted(range(len(s_scores)), key=lambda x: -s_scores[x])[:STAT_INJECT]
            for li in s_top:
                if s_scores[li] <= 0:
                    break
                gi = stat_idx_map[li]
                if gi not in seen:
                    top_chunks.append(chunks[gi])
                    seen.add(gi)

        # Circular-isolated BM25 injection
        if bm25_circ is not None:
            c_scores = bm25_circ.get_scores(q_tok)
            c_top    = sorted(range(len(c_scores)), key=lambda x: -c_scores[x])[:CIRC_INJECT]
            for li in c_top:
                if c_scores[li] <= 0:
                    break
                gi = circ_idx_map[li]
                if gi not in seen:
                    top_chunks.append(chunks[gi])
                    seen.add(gi)

        # Notification-isolated BM25 injection
        if bm25_notif is not None:
            n_scores = bm25_notif.get_scores(q_tok)
            n_top    = sorted(range(len(n_scores)), key=lambda x: -n_scores[x])[:NOTIF_INJECT]
            for li in n_top:
                if n_scores[li] <= 0:
                    break
                gi = notif_idx_map[li]
                if gi not in seen:
                    top_chunks.append(chunks[gi])
                    seen.add(gi)

        ev = evaluate_result(test, top_chunks)
        verdict = ev["verdict"]
        topic = test.get("topic", "unknown")
        topic_total[topic] += 1
        if verdict == "pass":
            topic_pass[topic] += 1

        flag = "✅" if verdict == "pass" else "❌"
        reason_str = "; ".join(ev["reasons"]) if ev["reasons"] else "—"
        print(f"  [{i+1:02d}] {flag} {test['id']:40s} kw={ev['kw_coverage']:.0%}  {reason_str}")
        results.append({"test": test, "verdict": verdict, "eval": ev})

    passed = sum(1 for r in results if r["verdict"] == "pass")
    total  = len(results)
    elapsed = time.time() - t0

    print(f"\n{'='*70}")
    print(f"  RESULTS (BM25-only, top-{TOP_K}):  {passed}/{total} = {passed/total:.0%}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"\n  By topic:")
    for topic in sorted(topic_total, key=lambda x: (x is None, x)):
        p = topic_pass[topic]
        t = topic_total[topic]
        bar = "█" * p + "░" * (t - p)
        print(f"    {topic:12s}  {p}/{t}  {bar}")

    # Coverage histogram
    covs = [r["eval"]["kw_coverage"] for r in results]
    avg_cov = sum(covs) / len(covs) if covs else 0
    print(f"\n  Avg keyword coverage: {avg_cov:.1%}")
    below_thresh = sum(1 for c in covs if c < 0.70)
    print(f"  Tests below 70% kw threshold: {below_thresh}/{total}")
    cats_fail = sum(1 for r in results if r["eval"]["cats_missing"])
    auths_fail = sum(1 for r in results if r["eval"]["auths_missing"])
    print(f"  Tests failing category check: {cats_fail}/{total}")
    print(f"  Tests failing authority check: {auths_fail}/{total}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
