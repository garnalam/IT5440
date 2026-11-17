#!/usr/bin/env python3
"""IT5440 — vẽ hình từ analysis/output/summary.json (chạy analyze.py trước).

Cần matplotlib (pip install matplotlib). Không có matplotlib thì bỏ qua nhẹ nhàng.
    python3 analysis/figures.py
Ghi PNG vào analysis/output/.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "analysis", "output")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib chưa cài — bỏ qua vẽ hình (pip install matplotlib). Số liệu vẫn có trong SUMMARY.md.")
    sys.exit(0)

COLORS = {"qwen2.5-coder-7b": "#d62728", "qwen3.5-9b": "#ff7f0e", "qwen2.5-coder-14b": "#9467bd",
          "claude-haiku-5-5": "#1f77b4", "claude-sonnet-5-5": "#2ca02c"}
BUDGETS = [2000, 4000, 8000, 16000]


def load():
    with open(os.path.join(OUT, "summary.json"), encoding="utf-8") as fh:
        return json.load(fh)


def label_color(l):
    return COLORS.get(l, "#7f7f7f")


def fig_budget(cells):
    strategies = ["full", "fixed", "bm25", "bm25_namegraph", "dgc"]
    fig, axes = plt.subplots(1, len(strategies), figsize=(20, 4), sharey=True)
    for ax, s in zip(axes, strategies):
        for l in cells:
            xs, ys, los, his = [], [], [], []
            for b in BUDGETS:
                ck = "%s@%d" % (s, b)
                if ck in cells[l] and cells[l][ck]["n_ok"]:
                    c = cells[l][ck]
                    xs.append(b)
                    ys.append(c["acc"] * 100)
                    los.append((c["acc"] - c["ci_lo"]) * 100)
                    his.append((c["ci_hi"] - c["acc"]) * 100)
            if xs:
                ax.errorbar(xs, ys, yerr=[los, his], marker="o", capsize=3,
                            label=l, color=label_color(l))
        ax.set_xscale("log", base=2)
        ax.set_xticks(BUDGETS)
        ax.set_xticklabels(["2K", "4K", "8K", "16K"])
        ax.set_title(s)
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Độ chính xác (%) [Wilson 95%]")
    axes[-1].legend(fontsize=8, loc="lower right")
    fig.suptitle("ccbench: độ chính xác theo budget — model cục bộ vs Claude (cùng 64 câu frostline)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig1_accuracy_vs_budget.png"), dpi=150)
    plt.close(fig)


def fig_reference(cells):
    refs = ["none", "oracle", "oracle_trace", "full@full"]
    names = ["không code", "oracle", "oracle_trace", "cả repo (26K)"]
    models = list(cells)
    fig, ax = plt.subplots(figsize=(10, 5))
    w = 0.8 / max(1, len(models))
    for i, l in enumerate(models):
        xs, ys, los, his = [], [], [], []
        for j, ck in enumerate(refs):
            if ck in cells[l] and cells[l][ck]["n_ok"]:
                c = cells[l][ck]
                xs.append(j + i * w - 0.4 + w / 2)
                ys.append(c["acc"] * 100)
                los.append((c["acc"] - c["ci_lo"]) * 100)
                his.append((c["ci_hi"] - c["acc"]) * 100)
        if xs:
            ax.bar(xs, ys, width=w, yerr=[los, his], capsize=3, label=l, color=label_color(l))
    ax.set_xticks(range(len(refs)))
    ax.set_xticklabels(names)
    ax.set_ylabel("Độ chính xác (%) [Wilson 95%]")
    ax.set_ylim(0, 100)
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8)
    ax.set_title("Điều kiện tham chiếu: cả repository (a=1) so với oracle — HL1/HL3")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig2_reference_conditions.png"), dpi=150)
    plt.close(fig)


def fig_levels(cells):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, ck in zip(axes, ["full@full", "bm25@4000"]):
        for l in cells:
            if ck not in cells[l]:
                continue
            lv = cells[l][ck]["acc_by_level"]
            xs = list(range(5))
            ys = [lv[k][0] * 100 for k in ("L1", "L2", "L3", "L4", "L5")]
            ax.plot(xs, ys, marker="o", label=l, color=label_color(l))
        ax.set_xticks(range(5))
        ax.set_xticklabels(["L1", "L2", "L3", "L4", "L5"])
        ax.set_title(ck)
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Độ chính xác (%)")
    axes[-1].legend(fontsize=8)
    fig.suptitle("Độ chính xác theo mức câu hỏi")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig3_by_level.png"), dpi=150)
    plt.close(fig)


def main():
    if not os.path.isfile(os.path.join(OUT, "summary.json")):
        print("Chưa có analysis/output/summary.json — chạy analysis/analyze.py trước.")
        return
    data = load()
    cells = data["cells"]
    fig_budget(cells)
    fig_reference(cells)
    fig_levels(cells)
    print("đã ghi 3 hình PNG vào", OUT)


if __name__ == "__main__":
    main()