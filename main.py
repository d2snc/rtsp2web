import os
import json
import base64
import secrets
from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
@dataclass
class Stream:
    url: str
    name: str

class Config:
    def __init__(self):
        self.login = os.getenv("RTSP2WEB_LOGIN", "user")
        self.password = os.getenv("RTSP2WEB_PASSWORD", "pass")
        self.host = os.getenv("RTSP2WEB_HOST", "0.0.0.0")
        self.port = int(os.getenv("RTSP2WEB_PORT", "8080"))
        self.quality = int(os.getenv("RTSP2WEB_QUALITY", "80"))
        
        # Load streams from config file
        self.streams: List[Stream] = []
        self._load_streams()
    
    def _load_streams(self):
        try:
            with open("config.json", "r") as f:
                streams_data = json.load(f)
                self.streams = [Stream(**stream) for stream in streams_data]
        except Exception as e:
            print(f"Error loading streams configuration: {e}")
            self.streams = []

config = Config()

# Initialize FastAPI
app = FastAPI(docs_url=None, redoc_url=None)
security = HTTPBasic()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication
def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    is_username_correct = secrets.compare_digest(credentials.username, config.login)
    is_password_correct = secrets.compare_digest(credentials.password, config.password)
    
    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials

# Stream Manager
class StreamManager:
    def __init__(self):
        self.captures = {}
        self.last_frames = {}
        
    def get_stream(self, url: str) -> Optional[cv2.VideoCapture]:
        if url not in self.captures:
            cap = cv2.VideoCapture(url)
            if not cap.isOpened():
                return None
            self.captures[url] = cap
        return self.captures[url]
    
    def get_frame(self, url: str) -> Optional[str]:
        cap = self.get_stream(url)
        if not cap:
            return None
            
        ret, frame = cap.read()
        if not ret:
            # Try to reconnect
            cap.release()
            del self.captures[url]
            return self.last_frames.get(url)
            
        # Encode frame to JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, config.quality])
        if not ret:
            return None
            
        # Convert to base64
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        self.last_frames[url] = frame_base64
        return frame_base64

stream_manager = StreamManager()

# Routes
@app.get("/", response_class=HTMLResponse)
async def root(_: HTTPBasicCredentials = Depends(verify_credentials)):
    with open("static/index.html", "r") as f:
        return f.read()

@app.get("/api/streams")
async def get_streams(_: HTTPBasicCredentials = Depends(verify_credentials)):
    return JSONResponse(content=[{"name": s.name, "url": s.url} for s in config.streams])

@app.get("/api/frame/{stream_index}")
async def get_frame(
    stream_index: int,
    _: HTTPBasicCredentials = Depends(verify_credentials)
):
    if stream_index < 0 or stream_index >= len(config.streams):
        raise HTTPException(status_code=404, detail="Stream not found")
        
    stream = config.streams[stream_index]
    frame = stream_manager.get_frame(stream.url)
    
    if frame is None:
        raise HTTPException(status_code=503, detail="Stream unavailable")
        
    return JSONResponse(content={"frame": frame})

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.host, port=config.port)
