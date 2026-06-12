# Solution.md - Day 12 Codelab 1->5

File nay tra loi cac bai codelab tu Part 1 den Part 5 trong `CODE_LAB.md`.
Phan Project / Lab Assignment o `06-lab-complete` se lam sau.

---

## Part 1 - Localhost vs Production

### Exercise 1.1 - Anti-patterns trong `01-localhost-vs-production/develop/app.py`

1. Hardcode secret trong code:
   - `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`
   - `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`
   - Neu push len GitHub public, secret co the bi crawler quet va bi dung trai phep.

2. Config khong doc tu environment:
   - `DEBUG = True`
   - `MAX_TOKENS = 500`
   - `host="localhost"`
   - `port=8000`
   - Khi deploy len Railway/Render, port thuong duoc inject qua bien `PORT`, nen hardcode port de gay loi.

3. Debug/reload bat trong runtime:
   - `reload=True`
   - Phu hop dev local, khong phu hop production vi ton tai nguyen, co the reload bat ngo va lam lo thong tin debug.

4. Khong co health check:
   - Khong co `/health` hoac `/ready`.
   - Cloud platform/load balancer khong biet instance con song hay san sang nhan traffic.

5. Khong graceful shutdown:
   - Khong co lifespan cleanup hay SIGTERM handling.
   - Khi container bi stop, request dang xu ly co the bi cat ngang.

6. Logging bang `print()` va log secret:
   - `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`
   - Production can structured logging va tuyet doi khong log secret.

7. Bind vao `localhost`:
   - Container/platform ben ngoai khong truy cap duoc neu chi bind localhost.
   - Production nen bind `0.0.0.0`.

### Exercise 1.2 - Chay basic version

Lenh chay:

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\01-localhost-vs-production\develop
pip install -r requirements.txt
python app.py
```

Lenh test:

```powershell
curl -X POST "http://localhost:8000/ask?question=hello"
```

Quan sat:

- App chay duoc tren may local.
- Tuy nhien app chua production-ready vi secret bi hardcode, khong co health check, khong co env config, logging chua an toan, khong co graceful shutdown.

### Exercise 1.3 - So sanh basic va production

Lenh chay ban production:

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\01-localhost-vs-production\production
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Bang so sanh:

| Feature | Basic | Production | Tai sao quan trong? |
| --- | --- | --- | --- |
| Config | Hardcode trong code | Doc tu env vars qua `.env`/environment | Moi moi truong dev/staging/prod co the doi config ma khong sua code |
| Secrets | Hardcode va co the bi log | Doc tu `OPENAI_API_KEY`, `AGENT_API_KEY`, khong log secret | Giam rui ro lo key va de rotate |
| Port | Co dinh `8000` | Doc tu `PORT` | Cloud platform thuong inject port dong |
| Host | `localhost` | `0.0.0.0` | Container can nhan request tu ben ngoai |
| Health check | Khong co | Co `/health`, `/ready`, `/metrics` | Platform biet luc nao restart hoac route traffic |
| Logging | `print()` | Structured JSON logging | De query/search trong log aggregator |
| Shutdown | Tat dot ngot | Lifespan + SIGTERM handler | Hoan thanh request dang xu ly truoc khi stop |
| Debug | `reload=True` | Chi reload khi `DEBUG=true` | Production on dinh va an toan hon |

### Checkpoint 1

- Hardcode secret nguy hiem vi co the bi lo khi commit/push code.
- Environment variables giup tach config khoi code va dung cung mot codebase cho nhieu moi truong.
- Health check giup platform giam sat/restart instance loi.
- Graceful shutdown giup app dung nhan request moi, xu ly xong request dang chay, dong connection roi moi thoat.

---

## Part 2 - Docker Containerization

### Exercise 2.1 - Dockerfile co ban

File: `02-docker/develop/Dockerfile`

1. Base image:
   - `python:3.11`
   - Day la full Python image, de hieu nhung kha lon.

2. Working directory:
   - `WORKDIR /app`
   - Moi lenh tiep theo chay trong `/app`.

3. Tai sao copy `requirements.txt` truoc?
   - Docker build theo layer cache.
   - Neu source code thay doi nhung `requirements.txt` khong doi, Docker co the dung lai layer `pip install`, build nhanh hon.

4. `CMD` vs `ENTRYPOINT`:
   - `CMD` la command mac dinh, de override khi `docker run`.
   - `ENTRYPOINT` gan container nhu mot executable co dinh.
   - Thuong dung `CMD ["python", "app.py"]` cho app don gian; dung `ENTRYPOINT` khi muon container luon chay mot binary/script nhat dinh.

### Exercise 2.2 - Build va run

Build tu root cua Day 12:

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -p 8000:8000 my-agent:develop
```

