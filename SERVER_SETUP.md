# Hướng dẫn chạy trên server GPU (Linux, 24 GB VRAM)

Toàn bộ lệnh dưới đây chạy **trên server**, tại thư mục làm việc
`/home/vpcuser/AI_LAB/itadoritran`. Giả định: Ubuntu/Debian, GPU NVIDIA 24 GB
(đã có driver), Python ≥ 3.9. Repo này chỉ cần **thư viện chuẩn Python** —
không pip install gì cả.

Ước tính thời gian: smoke ~5 phút; mỗi model ~4–7 giờ; cả hàng đợi 7b + 9b
~8–14 giờ (chạy qua đêm). Chi tiết trong [RUNPLAN.md](RUNPLAN.md).

---

## Bước 0 — Kiểm tra máy

```bash
nvidia-smi                 # phải thấy GPU 24GB, driver hoạt động
python3 --version          # >= 3.9
df -h /home/vpcuser        # cần ~20GB trống (model 7b ~4.7GB, 9b ~6GB, 14b ~9GB)
```

## Bước 1 — Cài Ollama

**Cách A (có sudo):**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Cách B (không sudo, cài vào thư mục riêng):**

Ollama bản mới phát hành dạng `.tar.zst` (cần `zstd`). Các URL `.tgz` cũ
không còn tồn tại. Cài zstd theo distro:

- **CentOS Stream / RHEL 9** (máy celldata): `sudo dnf install -y zstd`
- Ubuntu/Debian: `sudo apt-get install -y zstd`
- Không có sudo: lấy gói đóng gói sẵn từ conda-forge (`.tar.bz2`, giải nén
  bằng tar thường, không cài vào hệ thống):

```bash
cd ~/ollama
curl -fsSL -o zstd-pkg.tar.bz2 https://conda.anaconda.org/conda-forge/linux-64/zstd-1.5.2-h6239696_4.tar.bz2
mkdir -p zstd-local
tar xjf zstd-pkg.tar.bz2 -C zstd-local   # thiếu bzip2 thì dùng python3:
# python3 -c "import bz2,sys; sys.stdout.buffer.write(bz2.open(sys.argv[1],'rb').read())" zstd-pkg.tar.bz2 | tar xf - -C zstd-local
[ -e zstd-local/lib/libzstd.so.1 ] || ln -s libzstd.so.1.5.2 zstd-local/lib/libzstd.so.1
export PATH="$HOME/ollama/zstd-local/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/ollama/zstd-local/lib:${LD_LIBRARY_PATH:-}"
```

```bash
mkdir -p ~/ollama && cd ~/ollama
curl -fsSL -o ollama.tar.zst https://ollama.com/download/ollama-linux-amd64.tar.zst
zstd -dc ollama.tar.zst | tar xf -
export PATH=$HOME/ollama/bin:$PATH   # thêm vào ~/.bashrc hoặc ~/.zshrc
# chạy server (để cửa sổ này mở, hoặc dùng tmux/nohup):
CUDA_VISIBLE_DEVICES=0 OLLAMA_FLASH_ATTENTION=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
  ollama serve
```

Máy có nhiều GPU (celldata: 2× L4 24GB): `CUDA_VISIBLE_DEVICES=0` ghim Ollama
vào GPU 0, để GPU 1 trống. Muốn chạy song song hai model trên hai GPU thì
mở hai server Ollama cổng khác nhau — hỏi người chuẩn bị repo, không tự làm.

Với cách A, đặt các biến môi trường trên cho service rồi khởi động lại:

```bash
sudo systemctl edit ollama
# thêm vào phần [Service]:
#   Environment="OLLAMA_FLASH_ATTENTION=1"
#   Environment="OLLAMA_NUM_PARALLEL=1"
#   Environment="OLLAMA_MAX_LOADED_MODELS=1"
sudo systemctl restart ollama
```

Ý nghĩa: `NUM_PARALLEL=1` — mỗi lúc một truy vấn (khớp thiết kế thí nghiệm,
temperature 0); `MAX_LOADED_MODELS=1` — chỉ giữ 1 model trong VRAM;
`FLASH_ATTENTION=1` — giảm bộ nhớ KV cache cho cửa sổ 32K.

**Bẫy trên máy celldata:** biến môi trường đặt sẵn `OLLAMA_MODELS=/dev/ollama/models`
làm server chết ngay khi khởi động (`mkdir /dev/ollama: permission denied`).
Phải đè bằng thư mục của mình trong lệnh serve:

```bash
CUDA_VISIBLE_DEVICES=0 OLLAMA_MODELS=$HOME/ollama/models \
  OLLAMA_FLASH_ATTENTION=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 ollama serve
```

và thêm `export OLLAMA_MODELS=$HOME/ollama/models` vào `~/.bashrc`.
Model sẽ nằm ở `~/ollama/models` (ổ `/`, kiểm tra `df -h /` còn trống ≥ 25GB).

Kiểm tra server sống:

```bash
curl -s http://localhost:11434/api/tags
```

## Bước 2 — Tải model

```bash
ollama pull qwen2.5-coder:7b
ollama pull qwen3.5:9b
# tuỳ chọn (điểm kích thước thứ ba, chỉ chạy khi có thời gian):
ollama pull qwen2.5-coder:14b
```

Kiểm tra model chạy **trên GPU** (không phải CPU):

```bash
ollama run qwen2.5-coder:7b "Reply with the single word: ok" --verbose
ollama ps    # cột PROCESSOR phải là 100% GPU
```

Nếu thấy CPU: driver/CUDA chưa nhận — kiểm tra `nvidia-smi`, hoặc Ollama bản
quá cũ. Đừng chạy hàng đợi khi model còn nằm trên CPU (chậm hơn ~20 lần).

