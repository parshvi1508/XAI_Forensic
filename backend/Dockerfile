# Hugging Face Spaces requires the app to listen on port 7860
# python:3.11-slim keeps the image small, no CUDA needed for CPU inference on HF free tier
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces free tier: CPU only, 16GB RAM, models download on first cold start
# models cache to /root/.cache/huggingface after first load
EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]