Test:

```powershell
curl http://localhost:8000/ask -X POST -H "Content-Type: application/json" -d "{\"question\":\"What is Docker?\"}"
```

Xem image size:

```powershell
docker images my-agent:develop
```

Nhan xet:

- Ban develop dung `python:3.11` full image nen image thuong lon.
- Container giup dong goi Python version, dependencies va source code vao cung mot runtime lap lai duoc.

### Exercise 2.3 - Multi-stage build

File: `02-docker/production/Dockerfile`

Stage 1 - Builder:

- `FROM python:3.11-slim AS builder`
- Cai build dependencies nhu `gcc`, `libpq-dev`.
- Cai Python packages vao `/root/.local` bang `pip install --user`.
- Stage nay chi dung de build dependency, khong deploy.

Stage 2 - Runtime:

- `FROM python:3.11-slim AS runtime`
- Tao non-root user `appuser`.
- Copy package da build tu builder sang runtime.
- Copy source code can thiet.
- Chay app bang `uvicorn`.
- Co Docker `HEALTHCHECK`.

Tai sao image nho va an toan hon:

- Runtime khong giu build tools, compiler, cache pip.
- Chay bang non-root user.
- Chi copy file can chay.

Lenh build va so sanh:

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment
docker build -f 02-docker/production/Dockerfile -t my-agent:production .
docker images my-agent
```

### Exercise 2.4 - Docker Compose stack

File: `02-docker/production/docker-compose.yml`

Services:

- `agent`: FastAPI AI agent.
- `redis`: cache/session/rate limiting.
- `qdrant`: vector database cho RAG.
- `nginx`: reverse proxy/load balancer, expose HTTP/HTTPS ra ngoai.

Architecture:

```text
Client
  |
  v
Nginx :80/:443
  |
  v
Agent container :8000
  |-----------------> Redis :6379
  |
  |-----------------> Qdrant :6333
```

Lenh chay:

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\02-docker\production
docker compose up
```

Test:

```powershell
curl http://localhost/health
curl http://localhost/ask -X POST -H "Content-Type: application/json" -d "{\"question\":\"Explain microservices\"}"
```

Lenh debug huu ich:

```powershell
docker compose ps
docker compose logs agent
docker compose exec agent sh
docker compose down
```

### Cau hoi thao luan Part 2

1. `.dockerignore` nen chua:
   - `.env`, `venv/`, `__pycache__/`, `.git/`, logs, test cache, local data.
   - `venv/` lam build context rat lon va co dependency theo OS local.
   - `.env` co secret, khong duoc copy vao image.

2. Mount volume khi agent can doc file tu disk:

```powershell
docker run -p 8000:8000 -v C:\path\local-data:/app/data my-agent:production
```

Trong Docker Compose:

```yaml
volumes:
  - ./data:/app/data
```

3. Compose huu ich vi gom nhieu service thanh mot stack, co network noi bo, dependency order, healthcheck va volume rieng.

---

## Part 3 - Cloud Deployment

### Exercise 3.1 - Railway

Muc tieu:

- Dua app co public URL.
- Railway inject `PORT`, nen app phai bind `0.0.0.0` va doc port tu env.
- Health check path la `/health`.

Lenh deploy mau:

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\03-cloud-deployment\railway
npm i -g @railway/cli
railway login
railway init
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY=my-secret-key
railway up
railway domain
```

Test public URL:

```powershell
curl https://your-app.up.railway.app/health
curl https://your-app.up.railway.app/ask -X POST -H "Content-Type: application/json" -d "{\"question\":\"hello\"}"
```

Giai thich `railway.toml`:

- `builder = "NIXPACKS"`: Railway tu detect Python app.
- `startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT"`: chay uvicorn bang port Railway inject.
- `healthcheckPath = "/health"`: dung de restart khi app fail.
- `restartPolicyType = "ON_FAILURE"`: tu restart khi crash.

