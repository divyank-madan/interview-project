Resume Match Scoring (backend/main.py)

Overview

This document explains the scoring logic implemented in `backend/main.py`.

Components

- Keywords: extracted from job description and resume (stop words removed).  Used to compute `keyword_norm` (0..1).
- Phrases: short multi-word phrases from the JD; normalized and checked for literal presence in the resume.  Converted to `phrase_norm` (0..1).
- Sentence-level semantics: per-sentence embeddings are compared and averaged to produce a `sentence_semantic` score (0..1).
- Global (pooled) semantics: pooled embedding similarity across entire resume and JD produces `global_semantic` (0..1).

Combination

- `semantic_score` = max(sentence_semantic, global_semantic)
- `combined_keyword` = 0.7 * `keyword_norm` + 0.3 * `phrase_norm`
- `combined_score` = `semantic_weight` * `semantic_score` + (1 - `semantic_weight`) * `combined_keyword`
- `score` = round(clamp(combined_score, 0, 1) * 100)

Tunable parameters (in `backend/main.py`)

- `semantic_weight` (default 0.8): how much the final score favors semantic similarity vs keyword/phrase signals.
- `phrase` normalization divisor (3.0): controls how many phrase matches count as full phrase coverage.
- Aggressive boost: if `semantic_score >= 0.55` and matched keywords exceed a threshold, a boosted score is computed to favor candidates with both concept and coverage.
- High-semantic micro-boost: if `semantic_score > 0.85`, a small +8 adjustment is applied (capped at 100).

Output

The `/score` endpoint returns a `MatchResponse` containing:
- `fit`: boolean (score >= 55)
- `score`: integer 0..100
- `details`: human-readable string containing a breakdown (matched/missing keywords, phrase matches, semantic labels) and a component scores line: `Component scores - semantic: X%, keywords: Y%, phrases: Z%, combined: W%`.
- `matched_keywords`: list of matched keyword strings

How to adjust behavior

- Reduce `semantic_weight` towards 0 to favor exact keyword matches.
- Increase `semantic_weight` towards 1 to favor conceptual alignment.
- Tweak the aggressive boost thresholds (semantic threshold and `min_keyword_threshold`) to change when candidates receive the large boost.

Notes

- The implementation uses `sentence-transformers` (`all-MiniLM-L6-v2`) and may fetch model weights on first run.
- For deterministic tuning, test with representative JD/resume pairs and iterate on `semantic_weight` and the boost thresholds.

File: backend/main.py

Refer to `backend/main.py` for the exact implementation and inline comments.
