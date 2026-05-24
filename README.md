# 🚀 Fast YouTube Stream & Download API

A high-performance FastAPI-based YouTube downloader and streaming API.  
Supports raw MP3/MP4 streaming with optimized chunked responses and low latency playback.

---

## 🔍 How This Maps to Your Client

| Client Expectation | API Implementation |
|-------------------|-------------------|
| `GET /download?url=...&type=...&api_key=...` | `@app.get("/download")` with `Query` params |
| Streams raw MP3/MP4 | `StreamingResponse` with 128KB chunked yield |
| `200 OK` on success | FastAPI returns `200` automatically |
| Non-200 on failure | `HTTPException` with proper status codes |
| Timeout handling | FastAPI/Uvicorn supports timeout via reverse proxy or client config |

---

# 🚀 Production Recommendations

### 1. API Key Management
Replace env var with a DB/Redis lookup or JWT validation.

### 2. Rate Limiting
Add `slowapi` or Nginx `limit_req` to prevent abuse.

### 3. Caching
Cache frequent downloads to disk/Redis to save bandwidth and avoid re-fetching.

### 4. Queue System
For heavy traffic, use `Celery` + `RabbitMQ` to offload `yt-dlp` blocking calls.

### 5. Dockerize

```dockerfile
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## ⚡ Features

- 🎵 MP3 Audio Streaming
- 🎬 MP4 Video Download
- ⚡ Fast Chunked Streaming
- 🔐 API Key Protection
- 🐳 Docker Ready
- 🚀 Production Optimized

---

## 📦 Tech Stack

- FastAPI
- Uvicorn
- yt-dlp
- FFmpeg
- Python 3.11

---

## 📜 License

MIT License
