# SOURCE — Nguồn gốc và các thay đổi so với bản gốc

## Code vendored

| Thành phần | Nguồn | Commit |
|---|---|---|
| `ccbench/` (toàn bộ code, dữ liệu frostline v1, kết quả Claude đã công bố) | https://github.com/tuannt2906/code-context-benchmark | `cc3e4e672664a845cccfd832efc3e21f42a16a3b` |
| Mẫu adapter Ollama native (tham khảo, không copy code) | https://github.com/infinityrbx/it5440-5kh-local-runs | `90e02bb5d3bcb2ee547481eb0faf9ace6d182273` |

Kết quả Claude giữ nguyên trong `ccbench/results/` (main_haiku, main_sonnet,
oracle_trace_*, repeat_haiku, combined_v1-20261113) để so sánh trực tiếp trên
cùng tập câu mà không cần tải lại.

## Thay đổi so với ccbench gốc (toàn bộ là THÊM MỚI, không sửa logic cũ)

1. **Thêm** `ccbench/ccbench/providers/ollama_native.py` — adapter gọi Ollama
   native `/api/chat`: `think` (tuỳ chọn theo model), `options.num_ctx`,
   `options.num_predict`, `options.seed`, `keep_alive`; ghi `done_reason`,
   `thinking_chars`, `prompt_eval_count`, `eval_count` vào mỗi bản ghi.
2. **Sửa tối thiểu** `ccbench/ccbench/providers/__init__.py` — đăng ký
   `"ollama_native"` vào PROVIDERS (2 dòng import + 1 dòng dict).
3. **Thêm** `ccbench/configs/local_smoke.json`, `local_qwen7b.json`,
   `local_qwen9b.json`, `local_qwen14b.json`.

Không thay đổi: prompt (p1), scorer (s2), dataset (v1, SHA
`5e550060fea81413`), fixture (`8da947b42b62564d`), runner, chiến lược dựng
ngữ cảnh, prereg.json. Nhờ đó kết quả cục bộ so sánh được trực tiếp với kết
quả Claude đã công bố.

Kiểm chứng sau vá (đã chạy trên máy chuẩn bị, Python 3.14):
- `python3 -m unittest discover -s tests` → 26 test OK
- `python3 -m ccbench build-dataset --check` → "ground truth reproduced exactly"
- `python3 -m ccbench run configs/demo_mock.json` → 396/396 ok (đã xoá kết quả demo)
- Adapter mới test với server giả lập: đúng payload `/api/chat`, `think:false`
  chỉ gửi khi cấu hình, lỗi 404 → fatal không retry.

## Giấy phép

ccbench gốc: MIT (giữ nguyên `ccbench/LICENSE`). Phần thêm mới của IT5440
dùng cùng giấy phép MIT.