## Bước 3 — Clone repo và kiểm tra offline

```bash
cd /home/vpcuser/AI_LAB/itadoritran
git clone https://github.com/garnalam/IT5440.git
cd IT5440/ccbench

python3 -m unittest discover -s tests        # 26 test phải OK
python3 -m ccbench build-dataset --check     # phải in "ground truth reproduced exactly"
python3 -m ccbench context-stats             # bảng context recall offline, không gọi model
```

Hai lệnh đầu xác nhận code và dữ liệu nguyên vẹn sau khi clone (SHA dataset
`5e550060fea81413`, fixture `8da947b42b62564d`). Nếu `build-dataset --check`
báo MISMATCH: dừng lại, báo về — đừng chạy.

## Bước 4 — Smoke test (bắt buộc, ~5 phút)

```bash
cd /home/vpcuser/AI_LAB/itadoritran/IT5440
bash run_queue.sh local_smoke
```

32 lượt gọi (2 model × 4 điều kiện × 4 câu). Hàng đợi tự kiểm tra: không có
lượt nào lỗi, không trả lời rỗng, không rò thinking. Kết quả mong đợi:
`smoke: 32 records, 0 bad, 0 with thinking leaked`.

Xem tận mắt một phản hồi:

```bash
cd ccbench
python3 -m ccbench show-context L3-03 bm25 --budget 4000 --prompt | head -30
tail -1 results/local_smoke-*/results.jsonl | python3 -m json.tool | head -40
```

Nếu smoke lỗi: xem `logs/local_smoke.log`. Lỗi thường gặp:

| Triệu chứng | Nguyên nhân | Cách xử |
|---|---|---|
| `model not found` (404) | chưa pull đúng tag | `ollama pull <tag>` |
| trả lời rỗng, `thinking_chars > 0` | thinking chưa tắt | chỉ xảy ra nếu dùng nhầm `/v1`; adapter ở repo này đã dùng `/api/chat` native — báo về nếu gặp |
| `done_reason: length` nhiều | output chạm trần 1024 | ghi nhận, chưa cần sửa (xem RUNPLAN) |
| chậm bất thường (>60s/câu ngắn) | model trên CPU | `ollama ps`, xem Bước 2 |

## Bước 5 — Chạy qua đêm

```bash
cd /home/vpcuser/AI_LAB/itadoritran/IT5440
nohup bash run_queue.sh > logs/queue.out 2>&1 &
echo $!    # ghi lại PID
```

Thứ tự: smoke (chạy lại, các lượt đã xong được bỏ qua) → `local_qwen7b`
(1.536 lượt) → `local_qwen9b` (1.536 lượt).

Theo dõi:

```bash
tail -f logs/queue.out              # tiến độ tổng
tail -f logs/local_qwen7b.log       # từng model
ollama ps                           # VRAM / GPU
watch -n 60 'wc -l ccbench/results/local_qwen7b-*/results.jsonl'
```

**Mất kết nối SSH / server reboot / bị kill:** không sao. Chạy lại đúng lệnh
trên — ccbench bỏ qua mọi lượt đã ghi `status ok` và chạy tiếp phần còn lại
(resume). Không bao giờ ghi đè kết quả cũ.

Tuỳ chọn điểm kích thước thứ ba (sau khi hàng đợi chính xong):

```bash
nohup bash run_queue.sh local_qwen14b > logs/queue14.out 2>&1 &
```

## Bước 6 — Gom kết quả gửi về

Sau khi hàng đợi xong (hoặc giữa chừng cũng gửi được — bản gửi về phải kèm
đúng các thư mục này):

```bash
cd /home/vpcuser/AI_LAB/itadoritran/IT5440
tar czf ~/it5440-results-$(date +%Y%m%d).tgz \
  ccbench/results/local_smoke-* \
  ccbench/results/local_qwen7b-* \
  ccbench/results/local_qwen9b-* \
  logs/
# nếu có chạy 14b thì thêm ccbench/results/local_qwen14b-*
ls -la ~/it5440-results-*.tgz
```

Gửi file `.tgz` đó về. Mỗi thư mục kết quả chứa `results.jsonl` (toàn bộ phản
hồi thô + điểm), `config.json` (cấu hình + provenance: SHA dataset, tham số
thật của provider, phiên bản Python/nền tảng) và `report/` (bảng + hình do
ccbench tự sinh). Phần phân tích chéo với Claude và báo cáo cuối sẽ làm từ
các file thô này.

**Không commit/không gửi:** `.env` (không cần tạo), file chứa đường dẫn máy
cục bộ ngoài `logs/` đã gom ở trên.

## Ghi chú kỹ thuật (đã xử lý sẵn trong repo, không cần làm gì)

- **Cửa sổ ngữ cảnh 32.768 token** cho mọi điều kiện (`num_ctx` trong
  config). Repository đầy đủ ~26K token ước lượng; Ollama mặc định cửa sổ
  nhỏ và **cắt âm thầm** prompt dài — đặt 32K để không điều kiện nào bị cắt.
  Script phân tích sẽ đối chiếu `prompt_eval_count` thật với ước lượng để
  phát hiện nếu có cắt.
- **`think: false` qua API native `/api/chat`** cho qwen3.5 (endpoint `/v1`
  bỏ qua tham số này — bài học từ repo it5440-5kh-local-runs). qwen2.5-coder
  không có thinking nên không gửi tham số.
- **Temperature 0, seed 0, 1 truy vấn/lần, max output 1024** — khớp đúng
  thiết lập các lượt chạy Claude đã công bố để so sánh được.
- Lượng tử hoá: Ollama mặc định Q4_K_M (cùng mức lượng tử hoá với lượt 7B
  trong paper). Ghi trong báo cáo như một hạn chế.