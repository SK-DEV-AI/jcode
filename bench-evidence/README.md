# Focused-CE bench evidence for #1228

Local rerun of `memory_recall_bench` comparing `hybrid` vs `ce_rerank_focused`.

## Corpus (local, not upstream's)
- Memory graph: single project graph, 29 memories (`~/.jcode/memory/projects/*.json`)
- Queries: 181 replayed from local sessions
  (`memory_recall_bench queries --max_sessions=40 --per_session=10`)
- Pool: 50 candidates per query

## Labels (proxy-judged, NOT sonnet)
- `gold_muse13_181q.jsonl`: 11 queries with >=1 relevant, 31 labels
- `gold_nemotron_181q.jsonl`: 102 queries with >=1 relevant, 711 labels
- Judge prompt: same contract as `build_judge_prompt` (strict precision).
- Scripts: `bench_judge.py` (judge via OpenAI-compatible endpoint),
  `bench_agreement.py` (inter-judge Jaccard).

## Results (recall@5)
| config | muse labels | nemotron labels |
| hybrid | 0.000 | 0.132 |
| hybrid_focused | 0.242 | 0.199 |
| ce_rerank_focused | 0.356 | 0.349 |

## Latency (CPU-only, candle, 181 queries)
- hybrid: 11.6s total = ~64 ms/query
- ce_rerank_focused: 216s total = ~1194 ms/query
- CE overhead: ~1130 ms/query (20-pair rescore, cold model load included)

## Reproduce (same-corpus decider goes here)
Upstream's recorded hybrid 0.530 came from the maintainer's own
`~/jcode-memory-bench` (larger graph + sonnet labels), which is not in the
repo. To decide, run on that corpus:
`memory_recall_bench metrics --corpus=<shared> --config=hybrid`
`memory_recall_bench metrics --corpus=<shared> --config=ce_rerank_focused --reranker=<ms-marco-minilm dir>`
