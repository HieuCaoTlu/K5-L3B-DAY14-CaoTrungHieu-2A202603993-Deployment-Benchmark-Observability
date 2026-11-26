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

Stack: `docker compose -p k5-day14-observability`, agent v2 (2 instance) + Nginx + Prometheus + Grafana + Jaeger + Locust. Tải nền: Locust headless 30 user.

### 4.1 Screenshot

- [Dashboard Grafana khi đang có tải](screenshots/grafana-dashboard.png)
- [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png)
- [Trace lỗi trong Jaeger](screenshots/jaeger-error-trace.png)
- [Prometheus Alerts: AgentHighErrorRate + AgentInstanceDown cùng firing](screenshots/prometheus-alert-firing.png)

### 4.2 Thí nghiệm "phá hệ thống"

Thí nghiệm A và D chạy cùng lúc, T0 = 09:26:15 UTC (26/11/2026). Thời gian đo bằng cách poll `localhost:9090/api/v1/alerts` mỗi 5 giây.

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 91 s (rule `for: 1m` + cửa sổ `rate[1m]` + chu kỳ scrape/evaluate) | Error rate `/ask` |
| B | `MOCK_SLOW_RATE=0.3` | chưa chạy | | |
| C | `LLM_MODEL=mock-llm-large` | chưa chạy | | |
| D | `docker pause` 1 instance (`agent-2`) | `AgentInstanceDown` | 46 s (rule `for: 30s` + chu kỳ scrape) | Target up / số instance |
| E | `AGENT_VERSION=v1` | chưa chạy | | |

Trong lúc chạy A + D, `LLMCostBurnRateHigh` cũng đang firing (tải nền liên tục làm chi phí ước tính vượt 2 USD/giờ).

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

v1 vẫn trả 200 nhanh nên các alert về lỗi/latency không bắt được, nhưng câu trả lời sai. Cần giám sát chất lượng: chạy eval golden dataset định kỳ (hoặc trong CI trước khi deploy) và alert khi accuracy giảm; theo dõi metric `agent_info{version}` để thấy version đang chạy; theo dõi tín hiệu gián tiếp như số token / câu giảm đột ngột hoặc feedback xấu của user.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `963bedadf99b2d33f9620b2f3df97d28`
- Tổng thời gian: 1766.9 ms
- Span chiếm nhiều thời gian nhất: gọi LLM (1686.3 ms, 95.4%)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-26T09:27:27.424075+00:00", "level": "INFO", "service": "observable-agent", "instance": "bc825ceafa2f", "event": "llm_call", "trace_id": "963bedadf99b2d33f9620b2f3df97d28", "span_id": "c908ce9f38223afa", "request_id": "923f26510a9c", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 95, "output_tokens": 55, "cost_usd": 4.7e-05, "llm_ms": 1686.3}
{"ts": "2026-11-26T09:27:27.424308+00:00", "level": "INFO", "service": "observable-agent", "instance": "bc825ceafa2f", "event": "http_request", "trace_id": "963bedadf99b2d33f9620b2f3df97d28", "span_id": "c908ce9f38223afa", "request_id": "923f26510a9c", "method": "POST", "route": "/ask", "status": 200, "ms": 1766.9}
```

Trace lỗi: `trace_id` `b821faa6dc93e61c38349fa9c4090441`, trả 503 sau 106.3 ms:

```json
{"ts": "2026-11-26T09:28:10.219505+00:00", "level": "INFO", "service": "observable-agent", "instance": "bc825ceafa2f", "event": "llm_error", "trace_id": "b821faa6dc93e61c38349fa9c4090441", "span_id": "ced3698efad3db9b", "request_id": "73683d699161", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
{"ts": "2026-11-26T09:28:10.219774+00:00", "level": "INFO", "service": "observable-agent", "instance": "bc825ceafa2f", "event": "http_request", "trace_id": "b821faa6dc93e61c38349fa9c4090441", "span_id": "ced3698efad3db9b", "request_id": "73683d699161", "method": "POST", "route": "/ask", "status": 503, "ms": 106.3}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Số liệu dòng `POST /ask` trong `production/benchmark-results/scale_1_stats.csv` và `scale_3_stats.csv`.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 60.22 | 190 | 230 | 1700 | 64 / 7191 (0.89%) |
| 3 | 60.27 | 190 | 220 | 1700 | 71 / 7192 (0.99%) |

**Giải thích kết quả:** Scale lên 3 instance gần như không đổi gì: RPS giữ ~60, p95 chỉ giảm 230 → 220 ms, p99 vẫn 1700 ms. Nút thắt không nằm ở agent: mỗi user Locust chờ 0.5–2 s giữa 2 request (`wait_time = between(0.5, 2)`), nên 100 user chỉ tạo ra khoảng 60 req/s cố định, 1 instance async đã xử lý đủ. Latency do mock LLM quyết định (~190 ms, cộng 3% request chậm ~1.7 s tạo nên p99), thêm instance không làm LLM nhanh hơn. Lỗi ~1% là lỗi 503 giả lập của upstream LLM. Muốn thấy lợi ích của scale cần tải vượt khả năng 1 instance (nhiều user hơn hoặc bỏ `wait_time`).

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. Average che giấu tail latency: 3% request chậm đẩy p99 từ 225 lên 1695 ms trong khi avg chỉ tăng 30 ms, nên SLO phải đặt theo p95/p99.
  2. So sánh phiên bản theo "cost / câu đúng" chứ không theo "cost / câu": v2 đắt hơn mỗi câu nhưng rẻ hơn ~11 lần trên mỗi câu đúng.
  3. Metrics cho biết có vấn đề, trace cho biết vấn đề ở bước nào, log có `trace_id` nối 2 thứ lại; alert có `for:` nên luôn có độ trễ (46 s, 91 s) cần tính vào thời gian phản ứng.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

Alert theo accuracy của eval định kỳ (bắt được lỗi kiểu thí nghiệm E), alert khi `agent_info{version}` thay đổi ngoài lịch deploy, burn-rate alert theo error budget của SLO (thay vì ngưỡng cố định), metric tỉ lệ retrieval không tìm thấy tài liệu, và alert saturation (`agent_in_flight_requests`, CPU/memory container).