### Exercise 3.2 - Render

Deploy flow:

1. Push code len GitHub.
2. Vao Render Dashboard.
3. New -> Blueprint.
4. Connect repo.
5. Render doc `render.yaml`.
6. Set secret env vars trong dashboard.
7. Deploy.

So sanh `render.yaml` voi `railway.toml`:

| Noi dung | Railway | Render |
| --- | --- | --- |
| Config file | `railway.toml` | `render.yaml` |
| Cach build | Nixpacks/Docker auto detect | `runtime`, `buildCommand`, `startCommand` |
| Health check | `healthcheckPath` | `healthCheckPath` |
| Env vars | CLI/dashboard | `envVars`, `sync:false`, dashboard |
| IaC | Ngan gon cho 1 service | Blueprint mo ta web service + Redis |
| Auto deploy | Theo project Railway | `autoDeploy: true` khi push GitHub |

### Exercise 3.3 - GCP Cloud Run

Trong `03-cloud-deployment/production-cloud-run`:

- `cloudbuild.yaml`: CI/CD pipeline build image, push image, deploy len Cloud Run.
- `service.yaml`: khai bao Cloud Run service, container, env vars, resources va scaling.

Khi nao chon platform:

- Railway/Render: demo, MVP, bai hoc, deploy nhanh.
- Cloud Run: production nhe/vua, can autoscaling, scale-to-zero, CI/CD tot hon.
- Kubernetes: he thong lon, nhieu service, can control cao, doi hoi van hanh nhieu hon.

### Cau hoi thao luan Part 3

1. Tai sao serverless khong phai luc nao cung tot cho AI agent?
   - AI agent co the can request lau, streaming, warm model/cache, background job, connection dai.
   - Serverless co timeout, cold start va han che runtime.

2. Cold start la gi?
   - La thoi gian khoi tao container/function moi khi chua co instance warm.
   - Anh huong UX vi request dau tien cham hon.

3. Khi nao upgrade tu Railway len Cloud Run?
   - Khi can autoscaling on dinh, traffic lon, CI/CD ro rang, IAM/secret management tot, monitoring/logging tot, region/resource control tot hon.

### Checkpoint 3

- App phai co `/health`.
- Config production phai nam trong env vars, khong hardcode.
- Public URL can test duoc bang curl/Postman.
- Can biet xem logs tren dashboard hoac CLI.

---

## Part 4 - API Security

### Exercise 4.1 - API Key authentication

File: `04-api-gateway/develop/app.py`

API key duoc check o:

- `api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)`
- `verify_api_key(...)`
- Endpoint `/ask` dung dependency `_key: str = Depends(verify_api_key)`.

Neu thieu key:

- Tra `401 Missing API key`.

Neu sai key:

- Tra `403 Invalid API key`.

Neu dung key:

- Endpoint `/ask` xu ly request va tra answer.

Rotate key:

- Doi bien moi truong `AGENT_API_KEY`.
- Restart/redeploy app.
- Trong production nen co thoi gian overlap key cu/moi neu co client dang dung key cu.

Lenh chay/test:

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\04-api-gateway\develop
pip install -r requirements.txt
$env:AGENT_API_KEY="secret-key-123"
python app.py
```

Test khong co key:

```powershell
curl http://localhost:8000/ask -X POST -H "Content-Type: application/json" -d "{\"question\":\"Hello\"}"
```

Test co key:

```powershell
curl http://localhost:8000/ask -X POST -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d "{\"question\":\"Hello\"}"
```

### Exercise 4.2 - JWT authentication

Files:

- `04-api-gateway/production/auth.py`
- `04-api-gateway/production/app.py`

JWT flow:

1. Client gui username/password den `/auth/token`.
2. Server verify bang `authenticate_user`.
3. Server tao token bang `create_token`.
4. Client gui `Authorization: Bearer <token>` khi goi `/ask`.
5. `verify_token` decode token, check signature/expiry, lay `username` va `role`.

Demo users:

- `student / demo123` -> role `user`
- `teacher / teach456` -> role `admin`

Lenh lay token:

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\04-api-gateway\production
pip install -r requirements.txt
python app.py
```

```powershell
curl http://localhost:8000/auth/token -X POST -H "Content-Type: application/json" -d "{\"username\":\"student\",\"password\":\"demo123\"}"
```

