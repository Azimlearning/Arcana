# Evaluation results

Result files referenced by the MCAIT 2026 camera-ready paper (EDAS #1571344896), Section VI.

| File | What it is |
|---|---|
| `ablation_smoke.json` | The **pilot run** reported in the paper (Table V). All 20 pre-registered questions (`eval/questions.yaml`, committed 9 Jun 2026) through five arms: dense, sparse, graph, flat, hybrid. Index and graph built from **4 of the 16** manifest documents (796 nodes, 859 edges). Generated 2026-09-07T07:26Z, **before** the approximate query-entity resolution change in `api/stores/*` and `api/retrieval/graph.py`, so the graph arm ran under exact-match resolution. |
| `ingest_summary.json` | Resumed ingestion of the benchmark corpus. Entity extraction for the remaining documents stopped when the model provider returned HTTP 402 (quota exhausted), which is why no full 16-document run exists yet. |

Scripts: `eval/run_ablation.py` (ablation + paired Wilcoxon), `eval/extraction_audit.py`
(edge-sampling audit, not yet run), `eval/ingest_corpus.py`, `eval/extract_only.py`,
`eval/probe_entities.py`. The corpus is listed by arXiv identifier in `eval/corpus/MANIFEST.json`;
the PDFs themselves are not redistributed.
