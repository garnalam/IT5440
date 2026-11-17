# RUNPLAN — Kế hoạch thí nghiệm ccbench trên model cục bộ

Ngày lập kế hoạch: 17/11/2026 (các ngưỡng dưới đây cố định **trước khi chạy**).

## 1. Mục đích — lấp đúng chỗ trống của paper

Paper hiện có: S1/P (7B, mã tổng hợp + toolz), S2 (27B/API, toolz), S3
(Claude Haiku/Sonnet, repository frostline trong ccbench). So sánh chéo giữa
hai nhóm model bị nhiễu: khác model **và** khác tác vụ **và** khác loại nhiễu
(paper, Mục V.B và hướng phát triển iii).

Thí nghiệm này chạy **cùng 64 câu hỏi frostline, cùng lưới điều kiện** của S3
nhưng trên **qwen2.5-coder:7b và qwen3.5:9b** — đúng hai model của báo cáo
5-KH chạy cục bộ. Kết quả tạo thành bảng chéo hoàn chỉnh:

| | D2 (tổng hợp) | toolz (code thật) | ccbench (repository) |
|---|---|---|---|
| qwen2.5-coder:7b | 5-KH ✓ | 5-KH ✓ | **thí nghiệm này** |
| qwen3.5:9b | 5-KH ✓ | 5-KH ✓ | **thí nghiệm này** |
| Claude Haiku/Sonnet | — | — | S3 ✓ (đã công bố) |

Nếu model nhỏ sụt mạnh ở điều kiện cả-repository (nơi Claude đạt 98–100%)
trong khi bằng chứng có mặt đầy đủ (a = 1), đó là bằng chứng trực tiếp cho
giả thuyết quy mô: **u (khả năng sử dụng) sụp ở model nhỏ**, độc lập với loại
nhiễu. Nếu không sụt, giả thuyết quy mô yếu đi — kết quả trung thực vẫn có
giá trị công bố.

## 2. Thiết kế

- **Dữ liệu**: frostline v1, 64 câu L1–L5, ground truth bằng thực thi code.
  SHA `5e550060fea81413`, fixture `8da947b42b62564d` (kiểm bằng
  `build-dataset --check` trước khi chạy).
- **Model**: `qwen2.5-coder:7b`, `qwen3.5:9b` (Ollama, Q4_K_M); tuỳ chọn
  `qwen2.5-coder:14b` làm điểm kích thước thứ ba.
- **24 điều kiện** (giống lưới `free_qwen7b.json` đã chuẩn bị trong ccbench,
  thêm `oracle_trace`):

| Chiến lược | Budget (token ước lượng) | Số ô |
|---|---|---|
| none (không code) | — | 1 |
| oracle (chỉ unit vàng) | — | 1 |
| oracle_trace (vàng + vết thực thi) | — | 1 |
| full (cả repo / cắt từ đầu) | null, 2K, 4K, 8K, 16K | 5 |
| fixed (file cố định) | 2K, 4K, 8K, 16K | 4 |
| bm25 | 2K, 4K, 8K, 16K | 4 |
| bm25_namegraph | 2K, 4K, 8K, 16K | 4 |
| dgc | 2K, 4K, 8K, 16K | 4 |

- **Số lượt gọi**: 24 × 64 = **1.536/model**; 2 model = 3.072; +14b = 4.608.
- **Tham số**: temperature 0, seed 0, concurrency 1, max output **1024**
  (khớp lượt Claude đã công bố), cửa sổ `num_ctx` **32.768** cho mọi ô.
- **Khác biệt hạ tầng so với S3** (ghi nhận, không che giấu): Ollama cục bộ
  Q4_K_M trên GPU 24GB thay vì Claude API; ước lượng budget bằng kí tự
  (2,35 char/token, hiệu chuẩn trên Claude) nên số token thật của Qwen lệch
  đôi chút — cả hai số luôn được ghi cạnh nhau trong kết quả.

## 3. Giả thuyết đăng ký trước (ngưỡng cố định trước khi chạy)

Kí hiệu: Acc(strategy, budget) theo model; so sánh ghép cặp McNemar chính
xác trên cùng 64 câu; CI Wilson 95%.

- **HL1 — u sụp ở model nhỏ khi a = 1.** Ở `full(null)` (cả repo 26K, mọi
  bằng chứng có mặt): ủng hộ giả thuyết quy mô nếu Acc ≤ 85% **và** cận trên
  CI < 95% (Claude: 98,4% / 100%). Làm yếu giả thuyết nếu Acc ≥ 95%. Ở giữa:
  không kết luận.
