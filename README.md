# IT5440 — Chạy ccbench trên model cục bộ (đóng góp cho paper nhóm)

Chạy **cùng 64 câu hỏi repository frostline** của benchmark
[ccbench](https://github.com/tuannt2906/code-context-benchmark) (S3 trong
paper, hiện chỉ có Claude Haiku/Sonnet) trên **qwen2.5-coder:7b và
qwen3.5:9b** — đúng hai model mà báo cáo
[it5440-5kh-local-runs](https://github.com/infinityrbx/it5440-5kh-local-runs)
đã chạy trên D2/toolz. Mục tiêu: hoàn thành bảng chéo *cùng model × ba tác
vụ* và kiểm tra trực tiếp giả thuyết quy mô mô hình của paper (hướng phát
triển iii): khi cả repository nằm trong cửa sổ (a = 1), model nhỏ có giữ
được độ chính xác 98–100% như Claude, hay u sụp?

Kế hoạch thí nghiệm + giả thuyết đăng ký trước: **[RUNPLAN.md](RUNPLAN.md)**.

## Trạng thái

- [x] Nguyên liệu sẵn sàng: code ccbench (vendored, commit `cc3e4e6`) + adapter
      Ollama native + configs + hàng đợi chạy đêm + script phân tích.
- [ ] Chạy trên server GPU 24GB → xem **[SERVER_SETUP.md](SERVER_SETUP.md)**.
- [ ] Kết quả thô gửi về → `analysis/analyze.py` + `figures.py` → **[REPORT.md](REPORT.md)**.

## Cấu trúc

```
IT5440/
├── README.md            ← file này
├── RUNPLAN.md           ← kế hoạch + giả thuyết (cố định trước khi chạy)
├── SERVER_SETUP.md      ← từng bước chạy trên server Linux GPU
├── REPORT.md            ← báo cáo kết quả (điền sau khi có số liệu)
├── SOURCE.md            ← nguồn gốc code vendored + danh sách vá
├── run_queue.sh         ← hàng đợi chạy đêm, resume-safe
├── analysis/
│   ├── analyze.py       ← tính lại mọi bảng + kiểm định từ log thô (stdlib)
│   └── figures.py       ← vẽ hình (matplotlib)
└── ccbench/             ← bản sao đầy đủ ccbench (code + dữ liệu + kết quả Claude)
    ├── ccbench/providers/ollama_native.py   ← adapter MỚI cho Ollama
    ├── configs/local_smoke.json             ← 32 lượt kiểm tra
    ├── configs/local_qwen7b.json            ← 1.536 lượt
    ├── configs/local_qwen9b.json            ← 1.536 lượt
    ├── configs/local_qwen14b.json           ← tuỳ chọn, điểm kích thước thứ 3
    └── results/                             ← kết quả Claude đã công bố + kết quả cục bộ (sau khi chạy)
```

## Quy trình tổng thể

```
máy này (workspace)                    server GPU 24GB
─────────────────────                  ───────────────────────────────
chuẩn bị code + config + kế hoạch
        │ push GitHub
        └──────────────────────────►   git clone
                                       cài Ollama, pull model (SERVER_SETUP.md)
                                       bash run_queue.sh  (smoke → 7b → 9b, qua đêm)
        │ kết quả thô (.tgz)           tar ccbench/results/local_* logs/
        ◄──────────────────────────┘
xếp kết quả vào repo
python3 analysis/analyze.py
python3 analysis/figures.py
điền REPORT.md → push GitHub = repo báo cáo trọn vẹn
```

## Kiểm tra nhanh (không cần GPU, không cần model)

```bash
cd ccbench
python3 -m unittest discover -s tests      # 26 test
python3 -m ccbench build-dataset --check   # SHA ground truth phải khớp
python3 -m ccbench context-stats           # context recall offline
```

## Ghi chú thiết kế quan trọng

- **Ollama native `/api/chat`**, không dùng `/v1`: endpoint OpenAI-compatible
  bỏ qua `think: false` với qwen3.5 → model đốt ngân sách output để nghĩ và
  trả lời rỗng (bài học từ repo 5-KH). Adapter mới gửi `think: false` đúng chỗ.
- **`num_ctx = 32768`** cho mọi điều kiện: repo đầy đủ ~26K token; Ollama cắt
  âm thầm prompt dài hơn cửa sổ mặc định — phải đặt tường minh.
- **Temperature 0, seed 0, output 1024, 1 truy vấn/lần** — khớp thiết lập
  Claude đã công bố để so sánh cùng thước đo.
- ccbench **không bao giờ ghi đè** kết quả và **resume** được: mọi lượt đã
  `ok` bị bỏ qua khi chạy lại; điểm luôn chấm lại từ phản hồi thô (scorer s2).