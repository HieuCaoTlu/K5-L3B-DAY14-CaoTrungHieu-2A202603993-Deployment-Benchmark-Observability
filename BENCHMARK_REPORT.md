# Benchmark & Observability Report — Day 14

**Họ tên:** Cao Trung Hiếu - 2A202603993
**Ngày chạy:** 26/11/2026
**Môi trường:** Windows 11 + WSL2 Ubuntu 26.04 (16 CPU, 7 GB RAM), Python 3.14, Docker 29.9.3

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Mock LLM mất ~190 ms (p50), 500 ms vẫn đủ nhanh cho chat và để dư cho lúc tải cao (c=100 p95 = 398 ms) |
| Error rate `/ask` | < 2 % | Mock LLM có ~1% lỗi 503 upstream, 2% cho phép lỗi ngẫu nhiên nhưng bắt được khi upstream hỏng thật |
| Accuracy trên golden dataset | ≥ 85 % | Ngưỡng của quality gate trong CI; dưới mức này không cho merge |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.04 | 189.5 | 219.8 | 1705.9 | 1.67% | ✅ PASS |
| 10 | 34.35 | 188.4 | 223.5 | 1700.6 | 0.67% | ✅ PASS |
| 50 | 114.05 | 196.1 | 239.3 | 1691.6 | 1.00% | ✅ PASS |
| 100 | 130.36 | 207.7 | 398.0 | 1780.1 | 1.33% | ✅ PASS |

**Nhận xét:** RPS tăng gần tuyến tính từ c=1 đến c=10 (4 → 34) vì agent là async, mỗi request chủ yếu chờ LLM nên chạy song song được. Từ c=50 lên c=100 RPS chỉ tăng 114 → 130 và p95 tăng 239 → 398 ms: 1 process uvicorn bắt đầu bão hoà (event loop, CPU cho serialize/metrics), request phải xếp hàng.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 190.1 | 219.2 | 225.1 |
| 0.03 (mặc định) | 220.5 | 221.3 | 1695.1 |
| 0.1 | 324.7 | 1688.1 | 1713.1 |

**Nhận xét:** p99 nhạy nhất: chỉ 3% request chậm đã đẩy p99 từ 225 lên 1695 ms trong khi avg chỉ tăng 190 → 220 ms. Khi tỉ lệ chậm lên 10% (vượt 5%) thì cả p95 cũng nhảy lên ~1.7 s và SLO p95 FAIL. Average bị các request nhanh "kéo xuống" nên che mất trải nghiệm tệ của một phần user, vì vậy SLO đặt theo p95/p99.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57.2 | 108.7 | 113.8 |
| Tổng cost (USD) | 0.000406 | 0.000756 | 0.000792 |
| Cost / câu đúng (USD) | 0.00040575 | 0.00003599 | 0.00003442 |
| Quality gate | FAIL | PASS | PASS (min 100%, không regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Thêm tài liệu `["jwt", "api key"]` vào `KNOWLEDGE_BASE`: so sánh API key (cố định, không hết hạn) với JWT (token có chữ ký, có thời điểm hết hạn) |
| scaling-03 | cpu, memory, custom metrics | Thêm tài liệu `["hpa", "kubernetes", "autoscal"]`: HPA scale theo CPU, memory hoặc custom metrics |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

v2 có bước retrieval nên prompt dài gấp đôi (57 → 109 token), tổng cost tăng ~86% và có thêm latency của bước search. Đổi lại accuracy tăng từ 4.3% lên 91.3%, nên cost / câu đúng giảm ~11 lần (0.000406 → 0.000036 USD). So theo "cost / câu" thì v1 rẻ hơn, nhưng so theo "cost / câu đúng" thì v2 rẻ hơn rất nhiều, vì câu trả lời sai là tiền mất trắng.

### CI quality gate

File `.github/workflows/eval.yml`: mỗi pull request chạy agent v2 rồi `run_eval.py --min-accuracy 0.85`. `run_eval.py` trả exit code 1 khi accuracy dưới ngưỡng hoặc có regression, nên job fail và PR không merge được.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
