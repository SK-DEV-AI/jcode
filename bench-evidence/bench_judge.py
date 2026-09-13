#!/usr/bin/env python3
"""Bridge the memory_recall_bench judge stage through the local opencode2api proxy.

The bench's own `judge` subcommand pins OpenAI/Claude credentials via the
sidecar (hardcoded endpoints, no env override). We have neither — but we do
have the proxy with free models. This reproduces the bench's judge contract
exactly:
  input:  labels/pool.jsonl + labels/queries.jsonl
  prompt: JUDGE_SYSTEM + build_judge_prompt (same text as the Rust source)
  output: labels/gold.jsonl  {qid, relevant_ids}

Model choice is a METHODOLOGICAL CAVEAT for the result: the upstream bench
used claude-sonnet-4-5; we use a free model. Gold-label quality bounds the
metric's meaningfulness, so this is stated in the issue.
"""
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BENCH = os.path.expanduser("~/jcode-memory-bench")
PROXY = os.environ.get("PROXY", "http://127.0.0.1:8787/v1/chat/completions")
KEY = os.environ.get("PROXY_KEY", "local-dev-key")
MODEL = os.environ.get("JUDGE_MODEL", "muse-spark-1.3-contributor-free")
CONCURRENCY = int(os.environ.get("JUDGE_CONCURRENCY", "4"))

JUDGE_SYSTEM = (
    "You judge whether stored MEMORIES would be genuinely useful to surface to an AI coding agent given the CURRENT conversation context. "
    "Be strict and prefer precision: a memory is relevant ONLY if a competent engineer would say \"yes, knowing this specifically helps respond here.\" "
    "Mark relevant when the memory is a fact, user preference, correction, or procedure that applies to what is happening right now. "
    "Mark NOT relevant when it is off-topic, generic/obvious, only shares surface keywords, or would be noise. When unsure, exclude it. "
    "The context contains boilerplate (system reminders, tool output); focus on what is actually being worked on. "
    "Reply with ONLY a JSON array of the relevant candidate numbers, e.g. [1,4] or []. No prose."
)


def truncate_for_judge(s: str, max_chars: int = 6000) -> str:
    if len(s) <= max_chars:
        return s
    return s[-max_chars:]


def build_judge_prompt(query: str, candidates) -> str:
    p = "CURRENT CONTEXT:\n" + truncate_for_judge(query) + "\n\nCANDIDATE MEMORIES:\n"
    for i, c in enumerate(candidates):
        p += f"{i + 1}. {c['content'].replace(chr(10), ' ')}\n"
    p += "\nReturn the numbers of the relevant memories as a JSON array."
    return p


def parse_judge_response(resp: str, n: int):
    s = resp.find("[")
    e = resp.rfind("]")
    if s == -1 or e == -1 or e < s:
        return []
    try:
        nums = json.loads(resp[s : e + 1])
    except Exception:
        return []
    return [(x - 1) if isinstance(x, int) and 1 <= x <= n else None for x in nums]


def call_proxy(system: str, user: str, retries: int = 3) -> str:
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
    ).encode()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                PROXY,
                data=body,
                headers={
                    "Authorization": f"Bearer {KEY}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read())
            return d["choices"][0]["message"]["content"]
        except Exception as ex:
            last = ex
    raise RuntimeError(f"proxy call failed after {retries}: {last}")


def main():
    queries = {}
    with open(f"{BENCH}/labels/queries.jsonl") as f:
        for line in f:
            r = json.loads(line)
            queries[r["qid"]] = r["query"]

    pool = []
    with open(f"{BENCH}/labels/pool.jsonl") as f:
        for line in f:
            pool.append(json.loads(line))

    def judge(rec):
        qid = rec["qid"]
        cands = rec["candidates"]
        prompt = build_judge_prompt(queries.get(qid, ""), cands)
        try:
            resp = call_proxy(JUDGE_SYSTEM, prompt)
            idxs = [i for i in parse_judge_response(resp, len(cands)) if i is not None]
            rel = [cands[i]["id"] for i in idxs]
        except Exception as ex:
            print(f"judge failed {qid}: {ex}", file=sys.stderr)
            rel = []
        return {"qid": qid, "relevant_ids": rel}

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        results = list(ex.map(judge, pool))

    out = f"{BENCH}/labels/gold.jsonl"
    with open(out, "w") as f:
        for g in results:
            f.write(json.dumps(g) + "\n")
    with_rel = sum(1 for g in results if g["relevant_ids"])
    total = sum(len(g["relevant_ids"]) for g in results)
    print(f"Judged {len(results)} queries -> {out} ({with_rel} with >=1 relevant, {total} total labels)")


if __name__ == "__main__":
    main()
