from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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


@app.post("/why")
def why(body: TextInput):
    if len(body.text) > 1000:
        raise HTTPException(status_code=400, detail="text exceeds 1000 character limit")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")
    return analyser.explain_why(body.text)


@app.post("/flip")
def flip(body: TextInput):
    if len(body.text) > 1000:
        raise HTTPException(status_code=400, detail="text exceeds 1000 character limit")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")
    return analyser.explain_flip(body.text)


@app.post("/disagree")
def disagree(body: TextInput):
    if len(body.text) > 1000:
        raise HTTPException(status_code=400, detail="text exceeds 1000 character limit")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")
    return analyser.explain_disagree(body.text)


@app.post("/analyse")
def analyse(body: TextInput):
    # single endpoint that runs all three methods and returns combined JSON
    # the frontend calls this once instead of three parallel calls
    # tradeoff: slower than parallel calls but simpler to wire on the frontend
    if len(body.text) > 1000:
        raise HTTPException(status_code=400, detail="text exceeds 1000 character limit")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")
    return {
        "why": analyser.explain_why(body.text),
        "flip": analyser.explain_flip(body.text),
        "disagree": analyser.explain_disagree(body.text),
    }