import logging
import time
import uuid

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

import analyser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("xai_forensics")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="xai-forensics")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = uuid.uuid4().hex[:8]
        logger.info("[%s] %s %s", request_id, request.method, request.url.path)
        response = await call_next(request)
        logger.info("[%s] %s %s -> %s", request_id, request.method, request.url.path, response.status_code)
        return response


app.add_middleware(RequestIDMiddleware)


class TextInput(BaseModel):
    text: str
    seed: int = 42


def _validate(body: TextInput) -> None:
    if len(body.text) > 1000:
        raise HTTPException(status_code=400, detail="text exceeds 1000 character limit")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")


def with_duration(result: dict, start: float) -> dict:
    result["duration_ms"] = round((time.perf_counter() - start) * 1000)
    return result


# ---------------------------------------------------------------------------
# Health check (root, no prefix)
# ---------------------------------------------------------------------------

@app.get("/")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# v1 API routes
# ---------------------------------------------------------------------------

v1 = APIRouter(prefix="/v1")


@v1.post("/why")
@limiter.limit("3/minute")
def why(request: Request, body: TextInput):
    _validate(body)
    start = time.perf_counter()
    return with_duration(analyser.explain_why(body.text, seed=body.seed), start)


@v1.post("/flip")
@limiter.limit("3/minute")
def flip(request: Request, body: TextInput):
    _validate(body)
    start = time.perf_counter()
    return with_duration(analyser.explain_flip(body.text), start)


@v1.post("/disagree")
@limiter.limit("3/minute")
def disagree(request: Request, body: TextInput):
    _validate(body)
    start = time.perf_counter()
    return with_duration(analyser.explain_disagree(body.text), start)


@v1.post("/analyse")
@limiter.limit("3/minute")
def analyse(request: Request, body: TextInput):
    _validate(body)
    start = time.perf_counter()
    result = {
        "why": analyser.explain_why(body.text, seed=body.seed),
        "flip": analyser.explain_flip(body.text),
        "disagree": analyser.explain_disagree(body.text),
    }
    result["duration_ms"] = round((time.perf_counter() - start) * 1000)
    return result


app.include_router(v1)


# ---------------------------------------------------------------------------
# Legacy bare routes (307 redirect preserves POST method and body)
# ---------------------------------------------------------------------------

@app.post("/why")
def why_redirect():
    return RedirectResponse(url="/v1/why", status_code=307)


@app.post("/flip")
def flip_redirect():
    return RedirectResponse(url="/v1/flip", status_code=307)


@app.post("/disagree")
def disagree_redirect():
    return RedirectResponse(url="/v1/disagree", status_code=307)


@app.post("/analyse")
def analyse_redirect():
    return RedirectResponse(url="/v1/analyse", status_code=307)
