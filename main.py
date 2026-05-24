
import os
import re
import tempfile
import logging
import yt_dlp
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Download API", version="1.0.0")

# 🔑 API Key Configuration - SET YOUR KEY HERE
# For production: use os.getenv("API_KEYS") instead of hardcoding
API_KEYS_RAW = os.getenv("API_KEYS", "dev-key-123")
VALID_API_KEYS = {key.strip() for key in API_KEYS_RAW.split(",") if key.strip()}

# Fallback for local testing only - REMOVE IN PRODUCTION
if not VALID_API_KEYS:
    VALID_API_KEYS.add("dev-key-123")
    logger.warning("⚠️ No API_KEYS env var set. Using fallback key: 'dev-key-123'")


def validate_api_key(key: str) -> None:
    """Raise 401 if API key is invalid"""
    if not key or key not in VALID_API_KEYS:
        logger.warning(f"❌ Invalid API key attempt: {key[:10] if key else 'empty'}...")
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.get("/download")
async def download_media(
    url: str = Query(..., description="YouTube video ID or full URL"),
    type: str = Query(..., pattern="^(audio|video)$", description="media type: audio or video"),
    api_key: str = Query(..., description="Your API authentication key")
):
    """
    Download & stream YouTube media.
    Matches client expectation: GET /download?url=VIDEO_ID&type=audio|video&api_key=KEY
    Streams raw MP3/MP4 in 128KB chunks.
    """
    validate_api_key(api_key)
    logger.info(f"📥 Request: type={type}, url={url[:50]}...")
    
    # 🔗 Normalize: convert video ID → full YouTube URL if needed
    if not url.startswith(("http://", "https://")):
        if re.match(r"^[a-zA-Z0-9_-]{11}$", url):            url = f"https://www.youtube.com/watch?v={url}"
            logger.debug(f"🔗 Converted ID to URL: {url}")
        else:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL or video ID")
    
    # ⚙️ yt-dlp options
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "noplaylist": True,
        "cachedir": False,
        # 🎭 Browser-like headers to avoid YouTube blocking
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": "https://www.youtube.com/",
        # 🔄 Retry logic
        "retries": 3,
        "fragment_retries": 3,
    }
    
    # 🎵 Audio vs 🎬 Video format settings
    if type == "audio":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "outtmpl": "%(id)s.mp3",
        })
    else:
        ydl_opts.update({
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": "%(id)s.mp4",
        })
    
    # 🗂️ Use temp directory (auto-cleanup on exit)
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts["outtmpl"] = os.path.join(tmpdir, "%(id)s." + ("mp3" if type == "audio" else "mp4"))
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.debug(f"🔍 Extracting info for: {url}")
                info = ydl.extract_info(url, download=True)
                
                if not info or "id" not in info:
                    raise HTTPException(status_code=404, detail="Video not found or restricted")
                                video_id = info["id"]
                expected_ext = "mp3" if type == "audio" else "mp4"
                
                # 🔎 Find the actual downloaded file
                downloaded_files = list(Path(tmpdir).glob(f"{video_id}.*"))
                if not downloaded_files:
                    raise HTTPException(status_code=500, detail="Download completed but file not found")
                
                # Pick the file with correct extension or largest size as fallback
                target_file = next((f for f in downloaded_files if f.suffix == f".{expected_ext}"), None)
                if not target_file:
                    target_file = max(downloaded_files, key=lambda p: p.stat().st_size)
                    logger.warning(f"⚠️ Using fallback file: {target_file.name}")
                
                # 📦 Stream the file in 128KB chunks (matches client's iter_chunked(131072))
                media_type = "audio/mpeg" if type == "audio" else "video/mp4"
                filename = target_file.name
                
                def file_iterator():
                    with open(target_file, "rb") as f:
                        while chunk := f.read(131072):
                            yield chunk
                
                logger.info(f"✅ Streaming {filename} ({type})")
                return StreamingResponse(
                    file_iterator(),
                    media_type=media_type,
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "X-Video-ID": video_id,
                    }
                )
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e).lower()
            logger.error(f"❌ yt-dlp error: {e}")
            
            if "video unavailable" in error_msg or "private video" in error_msg:
                raise HTTPException(status_code=404, detail="Video is private, deleted, or region-locked")
            elif "age" in error_msg or "age-restricted" in error_msg:
                raise HTTPException(status_code=403, detail="Age-restricted video. Enable cookies in API config.")
            elif "geo" in error_msg or "region" in error_msg:
                raise HTTPException(status_code=451, detail="Video not available in your region")
            else:
                raise HTTPException(status_code=400, detail=f"Download error: {str(e)}")
                
        except Exception as e:
            logger.exception(f"❌ Unexpected server error: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Simple health endpoint for monitoring"""
    return {"status": "healthy", "keys_loaded": len(VALID_API_KEYS)}


@app.get("/")
async def root():
    """API info"""
    return {
        "name": "YouTube Download API",
        "version": "1.0.0",
        "endpoints": {
            "/download": "GET - Download audio/video (params: url, type, api_key)",
            "/health": "GET - Health check"
        }
    }
