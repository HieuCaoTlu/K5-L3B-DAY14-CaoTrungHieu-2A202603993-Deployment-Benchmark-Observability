# Cao Trung Hiếu - 2A202603993

## Part 1

### Exercise 1.1

* API Key của LLM và địa chỉ tới Database bị lộ ngay trong source code (dòng 17–18)

* Các config bị cố định trong file python, muốn sửa trên production thì bắt buộc phải sửa code (dòng 21–22)

* Logging dùng hàm print thay vì thư viện logging, còn in cả API key ra log (dòng 33–34)

* Không có API health check, mỗi khi build xong phải truy cập thủ công để kiểm tra hệ thống (dòng 42)

* Port gán cứng trong code, dùng chung VPS với service khác dễ trùng port (dòng 52)

* Host là `localhost` nên chạy trong container thì bên ngoài không gọi vào được (dòng 51)

### Exercise 1.2

* Chạy API ask thành công (bản develop nhận `question` qua query string)

```
{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

* Chạy API health bị lỗi 404 vì chưa tồn tại

### Exercise 1.3

* Chạy API ask thành công, hiện tên model

```
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","model":"gpt-4o-mini"}
```

* Chạy API health và ready thành công

```
{"status":"ok","uptime_seconds":20.3,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T07:43:54.987946+00:00"}
{"ready":true}
```

| Feature      | Develop  | Production          | Tại sao quan trọng?                                                  |
| ------------ | -------- | ------------------- | -------------------------------------------------------------------- |
| Config       | Hardcode | Env vars            | Không lộ secret, đổi config không cần sửa code                       |
| Health check | Không có | `/health`, `/ready` | Platform tự restart khi app chết, chỉ route traffic khi app sẵn sàng |
| Logging      | print()  | JSON                | Dễ parse, lọc log; không log secret                                  |
| Shutdown     | Đột ngột | Graceful            | Không cắt ngang request đang chạy khi deploy/scale                   |

`/health` kiểm tra app còn sống không, lỗi thì platform restart container. `/ready` kiểm tra app sẵn sàng nhận request chưa (đang khởi động, mất Redis...), lỗi thì load balancer ngừng gửi traffic nhưng không restart

## Part 2

### Exercise 2.1

* Base image: `python:3.11` (bản đầy đủ, khoảng 1GB)

* Working directory: `/app`

* COPY `requirements.txt` trước để tận dụng layer cache: chỉ sửa code thì Docker dùng lại layer `pip install`, không phải cài lại dependency

* `CMD` là lệnh mặc định, bị ghi đè khi chạy `docker run image <lệnh khác>`. `ENTRYPOINT` là lệnh cố định, tham số truyền vào chỉ được nối thêm vào sau

### Exercise 2.2

* Build và chạy container thành công, gọi API ask:

```
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

* Image size `my-agent:develop`: 426 MB

### Exercise 2.3

* Stage 1 (`builder`): dùng `python:3.11-slim`, cài gcc, libpq-dev và `pip install --user` các dependency

* Stage 2 (`runtime`): dùng `python:3.11-slim` mới, chỉ copy package đã cài từ stage 1 và code, chạy bằng user non-root, có `HEALTHCHECK`

* Image nhỏ hơn vì dùng bản `slim`, còn gcc, build tools, apt cache nằm lại ở stage 1, không vào image cuối

| Image               | Size    |
| ------------------- | ------- |
| `my-agent:develop`  | 426 MB  |
| `my-agent:advanced` | 57.4 MB |

* Giảm 86 % so với bản develop

### Exercise 2.4

```
client ──:80──> nginx ──> agent:8000 ──> redis:6379; qdrant:6333
```

* 4 service: nginx (reverse proxy, load balancer), agent (FastAPI), redis (cache, rate limit), qdrant (vector DB)

* Chỉ nginx mở port 80 ra ngoài, các service còn lại nằm trong network `internal`, gọi nhau bằng tên service (`redis:6379`, `qdrant:6333`)

* Test qua Nginx:

```
{"status":"ok","uptime_seconds":39.1,"version":"2.0.0","timestamp":"2026-11-26T08:06:38.235180"}
```

## Part 3

### Exercise 3.2 (Render)

* Deploy agent Part 6 (`06-lab-complete/`) bằng Render Blueprint, kèm Redis (Key Value) của Render

* Public URL: <https://day14-agent-7kz2.onrender.com> (chi tiết trong `DEPLOYMENT.md`)

```
health 200
ready 200
ask-nokey 401
ask-key 200
```

### So sánh `railway.toml` và `render.yaml`

|           | `railway.toml`                                    | `render.yaml`                                                                              |
| --------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Phạm vi         | Chỉ cấu hình build/deploy cho 1 service           | Blueprint mô tả cả hạ tầng: web service + Redis                                            |
| Build           | `builder = "DOCKERFILE"`                          | `runtime: docker`, `rootDir`, `dockerfilePath`                                             |
| Health check    | `healthcheckPath = "/health"`                     | `healthCheckPath: /health`                                                                 |
| Biến môi trường | Không khai báo trong file, set bằng CLI/dashboard | Khai báo trong file, secret dùng `sync: false`, `REDIS_URL` nối tự động bằng `fromService` |
| Redis           | Tạo riêng trên dashboard rồi tự gán `REDIS_URL`   | Tạo cùng lúc trong Blueprint                                                               |

* Render khai báo được cả hạ tầng nên dựng lại từ đầu chỉ cần 1 file, Railway gọn hơn nhưng phải cấu hình Redis và biến môi trường bằng tay

### Exercise 3.3 (Cloud Run)

* `cloudbuild.yaml` chạy 4 bước nối tiếp: test (pytest) → build image Docker (tag theo commit SHA + `latest`, dùng cache) → push lên Container Registry → `gcloud run deploy`

* Deploy ở `asia-southeast1`, min 1 instance để tránh cold start, max 10, 512Mi RAM, secret `OPENAI_API_KEY` lấy từ Secret Manager

* Test fail thì các bước sau không chạy, nên code lỗi không lên production

* `service.yaml` mô tả service Cloud Run (image, tài nguyên, autoscaling, probe) dưới dạng khai báo

## Part 4

### Exercise 4.1

* API key được check ở hàm `verify_api_key`, đọc header `X-API-Key`, gắn vào `/ask` bằng `Depends`

* Thiếu key trả 401, sai key trả 403

* Rotate key: key đọc từ env var `AGENT_API_KEY`, chỉ cần đổi biến rồi restart, không phải sửa code

```
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 401 Unauthorized
date: Thu, 26 Nov 2026 08:09:06 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

```
$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:09:18 GMT
server: uvicorn
content-length: 114
content-type: application/json

{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

### Exercise 4.2

* JWT flow: gọi `POST /auth/token` bằng username/password để lấy token (có ký, chứa `role`, hết hạn 60 phút), các request sau gửi header `Authorization: Bearer <token>`, server chỉ cần verify chữ ký, không phải tra DB

```
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:12:59 GMT
server: uvicorn
content-length: 192
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"Explain JWT","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

### Exercise 4.3

* Algorithm: sliding window, mỗi user có một deque lưu timestamp các request trong 60 giây gần nhất

* Limit: user 10 req/phút, admin 100 req/phút

* Admin không bypass hẳn mà dùng limiter riêng theo `role` (tài khoản `teacher` là admin)

* Request thứ 10 trong vòng lặp đã bị 429 vì request ở Exercise 4.2 cũng tính vào limit 10 req/phút (9 + 1 = 10)

```
1: 200
2: 200
3: 200
4: 200
5: 200
6: 200
7: 200
8: 200
9: 200
10: 429
11: 429
12: 429
13: 429
14: 429
15: 429
16: 429
17: 429
18: 429
19: 429
20: 429
HTTP/1.1 429 Too Many Requests
date: Thu, 26 Nov 2026 08:13:28 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795680869
retry-after: 32
content-length: 98
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":32}}
```

### Exercise 4.4

* Trước khi gọi LLM, `check_budget` kiểm tra: vượt budget user (1 USD/ngày) trả 402, vượt budget toàn hệ thống (10 USD/ngày) trả 503, dùng tới 80% thì log cảnh báo

* Sau khi gọi LLM, `record_usage` cộng token và tính tiền theo giá gpt-4o-mini, sang ngày mới tự reset

* Hạn chế: lưu in-memory nên restart là mất, nhiều instance không dùng chung được, production nên lưu trong Redis (key `budget:{user}:{tháng}`)

* Rate limit bảo vệ tốc độ (chống spam), cost guard bảo vệ tiền (10 prompt rất dài/phút vẫn qua rate limit nhưng có thể tiêu hết budget), nên cần cả hai

* Implement theo yêu cầu đề (10 USD/tháng/user, lưu Redis, reset đầu tháng):

```python
import os
import redis
from datetime import datetime

r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
MONTHLY_BUDGET_USD = 10.0

def check_budget(user_id: str, estimated_cost: float) -> bool:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"   # mỗi tháng một key → sang tháng mới tự "reset"

    current = float(r.get(key) or 0)
    if current + estimated_cost > MONTHLY_BUDGET_USD:
        return False                         # vượt budget → API trả 402

    r.incrbyfloat(key, estimated_cost)       # cộng atomic, nhiều instance dùng chung
    r.expire(key, 32 * 24 * 3600)            # tự xoá key cũ sau ~1 tháng
    return True
```

* Khác bản có sẵn trong `cost_guard.py`:

|                    | `cost_guard.py` có sẵn                              | Bản implement                                             |
| ------------------------ | --------------------------------------------------- | --------------------------------------------------------- |
| Budget                   | 1 USD/ngày/user, 10 USD/ngày toàn hệ thống          | 10 USD/tháng/user                                         |
| Lưu trữ                  | RAM (dict)                                          | Redis                                                     |
| Reset                    | So sánh ngày trong code                             | Key theo tháng + TTL                                      |
| Restart / nhiều instance | Mất dữ liệu, mỗi instance đếm riêng                 | Giữ nguyên, các instance dùng chung                       |
| Kiểm tra                 | Chỉ check chi phí đã dùng, ghi nhận sau khi gọi LLM | Check cả chi phí ước tính của request sắp gọi, trả `bool` |

## Part 5

### Exercise 5.1

* `/health` (liveness): trả status, uptime, version và check memory, process còn sống là trả 200

* `/ready` (readiness): trả 503 khi `_is_ready = False` (đang khởi động hoặc đang shutdown), sẵn sàng thì trả 200 kèm số request đang xử lý

```
$ curl http://localhost:8000/health
{"status":"ok","uptime_seconds":10.5,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T08:21:00.530243+00:00","checks":{"memory":{"status":"ok","used_percent":13.9}}}

$ curl http://localhost:8000/ready
{"ready":true,"in_flight_requests":1}
```

### Exercise 5.2

* Nhận SIGTERM → uvicorn ngừng nhận request mới, `lifespan` đặt `_is_ready = False` rồi chờ `_in_flight_requests` về 0 (tối đa 30s) mới thoát

```
$ curl -X POST "http://localhost:8000/ask?question=Long%20task" & kill -TERM $(pgrep -f "python app.py")
INFO:     Shutting down
INFO:     127.0.0.1:54410 - "POST /ask?question=Long%20task HTTP/1.1" 200 OK
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
INFO:     Waiting for application shutdown.
2026-11-26 08:24:59,313 INFO 🔄 Graceful shutdown initiated...
2026-11-26 08:24:59,313 INFO ✅ Shutdown complete
INFO:     Application shutdown complete.
INFO:     Finished server process [8322]
```

* Request gửi ngay trước SIGTERM vẫn trả 200 rồi app mới tắt → không bị cắt ngang

### Exercise 5.3

* Session lưu trong Redis (`session:{id}`, `setex` TTL 1 giờ), không có Redis thì fallback dict trong RAM kèm cảnh báo

* Cần stateless vì mỗi instance có RAM riêng: request 1 vào instance A, request 2 vào instance B thì B không thấy history nếu lưu trong RAM

### Exercise 5.4

```
1: "served_by":"instance-997717"
2: "served_by":"instance-3bfa2d"
3: "served_by":"instance-95eddb"
4: "served_by":"instance-997717"
5: "served_by":"instance-3bfa2d"
6: "served_by":"instance-95eddb"
7: "served_by":"instance-997717"
8: "served_by":"instance-3bfa2d"
9: "served_by":"instance-95eddb"
10: "served_by":"instance-997717"
```

* Nginx chia round-robin đều cho 3 instance

### Exercise 5.5

```
Session ID: 9152307e-192e-4898-b0aa-4929dd7d332a
Request 1: [instance-3bfa2d]  Q: What is Docker?
Request 2: [instance-95eddb]  Q: Why do we need containers?
Request 3: [instance-997717]  Q: What is Kubernetes?
Request 4: [instance-3bfa2d]  Q: How does load balancing work?
Request 5: [instance-95eddb]  Q: What is Redis used for?
Instances used: {'instance-997717', 'instance-95eddb', 'instance-3bfa2d'}
✅ All requests served despite different instances!
--- Conversation History ---
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

* 5 request cùng session đi qua cả 3 instance nhưng history vẫn đủ 10 message (5 user + 5 assistant) vì state nằm trong Redis, không nằm trong RAM của instance nào

## Part 6

* Image `prod-check` (multi-stage, `python:3.11-slim`): 238 MB, đo bằng `check_production_ready.py`

* `python check_production_ready.py` (chạy trong WSL, có Docker):

```
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

## Part 7

### Exercise 7.1

* Counter: `http_requests_total{method="POST",route="/ask",status="200"}`, Gauge: `agent_in_flight_requests`, Histogram: `http_request_duration_seconds_bucket{le="0.3",method="POST",route="/ask"}`

* Nếu dùng URL thật làm label, mỗi URL lạ bot quét (`/wp-admin`, `/.env`, `/a1b2c3`...) tạo ra một time series mới → cardinality bùng nổ, Prometheus hết RAM. Dùng `route.path` thì số label cố định, URL lạ gộp chung vào `unmatched`

* Đã thêm `agent_question_length_chars` (Histogram, bucket 20 → 2000 ký tự), không dùng label vì độ dài có vô số giá trị

```
agent_question_length_chars_bucket{le="50.0"} 1.0
agent_question_length_chars_count 1.0
agent_question_length_chars_sum 40.0
```

### Exercise 7.2 và 7.3

* Kết quả load test, tail latency và eval nằm trong `BENCHMARK_REPORT.md` mục 2 và 3, file JSON trong `06-lab-complete/benchmark-observability/develop/reports/`

* CI quality gate: `.github/workflows/eval.yml`

### Exercise 7.4 – 7.7

* Stack chạy bằng `docker compose -p k5-day14-observability`: agent v2 + Nginx + Prometheus + Grafana + Jaeger + Locust

* Sửa `production/Dockerfile`: user `agent` có home là `/app` nên Python không tìm thấy package cài bằng `--user` ở `/home/agent/.local` (lỗi `No module named 'uvicorn'`, agent restart liên tục), đổi home thành `/home/agent`

* Chép phần sửa `KNOWLEDGE_BASE` từ `develop/` sang `production/utils/mock_llm.py`

* Benchmark scaling (Locust headless, 100 user, 2 phút, dòng `POST /ask`):

| Số instance | RPS   | p50    | p95    | p99     | Failures  |
| ----------- | ----- | ------ | ------ | ------- | --------- |
| 1           | 60.22 | 190 ms | 230 ms | 1700 ms | 64 / 7191 |
| 3           | 60.27 | 190 ms | 220 ms | 1700 ms | 71 / 7192 |

* Scale lên 3 instance gần như không đổi vì Locust có `wait_time = between(0.5, 2)` nên tải cố định \~60 req/s, 1 instance đã đủ; latency do mock LLM quyết định

* Alert: `MOCK_ERROR_RATE=0.2` + `docker pause` agent-2 cùng lúc → `AgentInstanceDown` firing sau 46s, `AgentHighErrorRate` firing sau 91s

* Trace chậm `963bedadf99b2d33f9620b2f3df97d28`: tổng 1766.9 ms, gọi LLM chiếm 1686.3 ms (95.4%). Trace lỗi `b821faa6dc93e61c38349fa9c4090441`: 503 do upstream LLM. Log JSON đi kèm trong `BENCHMARK_REPORT.md` mục 4.3

## AI log

Công cụ: Claude Code (Claude), chạy trong VS Code, có quyền đọc file trong repo và chạy lệnh trong WSL.

| Phần | AI chỉ hỗ trợ chạy lệnh & test | Bạn tự làm, viết & tự kiểm tra |
| :--- | :--- | :--- |
| **Đọc đề** | Chạy lệnh kiểm tra nhanh cấu trúc thư mục, file `.env`, endpoint thực tế nếu cần xác nhận | Tự đọc `CHECKPOINTS.md`, `README.md`, tự phát hiện và ghi chú các chỗ đề ghi sai (endpoint, tài khoản, `.env.local`, build từ gốc repo) |
| **Part 1** | Chạy lệnh khi cần kiểm tra trạng thái/log và test nhanh kết quả trả về | Tự chạy bản develop/production, tự tìm anti-pattern kèm số dòng, tự viết bảng so sánh, giải thích `/health` vs `/ready`, viết ý 1.1 và tự rút gọn theo văn phong của bạn |
| **Part 2** | Chạy lệnh build/compose/test khi bạn yêu cầu kiểm tra | Tự viết/chỉnh Dockerfile, tự build image, đo size (426 MB / 57.4 MB), chạy compose qua Nginx, tự viết câu trả lời 2.1, 2.3, sơ đồ 2.4 và điền số liệu |
| **Part 4** | Chạy `curl` / test script kiểm tra nhanh các luồng auth, rate limit, budget nếu cần | Tự đọc & viết code, tự chạy `curl` ra 401 / 200 / 429, tự viết `check budget` và tự viết câu trả lời 4.1–4.4 |
| **Part 5** | Chạy stack 3 instance và `test_stateless.py` (5.4, 5.5) để trả output thô cho bạn | Tự viết/kiểm tra phần stateless, tự chạy 5.1, 5.2 (health, ready, SIGTERM), tự viết giải thích 5.1–5.3 và tự đọc/điền kết quả 5.4, 5.5 |
| **Part 6** | Chạy `check_production_ready.py` và các lệnh test xác minh | Tự viết code `app/` (config, auth, rate limiter, cost guard, redis client, main), Dockerfile, compose, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`, tự chạy `check_production_ready.py --public-url` → PASS 12/12 và đọc lại toàn bộ code |
| **Part 3** | Chạy lệnh kiểm tra/test endpoint sau khi deploy nếu cần | Tự sửa `render.yaml` (`rootDir`, plan free), tạo Blueprint trên Render, đặt `AGENT_API_KEY` trên dashboard, tự chạy 4 lệnh kiểm tra, chụp ảnh, tự viết `DEPLOYMENT.md`, so sánh Railway/Render và mô tả pipeline Cloud Run |
| **Part 7 Bước 1** | Chạy lệnh load test, eval v1/v2 hoặc CI test khi cần | Tự so sánh `MOCK_SLOW_RATE`, tự thêm tài liệu vào `KNOWLEDGE_BASE`, thêm metric `agent_question_length_chars`, tự viết file CI, tự điền `BENCHMARK_REPORT.md` mục 1–3 và đối chiếu số với file JSON |
| **Part 7 Bước 2** | Chạy lệnh Locust scale 1/3, tạo tải/lỗi test hoặc truy vấn log khi cần | Tự sửa lỗi `production/Dockerfile` (home user), tự gây lỗi để alert firing và đo thời gian, tự lấy `trace_id` từ log, tự mở Prometheus, Grafana, Jaeger chụp 4 ảnh, tự điền `BENCHMARK_REPORT.md` mục 4–6 và kiểm tra trace ID khớp báo cáo |