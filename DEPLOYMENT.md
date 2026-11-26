# Deployment Information

## Public URL
https://day14-agent-7kz2.onrender.com

## Platform
Render (Blueprint `06-lab-complete/render.yaml`): web service Docker `day14-agent` + Key Value (Redis) `day14-redis`, gói free

## Test Commands

```bash
BASE=https://day14-agent-7kz2.onrender.com
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```

Kết quả (26/11/2026):

```
health 200
ready 200
ask-nokey 401
ask-key 200
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

`python check_production_ready.py --public-url https://day14-agent-7kz2.onrender.com`:

```
✅ Public URL: GET https://day14-agent-7kz2.onrender.com/health → 200
```

## Environment Variables Set
- `AGENT_API_KEY`: secret, nhập trên dashboard Render (`sync: false`), không có trong code
- `REDIS_URL`: Render tự nối từ service `day14-redis` (`fromService`)
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`
- `PORT`: Render tự cấp, Dockerfile đọc qua `${PORT:-8000}`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
- [check_production_ready.py --public-url](screenshots/production_ready.png)
