# Lab 12 - Moni Finance Agent Productionization

Du an trong `06-lab-complete` da duoc thay bang codebase Moni Finance Agent va productionize theo yeu cau Day 12.

## Checklist

- [x] FastAPI backend tu project cu: `codebase/src/api/main.py`
- [x] Health check: `GET /health`
- [x] Readiness check: `GET /ready`
- [x] Metrics co ban: `GET /metrics`
- [x] API key authentication qua `X-API-Key`
- [x] Rate limiting
- [x] Cost guard
- [x] Config tu environment variables
- [x] Structured JSON logging
- [x] Graceful shutdown / SIGTERM handler
- [x] Redis-ready storage cho rate limit va budget
- [x] Dockerfile multi-stage, non-root user, healthcheck
- [x] Docker Compose backend + Redis
- [x] Render/Railway deployment config
- [x] GitHub Actions CI/CD

## Cau truc

```text
06-lab-complete/
├── codebase/
│   ├── src/                  # Moni FastAPI backend
│   │   ├── api/main.py        # Production API entrypoint
│   │   ├── agent/
│   │   ├── core/
│   │   ├── tools/
│   │   └── telemetry/
│   └── frontend/             # React + Vite frontend
├── Dockerfile
├── docker-compose.yml
├── render.yaml
├── railway.toml
├── requirements.txt
├── .env.example
└── check_production_ready.py
```

## Chay backend local bang Python

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\06-lab-complete
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example codebase\.env
```

Dien key that vao `codebase\.env` neu muon goi LLM that:

```env
OPENAI_API_KEY=...
AGENT_API_KEY=dev-key-change-me
```

Chay backend:

```powershell
$env:PYTHONPATH="codebase"
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Test:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl -X POST http://localhost:8000/agent -H "X-API-Key: dev-key-change-me" -H "Content-Type: application/json" -d "{\"prompt\":\"Toi con bao nhieu tien?\",\"max_steps\":10}"
```

## Chay bang Docker Compose

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\06-lab-complete
docker compose up --build
```

Test:

```powershell
curl http://localhost:8000/health
curl -X POST http://localhost:8000/agent -H "X-API-Key: dev-key-change-me" -H "Content-Type: application/json" -d "{\"prompt\":\"Lap ke hoach tiet kiem 5 trieu trong 3 thang\",\"max_steps\":10}"
```

## Chay frontend local

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\06-lab-complete\codebase\frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

Frontend env:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_AGENT_API_KEY=dev-key-change-me
```

## Deploy Render

1. Push repo len GitHub.
2. Render Dashboard -> New -> Blueprint.
3. Chon repo nay.
4. Render se doc `06-lab-complete/render.yaml`.
5. Set secret `OPENAI_API_KEY` hoac `GEMINI_API_KEY` tren Render Dashboard.
6. Deploy va ghi lai public API URL.

Test public URL:

```powershell
curl https://your-render-url.onrender.com/health
curl -X POST https://your-render-url.onrender.com/agent -H "X-API-Key: YOUR_AGENT_API_KEY" -H "Content-Type: application/json" -d "{\"prompt\":\"Xin chao Moni\",\"max_steps\":10}"
```

## Deploy Railway

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\06-lab-complete
railway login
railway init
railway variables set ENVIRONMENT=production
railway variables set APP_NAME="Moni Finance Agent"
railway variables set OPENAI_API_KEY=...
railway variables set AGENT_API_KEY=...
railway up
railway domain
```

## GitHub Actions CI/CD

Workflow nam tai:

```text
.github/workflows/day12-ci-cd.yml
```

Workflow se chay khi push/PR vao `main` hoac `master`:

- Backend dependency install
- Python compile
- Production readiness checker
- Frontend `npm ci` va `npm run build`
- Docker image build
- Trigger Render deploy neu co secret deploy hook

De bat CD len Render:

1. Vao Render service -> Settings -> Deploy Hook.
2. Copy deploy hook URL.
3. Vao GitHub repo -> Settings -> Secrets and variables -> Actions.
4. Them secret:

```text
RENDER_DEPLOY_HOOK_URL=<render deploy hook url>
```

Khi push vao branch `main`, GitHub Actions se trigger Render deploy hook sau khi CI pass.

## Kiem tra production readiness

```powershell
cd C:\Users\Admin\Desktop\AI\lab12\batch02-day12_cloud_infras_and_deployment\06-lab-complete
$env:PYTHONIOENCODING='utf-8'
python check_production_ready.py
```

Ket qua hien tai: `20/20 checks passed`.

## API URL sau deploy

Ghi URL cua ban vao day sau khi deploy:

```text
Production API URL: <dien-link-render-hoac-railway-o-day>
```

