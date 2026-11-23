#!/usr/bin/env python3
"""IT5440 — tính lại toàn bộ bảng số liệu và kiểm định từ log thô.

Chỉ thư viện chuẩn. Chạy từ bất kỳ đâu:
    python3 analysis/analyze.py

Đọc ccbench/results/local_* (model cục bộ) và các lượt Claude đã công bố
(main_haiku, main_sonnet, oracle_trace_*) để so sánh trên cùng 64 câu.
Mọi điểm được chấm lại từ raw_response bằng scorer s2 hiện hành.
Ghi analysis/output/: SUMMARY.md, summary.json, cells.csv, mcnemar.csv.
"""

import csv
import json
import math
import os
import random
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "ccbench"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from ccbench.runner import load_records  # noqa: E402

RESULTS = os.path.join(ROOT, "ccbench", "results")
OUT = os.path.join(ROOT, "analysis", "output")
Z = 1.959964
LOCAL_PREFIXES = ("local_qwen7b", "local_qwen9b", "local_qwen14b")
CLAUDE_DIRS = {
    "claude-haiku-5-5": ["main_haiku-20261113-184053", "oracle_trace_haiku-20261113-202029"],
    "claude-sonnet-5-5": ["main_sonnet-20261113-184443", "oracle_trace_sonnet-20261113-205901"],
}


def wilson(k, n):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
    return min(1.0, 2 * tail)


def bootstrap_diff(xs, ys, seed=7, iters=10000):
    """CI 95% cho mean(x)-mean(y) ghép cặp theo mục (xs, ys: list 0/1 cùng thứ tự)."""
    n = len(xs)
    if n == 0:
        return (0.0, 0.0, 0.0)
    diffs = [x - y for x, y in zip(xs, ys)]
    point = sum(diffs) / n
    rng = random.Random(seed)
    boots = []
    for _ in range(iters):
        s = sum(diffs[rng.randrange(n)] for _ in range(n))
        boots.append(s / n)
    boots.sort()
    return point, boots[int(0.025 * iters)], boots[int(0.975 * iters)]


def cell_key(strategy, budget):
    if budget is None and strategy != "full":
        return strategy
    return "%s@%s" % (strategy, "full" if budget is None else budget)


def gather():
    """-> {model_label: {cell_key: {"items": {id: rec}, ...}}} + metadata toàn cục."""
    models = defaultdict(lambda: defaultdict(dict))
    meta = {"runs": [], "guards": []}
    dirs = sorted(os.listdir(RESULTS)) if os.path.isdir(RESULTS) else []
    for d in dirs:
        path = os.path.join(RESULTS, d)
        if not os.path.isfile(os.path.join(path, "results.jsonl")):
            continue
        is_local = d.startswith(LOCAL_PREFIXES)
        is_claude = any(d in v for v in CLAUDE_DIRS.values())
        if not (is_local or is_claude):
            continue
        recs = load_records(path)
        meta["runs"].append({"dir": d, "n_records": len(recs)})
        for r in recs:
            label = r["model_label"]
            ck = cell_key(r["strategy"], r["budget"])
            prev = models[label][ck].get(r["item_id"])
            if prev is None or r.get("timestamp", "") >= prev.get("timestamp", ""):
                models[label][ck][r["item_id"]] = r
            if is_local and r.get("status") == "ok":
                extra = r.get("provider_extra") or {}
                itok = r.get("input_tokens") or 0
                if r["strategy"] == "full" and r["budget"] is None and (r.get("scores") or {}).get("context_recall", 1.0) < 1.0:
                    # gold units missing from the full-repo prompt => truncation, regardless of tokenizer counts
                    meta["guards"].append("full-repo prompt missing gold units (possible truncation): %s %s input=%d" % (label, r["item_id"], itok))
                if extra.get("thinking_chars", 0) > 0:
                    meta["guards"].append("thinking leaked: %s %s %s" % (label, ck, r["item_id"]))
                if itok and itok + (r.get("output_tokens") or 0) >= extra.get("num_ctx", 32768) - 64:
                    meta["guards"].append("context window saturated: %s %s %s" % (label, ck, r["item_id"]))
    return models, meta


def ok_recs(cell):
    return [r for r in cell.values() if r.get("status") == "ok"]


def correct_ids(cell):
    return {i for i, r in cell.items() if r.get("status") == "ok" and (r.get("scores") or {}).get("correct")}