Dung token:

```powershell
$env:TOKEN="<paste-token-here>"
curl http://localhost:8000/ask -X POST -H "Authorization: Bearer $env:TOKEN" -H "Content-Type: application/json" -d "{\"question\":\"Explain JWT\"}"
```

### Exercise 4.3 - Rate limiting

File: `04-api-gateway/production/rate_limiter.py`

Algorithm:

- Sliding Window Counter.
- Moi user co mot `deque` timestamp request.
- Moi request se xoa timestamp cu ngoai window.
- Neu so request trong window >= limit thi raise `429 Too Many Requests`.

Limit:

- User: `10 requests / 60 seconds`.
- Admin: `100 requests / 60 seconds`.

Bypass/higher limit cho admin:

- Trong `app.py`, neu `role == "admin"` thi dung `rate_limiter_admin`, con lai dung `rate_limiter_user`.
- Admin khong bypass hoan toan, nhung co quota cao hon.

Test spam 20 request trong PowerShell:

```powershell
1..20 | ForEach-Object {
  curl http://localhost:8000/ask -X POST -H "Authorization: Bearer $env:TOKEN" -H "Content-Type: application/json" -d "{\"question\":\"Test $_\"}"
}
```

Ket qua mong doi:

- Request trong limit tra `200`.
- Khi vuot limit tra `429`, co `Retry-After` va thong tin limit/reset.

### Exercise 4.4 - Cost guard

File: `04-api-gateway/production/cost_guard.py`

Logic hien tai:

- Per-user daily budget: `$1/day`.
- Global daily budget: `$10/day`.
- Warn khi user dung 80% budget.
- `check_budget(user_id)` chay truoc khi goi LLM.
- `record_usage(user_id, input_tokens, output_tokens)` ghi nhan usage sau khi co response.
- Vuot per-user budget: HTTP `402`.
- Vuot global budget: HTTP `503`.

Ban Redis-style theo yeu cau codelab:

```python
import redis
from datetime import datetime

r = redis.Redis()

def check_budget(user_id: str, estimated_cost: float) -> bool:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"

    current = float(r.get(key) or 0)
    if current + estimated_cost > 10:
        return False

    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)
    return True
```

Trong production that nen luu usage vao Redis/DB thay vi in-memory, vi scale nhieu instance thi memory moi instance khac nhau.

### Cau hoi thao luan Part 4

1. Khi nao dung API Key?
   - Internal service, MVP, B2B simple integration, machine-to-machine.

2. Khi nao dung JWT?
   - User login, can role/expiry, frontend/mobile client, stateless auth.

3. Khi nao dung OAuth2?
   - Can delegated access, login bang provider ben thu ba, enterprise SSO.

4. Rate limit nen dat bao nhieu cho AI agent?
   - Tuy budget/model/use case.
   - Vi du: free user 5-10 req/min, paid user 30-100 req/min, admin/internal cao hon.
   - Nen limit theo user, IP, endpoint va cost/token, khong chi theo request count.

5. Neu API key bi lo:
   - Revoke/rotate key ngay.
   - Kiem tra logs va usage bat thuong.
   - Doi secret tren cloud/env.
   - Redeploy service.
   - Them alert, rate limit, cost guard.
   - Neu key da commit, xoa khoi git history neu can va tao key moi.

---

## Part 5 - Scaling & Reliability

### Exercise 5.1 - Health checks

File tham khao: `05-scaling-reliability/develop/app.py`

Liveness `/health`:

- Tra `200` neu process con song.
- Nen kem uptime, version, environment, timestamp.
- Co the check memory/dependency nhe.

Readiness `/ready`:

- Tra `200` khi instance san sang nhan traffic.
- Tra `503` khi dang startup/shutdown hoac dependency chua ready.
- Load balancer dung readiness de quyet dinh co route traffic vao instance khong.

Code mau:

```python
@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "version": "1.0.0",
    }

@app.get("/ready")
def ready():
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Agent not ready")
    return {"ready": True}
```

Neu co Redis/DB:

```python
@app.get("/ready")
def ready():
    try:
        redis_client.ping()
        return {"ready": True}
    except Exception:
        raise HTTPException(status_code=503, detail="Dependency not ready")
```

### Exercise 5.2 - Graceful shutdown

Y tuong:

