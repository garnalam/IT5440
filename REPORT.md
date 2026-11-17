# REPORT — ccbench trên model cục bộ (qwen2.5-coder:7b, qwen3.5:9b)

**Trạng thái: CHỜ KẾT QUẢ.** Khung báo cáo lập sẵn ngày 17/11/2026; mọi ô
`[CHỜ]` sẽ điền từ `analysis/output/SUMMARY.md` sau khi có log thô từ server.
Kế hoạch và ngưỡng kiểm định cố định trước khi chạy: [RUNPLAN.md](RUNPLAN.md).

## Tóm tắt

[CHỜ — 3–5 câu: phát hiện chính, chiều hướng so với Claude, kết luận về giả
thuyết quy mô.]

## 1. Thiết lập

- Benchmark: ccbench (frostline v1, 64 câu L1–L5, ground truth bằng thực thi
  code; SHA `5e550060fea81413`).
- Model: qwen2.5-coder:7b, qwen3.5:9b [, qwen2.5-coder:14b nếu chạy] — Ollama,
  lượng tử hoá Q4_K_M, temperature 0, seed 0, output tối đa 1024 token, cửa sổ
  32.768 token, 1 truy vấn/lần.
- Phần cứng: [CHỜ — tên GPU, driver, phiên bản Ollama, Python; lấy từ
  config.json provenance của các lượt chạy].
- 24 điều kiện × 64 câu = 1.536 lượt/model. Thời gian chạy thực tế: [CHỜ].
- Đối chiếu: Claude Haiku 5.5 / Sonnet 5.5 (S3 đã công bố, cùng tập câu).

## 2. Kết quả chính

### 2.1 Cả repository trong cửa sổ (a = 1) — HL1

| Model | Acc cả-repo [CI 95%] | So với Claude | Kết luận |
|---|---|---|---|
| qwen2.5-coder:7b | [CHỜ] | 98,4% (Haiku) | [CHỜ] |
| qwen3.5:9b | [CHỜ] | 100% (Sonnet) | [CHỜ] |
| [14b nếu có] | [CHỜ] | | |

### 2.2 Chọn lọc so với cắt ở cùng budget — HL2

[CHỜ — bảng Acc(bm25) − Acc(full cắt) tại 2K/4K/8K/16K từng model, McNemar;
so với mức +33–50 đ.p.t. của Claude.]

### 2.3 Giá của nhiễu và trần trên — HL3

[CHỜ — oracle − cả-repo từng model + CI bootstrap; oracle_trace so với oracle
(V4: oracle viết tay không phải trần trên).]

### 2.4 Đơn điệu theo kích thước — HL4

[CHỜ — số ô 9b thắng / thua / hoà 7b trên cùng lưới; 14b nếu có.]

### 2.5 Phân rã lỗi — HL5

[CHỜ — tỉ lệ use_failure / distractor_confusion ở cả-repo từng model so với
Claude.]

### 2.6 Theo mức câu hỏi

[CHỜ — hình fig3_by_level.png; nhận xét L3–L5.]

## 3. Đối chiếu chéo ba tác vụ (cùng model)

| | D2 tổng hợp (5-KH) | toolz (5-KH) | ccbench (báo cáo này) |
|---|---|---|---|
| qwen2.5-coder:7b | sụp còn 6–28% có filler | xu hướng sụt, p=0,07 | [CHỜ] |
| qwen3.5:9b | chỉ sụt ở giữa tại 16k | không sụt (D=−0,04) | [CHỜ] |

[CHỜ — diễn giải: kết quả ccbench củng cố hay làm yếu giả thuyết quy mô của
paper (Mục V.B)? Lưu ý khác hạ tầng Q4 cục bộ vs API, khác loại nhiễu.]

## 4. Kiểm soát nhiễu và hạn chế

- Cắt output ở 1024: [CHỜ — số lượt done_reason=length theo model × ô].
- Rò thinking: [CHỜ — phải bằng 0; smoke đã chặn].
- Cắt âm thầm prompt: [CHỜ — guard trong analyze.py; input thật ô cả-repo].
- Một seed, một lần chạy, Q4_K_M, một GPU — CI theo câu, không theo lần chạy.
- So sánh chéo model là mô tả (khác hạ tầng), không phải kiểm định nhân quả.
- [CHỜ — các hạn chế phát sinh khi chạy thật.]

## 5. Tái lập

```bash
# trên server GPU (chi tiết: SERVER_SETUP.md)
bash run_queue.sh
# tính lại mọi số liệu từ log thô
python3 analysis/analyze.py && python3 analysis/figures.py
```

Kết quả thô: `ccbench/results/local_*/results.jsonl` (phản hồi gốc + điểm +
provenance). Mọi bảng trong báo cáo này tính lại được từ các file đó.