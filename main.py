import os
import yt_dlp
import tempfile
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse

app = FastAPI(title="YouTube Download API", version="1.0.0")

# Load allowed API keys (comma-separated from env)
VALID_API_KEYS = {key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip()}
if not VALID_API_KEYS:
    VALID_API_KEYS.add(os.getenv("DEFAULT_API_KEY", "change-me-in-production"))

def validate_api_key(key: str):
    if key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

@app.get("/download")
async def download_media(
    url: str = Query(..., description="YouTube video ID or full URL"),
    type: str = Query(..., pattern="^(audio|video)$", description="media type: audio or video"),
    api_key: str = Query(..., description="Your API authentication key")
):
    validate_api_key(api_key)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "noplaylist": True,
        "outtmpl": "%(id)s.%(ext)s",
        "cachedir": False,
    }

    if type == "audio":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        })
    else:
        ydl_opts.update({
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4"
        })

    # Use a temporary directory that auto-cleans after response
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts["outtmpl"] = os.path.join(tmpdir, "%(id)s.%(ext)s")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise HTTPException(status_code=404, detail="Video not found or restricted")

                # Locate the actual downloaded file
                downloaded_files = list(Path(tmpdir).glob("*"))
                if not downloaded_files:
                    raise HTTPException(status_code=500, detail="Download completed but file not found")

                file_path = downloaded_files[0]
                media_type = "audio/mpeg" if type == "audio" else "video/mp4"
                filename = file_path.name

                def file_iterator():
                    with open(file_path, "rb") as f:
                        while chunk := f.read(131072):  # 128KB chunks (matches your client)
                            yield chunk

                return StreamingResponse(
                    file_iterator(),
                    media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                )
        except yt_dlp.utils.DownloadError as e:
            raise HTTPException(status_code=400, detail=f"yt-dlp error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