- **HL2 — chọn lọc thắng cắt ở model nhỏ (tái lập phát hiện chính của S3).**
  Với mỗi model, tại 4K và 8K: Acc(bm25) − Acc(full cắt) ≥ +10 đ.p.t. và
  McNemar p < 0,05 → tái lập; nếu hiệu số âm có ý nghĩa → không tái lập
  (cũng là kết quả đáng báo cáo). Ngưỡng 10 đ.p.t. lấy từ prereg gốc của
  ccbench (`h1a_support`).
- **HL3 — giá của nhiễu.** Acc(oracle) − Acc(full null): ở Claude khoảng
  0–2 đ.p.t. Dự đoán ở model nhỏ chênh lệch lớn hơn (nhiễu làm giảm u); báo cáo hiệu
  số + CI bootstrap, không đặt ngưỡng cứng.
- **HL4 — đơn điệu theo kích thước.** Trên cùng tập câu và lưới: Acc(9b) ≥
  Acc(7b) ở đa số ô (dấu kiểm định McNemar từng ô, tổng hợp bằng số ô thắng /
  thua / hoà). Nếu chạy 14b: kì vọng 14b ≥ 9b cùng chiều.
- **HL5 — phân rã lỗi.** Ở `full(null)` mọi câu sai đều là `use_failure`
  hoặc `distractor_confusion` theo cấu tạo (a = 1). So sánh tỉ lệ
  distractor_confusion với Claude (bẫy hàm trùng tên): model nhỏ có thể mắc
  bẫy nhiều hơn — thăm dò, không ngưỡng.

**Không kiểm định ở thí nghiệm này**: hiệu ứng vị trí (ccbench không thao
tác vị trí bằng chứng — phần đó thuộc D2/toolz của 5-KH). So sánh chéo
model-kích-thước là **mô tả** khi khác hạ tầng (Q4 cục bộ vs API), đúng cách
paper đã xử lý so sánh S1/P với S2.

## 4. Nhiễu cần ghi nhận (rút từ báo cáo 5-KH)

1. **Cắt output ở 1024 token**: đếm `done_reason = "length"` theo model ×
   điều kiện. Nếu > 5% ở ô nào, ô đó bị giới hạn trần kéo điểm — ghi trong
   báo cáo; cân nhắc chạy lại ô đó với trần 2048 (config riêng, tên riêng)
   và báo cả hai.
2. **Rò thinking** (qwen3.5): smoke test chặn ngay nếu `thinking_chars > 0`.
3. **Cắt âm thầm prompt dài**: `num_ctx = 32768` > mọi prompt (~26K + lề).
   Script phân tích đối chiếu `prompt_eval_count` thật với ước lượng; cờ
   nếu ô `full(null)` có input < 20.000 token thật.
4. **Lỗi bộ chấm**: luôn chấm lại từ `raw_response` bằng scorer s2 hiện hành
   (ccbench làm sẵn khi đọc kết quả; `analysis/analyze.py` cũng vậy).
5. Một seed, một lần chạy, temperature 0 — không có phương sai lặp; khoảng
   tin cậy theo câu (Wilson/bootstrap), không theo lần chạy.

## 5. Thời gian ước tính (GPU 24GB, Q4)

Đo thật ở smoke rồi ngoại suy; ước tính ban đầu:

| Model | Prefill | Decode | TB/lượt | 1.536 lượt |
|---|---|---|---|---|
| 7b | ~1–2K tok/s | ~45–60 tok/s | ~8–12 s | ~3,5–5 giờ |
| 9b | ~0,8–1,5K tok/s | ~35–50 tok/s | ~10–15 s | ~4,5–6,5 giờ |
| 14b (tuỳ chọn) | ~0,6–1K tok/s | ~25–35 tok/s | ~15–22 s | ~6,5–9,5 giờ |

Ô `full(null)` chiếm phần lớn thời gian prefill (26K token/lượt). Tổng hàng
đợi chính: **~8–12 giờ** — vừa một đêm. VRAM: 7b ~7GB, 9b ~9GB, 14b ~15GB
(weights + KV 32K) — tất cả vừa 24GB, không cần offload.

## 6. Dòng đời kết quả

```
server: run_queue.sh → ccbench/results/local_*/results.jsonl (thô)
  → gửi .tgz về → xếp vào repo này
  → python3 analysis/analyze.py   (bảng + kiểm định từ log thô)
  → python3 analysis/figures.py   (hình, cần matplotlib)
  → REPORT.md hoàn chỉnh → push GitHub
```