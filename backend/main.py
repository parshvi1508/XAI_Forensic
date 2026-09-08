from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import analyser

app = FastAPI(title="xai-forensics")

# allow all origins for the demo - this is a public tool with no auth
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class TextInput(BaseModel):
    text: str


@app.get("/")
def health():
    return {"status": "ok"}


def with_duration(result: dict, start: float) -> dict:
    result["duration_ms"] = round((time.perf_counter() - start) * 1000)
    return result


@app.post("/why")
def why(body: TextInput):
    if len(body.text) > 1000:
        raise HTTPException(status_code=400, detail="text exceeds 1000 character limit")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")
    start = time.perf_counter()
    return with_duration(analyser.explain_why(body.text), start)


@app.post("/flip")
def flip(body: TextInput):
    if len(body.text) > 1000:
        raise HTTPException(status_code=400, detail="text exceeds 1000 character limit")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")
    start = time.perf_counter()
    return with_duration(analyser.explain_flip(body.text), start)


@app.post("/disagree")
def disagree(body: TextInput):
    if len(body.text) > 1000:
        raise HTTPException(status_code=400, detail="text exceeds 1000 character limit")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")
    start = time.perf_counter()
    return with_duration(analyser.explain_disagree(body.text), start)


@app.post("/analyse")
def analyse(body: TextInput):
    if len(body.text) > 1000:
        raise HTTPException(status_code=400, detail="text exceeds 1000 character limit")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")
    start = time.perf_counter()
    result = {
        "why": analyser.explain_why(body.text),
        "flip": analyser.explain_flip(body.text),
        "disagree": analyser.explain_disagree(body.text),
    }
    result["duration_ms"] = round((time.perf_counter() - start) * 1000)
    return result