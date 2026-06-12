import json
import logging
import os
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

from src.agent.agent import ReActAgent
from src.core.llm_provider import LLMProvider
from src.tools.finance_tools import FINANCE_TOOLS, save_saving_plan


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='{"time":"%(asctime)s","level":"%(levelname)s","event":"%(message)s"}',
)
logger = logging.getLogger("moni-agent")

START_TIME = time.time()
IS_READY = False
IN_FLIGHT_REQUESTS = 0

APP_NAME = os.getenv("APP_NAME", "Moni Finance Agent")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", "5.0"))

PRICE_PER_1K_TOKENS_USD = float(os.getenv("PRICE_PER_1K_TOKENS_USD", "0.0006"))
MAX_DAILY_REQUESTS = int(os.getenv("MAX_DAILY_REQUESTS", "200"))

try:
    import redis

    REDIS_URL = os.getenv("REDIS_URL", "")
    redis_client = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None
    if redis_client:
        redis_client.ping()
except Exception:
    redis_client = None

memory_rate_limits: dict[str, list[float]] = {}
memory_usage: dict[str, dict[str, Any]] = {}


def log_event(event: str, **data: Any) -> None:
    logger.info(json.dumps({"event": event, **data}, ensure_ascii=False))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global IS_READY
    log_event("startup", app=APP_NAME, version=APP_VERSION, env=ENVIRONMENT)
    IS_READY = True
    yield
    IS_READY = False
    log_event("shutdown_start", in_flight_requests=IN_FLIGHT_REQUESTS)
    timeout_seconds = 30
    started = time.time()
    while IN_FLIGHT_REQUESTS > 0 and time.time() - started < timeout_seconds:
        time.sleep(0.2)
    log_event("shutdown_complete")


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def track_requests(request: Request, call_next):
    global IN_FLIGHT_REQUESTS
    IN_FLIGHT_REQUESTS += 1
    started = time.time()
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed_ms = int((time.time() - started) * 1000)
        IN_FLIGHT_REQUESTS -= 1
        log_event(
            "request",
            method=request.method,
            path=request.url.path,
            elapsed_ms=elapsed_ms,
        )


class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    system_prompt: Optional[str] = None


class AgentRequest(PromptRequest):
    max_steps: int = Field(default=10, ge=1, le=20)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    max_steps: int = Field(default=10, ge=1, le=20)


class SavePlanRequest(BaseModel):
    goal_name: str = Field(..., min_length=1)
    goal_amount: float = Field(..., gt=0)
    months: int = Field(..., ge=1, le=120)
    start_date: Optional[str] = None
    reminder_day: int = Field(default=5, ge=1, le=31)


def verify_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> str:
    if not AGENT_API_KEY and ENVIRONMENT != "production":
        return "local-dev"
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if x_api_key != AGENT_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return "api-user"


def check_rate_limit(user_id: str = Depends(verify_api_key)) -> str:
    now = time.time()
    window_seconds = 60

    if redis_client:
        key = f"rate:{user_id}:{int(now // window_seconds)}"
        count = redis_client.incr(key)
        redis_client.expire(key, window_seconds + 5)
        if count > RATE_LIMIT_PER_MINUTE:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return user_id

    bucket = memory_rate_limits.setdefault(user_id, [])
    memory_rate_limits[user_id] = [t for t in bucket if t > now - window_seconds]
    if len(memory_rate_limits[user_id]) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    memory_rate_limits[user_id].append(now)
    return user_id


def estimate_cost_usd(text: str) -> float:
    estimated_tokens = max(1, len(text.split()) * 2)
    return round((estimated_tokens / 1000) * PRICE_PER_1K_TOKENS_USD, 6)


def check_budget(user_id: str, estimated_cost_usd: float) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if redis_client:
        cost_key = f"cost:{user_id}:{today}"
        req_key = f"requests:{user_id}:{today}"
        current_cost = float(redis_client.get(cost_key) or 0)
        current_requests = int(redis_client.get(req_key) or 0)
        if current_cost + estimated_cost_usd > DAILY_BUDGET_USD:
            raise HTTPException(status_code=402, detail="Daily budget exceeded")
        if current_requests >= MAX_DAILY_REQUESTS:
            raise HTTPException(status_code=402, detail="Daily request budget exceeded")
        redis_client.incrbyfloat(cost_key, estimated_cost_usd)
        redis_client.incr(req_key)
        redis_client.expire(cost_key, 2 * 24 * 3600)
        redis_client.expire(req_key, 2 * 24 * 3600)
        return

    record = memory_usage.setdefault(user_id, {"day": today, "cost": 0.0, "requests": 0})
    if record["day"] != today:
        record.update({"day": today, "cost": 0.0, "requests": 0})
    if record["cost"] + estimated_cost_usd > DAILY_BUDGET_USD:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")
    if record["requests"] >= MAX_DAILY_REQUESTS:
        raise HTTPException(status_code=402, detail="Daily request budget exceeded")
    record["cost"] += estimated_cost_usd
    record["requests"] += 1