def cell_stats(cell):
    rs = ok_recs(cell)
    n = len(rs)
    k = sum(1 for r in rs if (r.get("scores") or {}).get("correct"))
    acc, lo, hi = wilson(k, n)
    extra = [(r.get("provider_extra") or {}) for r in rs]
    errs = defaultdict(int)
    for r in rs:
        errs[(r.get("scores") or {}).get("error_class", "?")] += 1
    itoks = [r.get("input_tokens") for r in rs if r.get("input_tokens")]
    return {
        "n_ok": n, "n_error": len(cell) - n, "correct": k, "acc": acc, "ci_lo": lo, "ci_hi": hi,
        "n_truncated": sum(1 for e in extra if e.get("done_reason") == "length"),
        "n_parse_error": sum(1 for r in rs if (r.get("scores") or {}).get("parse_error")),
        "mean_input_tokens": sum(itoks) / len(itoks) if itoks else None,
        "mean_context_recall": sum((r.get("scores") or {}).get("context_recall", 0) for r in rs) / n if n else None,
        "error_classes": dict(errs),
        "acc_by_level": {lv: wilson(sum(1 for r in rs if r["level"] == lv and (r.get("scores") or {}).get("correct")),
                                    sum(1 for r in rs if r["level"] == lv))
                         for lv in ("L1", "L2", "L3", "L4", "L5")},
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    models, meta = gather()
    local_labels = [l for l in models if not l.startswith("claude")]
    if not local_labels:
        print("Chưa có kết quả cục bộ trong ccbench/results/local_* — chạy trên server trước (SERVER_SETUP.md).")
        return
    order = sorted(models, key=lambda l: (l.startswith("claude"), l))

    cells = {l: {ck: cell_stats(c) for ck, c in models[l].items()} for l in models}

    # ---- retention R so với oracle (cùng tập câu đúng ở oracle) ----
    retention = {}
    for l in models:
        oc = correct_ids(models[l].get("oracle", {}))
        retention[l] = {}
        for ck, c in models[l].items():
            cc = correct_ids(c)
            retention[l][ck] = (len(cc & oc) / len(oc)) if oc else None

    # ---- McNemar từng ô giữa các cặp model ----
    pairs = []
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            for ck in sorted(set(models[a]) & set(models[b])):
                ca, cb = correct_ids(models[a][ck]), correct_ids(models[b][ck])
                ids = {r["item_id"] for r in ok_recs(models[a][ck])} & {r["item_id"] for r in ok_recs(models[b][ck])}
                bb = len((ca - cb) & ids)
                cc = len((cb - ca) & ids)
                pairs.append({"model_a": a, "model_b": b, "cell": ck, "a_only": bb, "b_only": cc,
                              "p": mcnemar_exact(bb, cc),
                              "acc_a": cells[a][ck]["acc"], "acc_b": cells[b][ck]["acc"]})

    # ---- verdicts theo RUNPLAN ----
    verdicts = {"HL1": {}, "HL2": {}, "HL3": {}, "HL4": {}, "HL5": {}}
    for l in local_labels:
        st = cells[l].get("full@full")
        if st and st["n_ok"]:
            v = "không kết luận"
            if st["acc"] <= 0.85 and st["ci_hi"] < 0.95:
                v = "ủng hộ giả thuyết quy mô (u sụp ở model nhỏ)"
            elif st["acc"] >= 0.95:
                v = "làm yếu giả thuyết quy mô"
            verdicts["HL1"][l] = {"acc": st["acc"], "ci": [st["ci_lo"], st["ci_hi"]], "verdict": v}
        verdicts["HL2"][l] = {}
        for bud in (4000, 8000):
            ka, kb = "bm25@%d" % bud, "full@%d" % bud
            if ka in cells[l] and kb in cells[l]:
                diff = cells[l][ka]["acc"] - cells[l][kb]["acc"]
                ca, cb = correct_ids(models[l][ka]), correct_ids(models[l][kb])
                p = mcnemar_exact(len(ca - cb), len(cb - ca))
                v = "chưa rõ"
                if diff >= 0.10 and p < 0.05:
                    v = "tái lập: chọn lọc thắng cắt"
                elif diff < 0 and p < 0.05:
                    v = "không tái lập"
                verdicts["HL2"][l][str(bud)] = {"diff_pp": round(diff * 100, 1), "p": p, "verdict": v}
        o, f = models[l].get("oracle", {}), models[l].get("full@full", {})
        ids = sorted({r["item_id"] for r in ok_recs(o)} & {r["item_id"] for r in ok_recs(f)})
        if ids:
            xs = [1 if i in correct_ids(o) else 0 for i in ids]
            ys = [1 if i in correct_ids(f) else 0 for i in ids]
            pt, lo, hi = bootstrap_diff(xs, ys)
            verdicts["HL3"][l] = {"oracle_minus_full_pp": round(pt * 100, 1),
                                  "ci_pp": [round(lo * 100, 1), round(hi * 100, 1)], "n": len(ids)}
        st = cells[l].get("full@full")
        if st and st["n_ok"]:
            n = st["n_ok"]
            verdicts["HL5"][l] = {
                "use_failure": st["error_classes"].get("use_failure", 0) / n,
                "distractor_confusion": st["error_classes"].get("distractor_confusion", 0) / n}
    if len(local_labels) >= 2:
        sizes = sorted(local_labels, key=lambda l: int("".join(ch for ch in l.split("-")[-1] if ch.isdigit()) or 0))
        wins = losses = ties = 0
        for ck in set(models[sizes[0]]) & set(models[sizes[-1]]):
            da = cells[sizes[0]][ck]["acc"]
            db = cells[sizes[-1]][ck]["acc"]
            if db > da + 1e-9:
                wins += 1
            elif da > db + 1e-9:
                losses += 1
            else:
                ties += 1
        verdicts["HL4"] = {"small": sizes[0], "large": sizes[-1],
                           "large_wins": wins, "small_wins": losses, "ties": ties}

    # ---- ghi file ----
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump({"cells": cells, "retention_vs_oracle": retention, "verdicts": verdicts,
                   "guards": meta["guards"], "runs": meta["runs"]}, fh, indent=2, ensure_ascii=False)
    with open(os.path.join(OUT, "cells.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["model", "cell", "n_ok", "n_error", "correct", "acc", "ci_lo", "ci_hi",
                    "n_truncated", "n_parse_error", "mean_input_tokens", "mean_context_recall", "R_vs_oracle"])
        for l in order:
            for ck in sorted(cells[l]):
                s = cells[l][ck]
                w.writerow([l, ck, s["n_ok"], s["n_error"], s["correct"],
                            "%.4f" % s["acc"], "%.4f" % s["ci_lo"], "%.4f" % s["ci_hi"],
                            s["n_truncated"], s["n_parse_error"],
                            "%.0f" % s["mean_input_tokens"] if s["mean_input_tokens"] else "",
                            "%.3f" % s["mean_context_recall"] if s["mean_context_recall"] is not None else "",
                            "%.3f" % retention[l][ck] if retention[l][ck] is not None else ""])
    with open(os.path.join(OUT, "mcnemar.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["model_a", "model_b", "cell", "a_only_correct", "b_only_correct", "p_exact"])
        for p in pairs:
            w.writerow([p["model_a"], p["model_b"], p["cell"], p["a_only"], p["b_only"], "%.4f" % p["p"]])

    # ---- SUMMARY.md ----
    L = []
    L.append("# SUMMARY — tính từ log thô (analysis/analyze.py)\n")
    L.append("Điểm chấm lại bằng scorer s2 từ raw_response. CI Wilson 95%. "
             "R = tỉ lệ giữ lại so với oracle. Cột `cắt` = số phản hồi chạm trần output.\n")
    for l in order:
        L.append("\n## %s\n" % l)
        L.append("| Ô | n | Đúng | Acc [CI 95%] | R | Cắt | Lỗi parse | Token vào TB |")
        L.append("|---|---|---|---|---|---|---|---|")
        for ck in sorted(cells[l]):
            s = cells[l][ck]
            r = retention[l][ck]
            L.append("| %s | %d | %d | %.1f%% [%.1f–%.1f] | %s | %d | %d | %s |" % (
                ck, s["n_ok"], s["correct"], s["acc"] * 100, s["ci_lo"] * 100, s["ci_hi"] * 100,
                "%.0f%%" % (r * 100) if r is not None else "—",
                s["n_truncated"], s["n_parse_error"],
                "%.0f" % s["mean_input_tokens"] if s["mean_input_tokens"] else "—"))
    L.append("\n## Kiểm định theo RUNPLAN\n")
    L.append("```json\n%s\n```" % json.dumps(verdicts, indent=2, ensure_ascii=False))
    L.append("\n## Cảnh báo nhiễu (guards)\n")
    if meta["guards"]:
        L.extend("- " + g for g in meta["guards"][:50])
        L.append("\nTổng: %d cảnh báo." % len(meta["guards"]))
    else:
        L.append("Không có cảnh báo nào (không cắt âm thầm, không rò thinking, không bão hoà cửa sổ).")
    L.append("\n## Các lượt đã đọc\n")
    L.extend("- %s (%d bản ghi)" % (r["dir"], r["n_records"]) for r in meta["runs"])
    with open(os.path.join(OUT, "SUMMARY.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("đã ghi:", OUT)
    print("models:", ", ".join(order))
    if meta["guards"]:
        print("CẢNH BÁO: %d guard flags — xem SUMMARY.md" % len(meta["guards"]))


if __name__ == "__main__":
    main()