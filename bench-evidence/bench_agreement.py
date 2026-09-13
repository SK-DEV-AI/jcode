#!/usr/bin/env python3
"""Inter-judge agreement + manual spot-check for the recall bench gold labels.

Robustness question: is the measurement instrument (a free model) stable?
If two independent model families disagree, the labels are noise and any
recall delta built on them is untrustworthy.
"""
import json
import sys

BENCH = "/home/sk/jcode-memory-bench/labels"


def load(name):
    rows = {}
    with open(f"{BENCH}/{name}.jsonl") as f:
        for line in f:
            r = json.loads(line)
            rows[r["qid"]] = set(r["relevant_ids"])
    return rows


def jaccard(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main():
    files = sys.argv[1:] or ["gold_muse13", "gold_nemotron"]
    judges = {f: load(f) for f in files}
    qids = sorted(set.intersection(*[set(j) for j in judges.values()]))

    print(f"Judges: {list(judges)}  |  common queries: {len(qids)}\n")

    agree_exact = 0
    agree_lenient = 0  # agree that the query has *some* relevant memory (or none)
    jaccards = []
    for qid in qids:
        sets = [judges[f].get(qid, set()) for f in files]
        if all(s == sets[0] for s in sets):
            agree_exact += 1
        if all(bool(s) == bool(sets[0]) for s in sets):
            agree_lenient += 1
        a, b = sets[0], sets[1]
        jaccards.append(jaccard(a, b))

    n = len(qids)
    print(f"Exact set agreement:   {agree_exact}/{n} ({100*agree_exact/n:.1f}%)")
    print(f"Empty/non-empty agree: {agree_lenient}/{n} ({100*agree_lenient/n:.1f}%)")
    print(f"Mean Jaccard:          {sum(jaccards)/n:.3f}")

    # Of queries at least one judge called non-empty, how many both call non-empty?
    union_nonempty = [q for q in qids if any(judges[f].get(q) for f in files)]
    both_nonempty = [q for q in union_nonempty if all(judges[f].get(q) for f in files)]
    print(
        f"\nNon-empty union: {len(union_nonempty)}  |  both non-empty: {len(both_nonempty)}"
        f" ({100*len(both_nonempty)/max(1,len(union_nonempty)):.1f}%)"
    )

    # Sample a few disagreements for manual inspection
    dis = [q for q in qids if judges[files[0]].get(q) != judges[files[1]].get(q)]
    print(f"\nDisagreements: {len(dis)} — first 3:")
    for q in dis[:3]:
        print(f"  {q}: {files[0]}={sorted(judges[files[0]].get(q,set()))} "
              f"{files[1]}={sorted(judges[files[1]].get(q,set()))}")


if __name__ == "__main__":
    main()