def get_llm_provider() -> LLMProvider:
    provider_name = os.getenv("DEFAULT_PROVIDER", "openai").strip().lower()

    if provider_name == "openai":
        from src.core.openai_provider import OpenAIProvider

        api_key = os.getenv("OPENAI_API_KEY")
        model_name = os.getenv("OPENAI_MODEL") or os.getenv("DEFAULT_MODEL", "gpt-4o")
        return OpenAIProvider(model_name=model_name, api_key=api_key)

    if provider_name in {"gemini", "google"}:
        from src.core.gemini_provider import GeminiProvider

        api_key = os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("GEMINI_MODEL") or os.getenv("DEFAULT_MODEL", "gemini-1.5-flash")
        return GeminiProvider(model_name=model_name, api_key=api_key)

    if provider_name == "local":
        from src.core.local_provider import LocalProvider

        model_path = os.getenv("LOCAL_MODEL_PATH")
        if not model_path:
            raise HTTPException(
                status_code=500,
                detail="LOCAL_MODEL_PATH is required when DEFAULT_PROVIDER=local.",
            )
        return LocalProvider(model_path=model_path)

    raise HTTPException(status_code=400, detail=f"Unsupported DEFAULT_PROVIDER: {provider_name}")


def get_react_agent(provider: LLMProvider = Depends(get_llm_provider)) -> ReActAgent:
    return ReActAgent(provider, FINANCE_TOOLS)


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "environment": ENVIRONMENT,
        "status": "running",
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "version": APP_VERSION,
        "environment": ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def ready() -> Dict[str, Any]:
    if not IS_READY:
        raise HTTPException(status_code=503, detail="Application is not ready")
    redis_status = "disabled"
    if redis_client:
        try:
            redis_client.ping()
            redis_status = "ok"
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Redis not ready: {exc}") from exc
    return {"ready": True, "redis": redis_status}


@app.get("/metrics")
def metrics() -> Dict[str, Any]:
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "in_flight_requests": IN_FLIGHT_REQUESTS,
        "storage": "redis" if redis_client else "memory",
    }


@app.post("/llm")
def generate_with_llm(
    request: PromptRequest,
    user_id: str = Depends(check_rate_limit),
    provider: LLMProvider = Depends(get_llm_provider),
) -> Dict[str, Any]:
    check_budget(user_id, estimate_cost_usd(request.prompt))
    try:
        result = provider.generate(request.prompt, system_prompt=request.system_prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "success": True,
        "mode": "llm",
        "model": provider.model_name,
        "response": result.get("content", ""),
        "usage": result.get("usage", {}),
        "latency_ms": result.get("latency_ms"),
        "provider": result.get("provider"),
    }


@app.post("/agent")
def generate_with_agent(
    request: AgentRequest,
    user_id: str = Depends(check_rate_limit),
    agent: ReActAgent = Depends(get_react_agent),
) -> Dict[str, Any]:
    check_budget(user_id, estimate_cost_usd(request.prompt))
    agent.max_steps = request.max_steps
    try:
        answer = agent.run(request.prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return answer


@app.post("/ask")
def ask(
    request: AskRequest,
    user_id: str = Depends(check_rate_limit),
    agent: ReActAgent = Depends(get_react_agent),
) -> Dict[str, Any]:
    check_budget(user_id, estimate_cost_usd(request.question))
    agent.max_steps = request.max_steps
    try:
        answer = agent.run(request.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"question": request.question, "answer": answer}


@app.post("/save-plan")
def direct_save_plan(
    request: SavePlanRequest,
    user_id: str = Depends(check_rate_limit),
) -> Dict[str, Any]:
    check_budget(user_id, estimate_cost_usd(request.goal_name))
    try:
        result = save_saving_plan(
            goal_name=request.goal_name,
            goal_amount=request.goal_amount,
            months=request.months,
            start_date=request.start_date,
            reminder_day=request.reminder_day,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Save failed"))
    return result


def handle_sigterm(signum, frame):
    log_event("SIGTERM", signal=signum)


signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)