1. Khi nhan SIGTERM, danh dau instance khong ready.
2. Dung nhan request moi.
3. Cho request dang xu ly hoan thanh.
4. Dong connection Redis/DB/client.
5. Thoat trong grace period.

Code mau theo lifespan:

```python
_is_ready = False
_in_flight_requests = 0

@app.middleware("http")
async def track_requests(request, call_next):
    global _in_flight_requests
    _in_flight_requests += 1
    try:
        return await call_next(request)
    finally:
        _in_flight_requests -= 1

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    _is_ready = True
    yield
    _is_ready = False
    timeout = 30
    elapsed = 0
    while _in_flight_requests > 0 and elapsed < timeout:
        time.sleep(1)
        elapsed += 1
```

Signal handler:

```python
def handle_sigterm(signum, frame):
    logger.info(f"Received signal {signum}; uvicorn will handle graceful shutdown")

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)
```

Uvicorn:

```python
uvicorn.run(app, host="0.0.0.0", port=port, timeout_graceful_shutdown=30)
```

### Exercise 5.3 - Stateless design

Anti-pattern:

```python
conversation_history = {}
```

Van de:

- Khi scale len nhieu instance, moi instance co memory rieng.
- User request lan 1 vao instance A, request lan 2 vao instance B thi B khong co history.
- Khi instance restart, memory mat het.

Dung hon:

- Luu session/history vao Redis/DB/object storage.
- Moi instance doc/ghi cung mot store.
- Them TTL de tu expire session cu.

Code trong `05-scaling-reliability/production/app.py`:

- `save_session(session_id, data, ttl_seconds=3600)`
- `load_session(session_id)`
- `append_to_history(session_id, role, content)`
- Neu Redis co san thi luu vao Redis.
- Neu Redis khong san thi fallback in-memory, nhung co warning "not scalable".

### Exercise 5.4 - Load balancing

File: `05-scaling-reliability/production/docker-compose.yml`

Services:

- `agent`: co the scale thanh 3 instances.
- `redis`: shared session store.
- `nginx`: load balancer expose `localhost:8080`.

Architecture:

```text
Client
  |
  v
Nginx :8080
  |
  +--> Agent instance 1
  +--> Agent instance 2
  +--> Agent instance 3
          |
          v
        Redis
```

Lenh chay:

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\05-scaling-reliability\production
docker compose up --scale agent=3
```

Test:

```powershell
1..10 | ForEach-Object {
  curl http://localhost:8080/chat -X POST -H "Content-Type: application/json" -d "{\"question\":\"Request $_\"}"
}
```

Quan sat:

- Response co `served_by`, cho biet request duoc serve boi instance nao.
- Nginx phan tan request qua cac instance.
- Redis giu session nen history khong mat khi request vao instance khac.

### Exercise 5.5 - Test stateless

Lenh:

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\05-scaling-reliability\production
python test_stateless.py
```

Script lam gi:

1. Tao session moi qua `/chat`.
2. Gui nhieu cau hoi lien tiep voi cung `session_id`.
3. Ghi nhan `served_by` de xem request co vao nhieu instance khac nhau khong.
4. Goi `/chat/{session_id}/history`.
5. Xac nhan history van con du du request duoc serve boi instance nao.

Ket luan:

- Neu history van con khi request duoc phan tan qua nhieu instance, app da stateless dung cach.
- Neu dung memory local thay Redis, history de bi mat/le khi request vao instance khac.

### Checkpoint 5

- Health check = liveness, tra loi "process co con song khong?"
- Readiness check = instance co san sang nhan traffic khong?
- Graceful shutdown giup rolling deploy khong cat ngang request.
- Stateless design la dieu kien bat buoc de scale horizontally.
- Load balancer phan tan traffic; shared store nhu Redis giu state chung.

---

## Tom tat

5 phan codelab hoan thanh cac y chinh:

1. Localhost vs Production: tach config, khong hardcode secret, health check, structured logging, graceful shutdown.
2. Docker: dong goi app, toi uu image bang multi-stage, chay stack bang Compose.
3. Cloud Deployment: Railway/Render/Cloud Run, public URL, env vars, health check, logs.
4. API Security: API key, JWT, rate limiting, cost guard.
5. Scaling & Reliability: liveness/readiness, graceful shutdown, stateless Redis session, Nginx load balancing.

