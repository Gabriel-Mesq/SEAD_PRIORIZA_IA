from fastapi import FastAPI
from pydantic import BaseModel
from llama_client import call_llama

app = FastAPI()

class PromptRequest(BaseModel):
    prompt: str

@app.post("/generate")
def generate_text(request: PromptRequest):
    result = call_llama(request.prompt)
    return result
