import os
import json
import base64
import secrets
from typing import List, Optional, Dict
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
        self.fps = int(os.getenv("RTSP2WEB_FPS", "10"))
        self.quality = int(os.getenv("RTSP2WEB_QUALITY", "80"))
        self.max_width = int(os.getenv("RTSP2WEB_MAX_WIDTH", "1280"))
        self.max_retries = int(os.getenv("RTSP2WEB_MAX_RETRIES", "3"))
        self.retry_interval = int(os.getenv("RTSP2WEB_RETRY_INTERVAL", "5"))
        self.reconnect_timeout = int(os.getenv("RTSP2WEB_RECONNECT_TIMEOUT", "5"))
        self.log_level = os.getenv("RTSP2WEB_LOG_LEVEL", "info")
        self.access_log = os.getenv("RTSP2WEB_ACCESS_LOG", "false").lower() == "true"
        self.idle_timeout = int(os.getenv("RTSP2WEB_IDLE_TIMEOUT", "120"))
        
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
import time
import logging
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StreamStatus(str, Enum):
    CONNECTED = "connected"
    CONNECTING = "connecting"
    ERROR = "error"
    RECONNECTING = "reconnecting"
    COOLDOWN = "cooldown"

import asyncio
import threading
from queue import Queue
from collections import deque

class StreamManager:
    def __init__(self):
        self.captures: Dict[str, cv2.VideoCapture] = {}
        self.last_frames: Dict[str, str] = {}
        self.last_frame_times: Dict[str, float] = {}
        self.connection_errors: Dict[str, tuple[float, int]] = {}
        self.stream_status: Dict[str, StreamStatus] = {}
        self.frame_buffers: Dict[str, deque] = {}
        self.buffer_size = 3  # Keep last 3 frames
        self.processing_threads: Dict[str, threading.Thread] = {}
        self.stop_flags: Dict[str, threading.Event] = {}
        self.last_access_times: Dict[str, float] = {}
        idle_checker_thread = threading.Thread(target=self._idle_checker, daemon=True)
        idle_checker_thread.start()
        
    def _process_frames(self, url: str, stop_event: threading.Event):
        """Background thread for continuous frame processing"""
        while not stop_event.is_set():
            cap = self.captures.get(url)
            if not cap:
                time.sleep(0.1)  # Short sleep if no capture
                continue

            try:
                if not cap.grab():
                    self._handle_connection_error(url)
                    cap.release()
                    del self.captures[url]
                    self.stream_status[url] = StreamStatus.RECONNECTING
                    continue

                ret, frame = cap.retrieve()
                if not ret or frame is None:
                    continue

                # Process frame
                if frame.shape[1] > config.max_width:
                    scale = config.max_width / frame.shape[1]
                    new_width = config.max_width
                    new_height = int(frame.shape[0] * scale)
                    frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

                # Encode frame
                encode_params = [
                    cv2.IMWRITE_JPEG_QUALITY, config.quality,
                    cv2.IMWRITE_JPEG_OPTIMIZE, 1,
                    cv2.IMWRITE_JPEG_PROGRESSIVE, 1
                ]
                ret, buffer = cv2.imencode('.jpg', frame, encode_params)
                if not ret:
                    continue

                # Store encoded frame
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                self.last_frames[url] = frame_base64
                self.last_frame_times[url] = time.time()

                # Update frame buffer
                if url not in self.frame_buffers:
                    self.frame_buffers[url] = deque(maxlen=self.buffer_size)
                self.frame_buffers[url].append(frame_base64)

            except Exception as e:
                logger.error(f"Error processing frame from stream {url}: {str(e)}")
                time.sleep(0.1)  # Prevent tight loop on error

    def get_stream(self, url: str) -> Optional[cv2.VideoCapture]:
        """Initialize stream and start processing thread if needed"""
        if url not in self.captures:
            # Check if we're in retry cooldown
            if url in self.connection_errors:
                last_error_time, retry_count = self.connection_errors[url]
                if retry_count >= config.max_retries:
                    time_since_error = time.time() - last_error_time
                    if time_since_error < config.retry_interval:
                        logger.debug(f"Too many connection attempts for {url}, waiting {config.retry_interval - time_since_error:.1f}s")
                        self.stream_status[url] = StreamStatus.COOLDOWN
                        return None
                    else:
                        # Reset retry count after interval
                        del self.connection_errors[url]

            # Determine stream type and set appropriate options
            is_rtsp = url.lower().startswith('rtsp://')
            is_mjpeg = url.lower().endswith('.mjpg') or url.lower().endswith('.mjpeg')
            
            stream_url = url
            if is_rtsp:
                # RTSP-specific options
                rtsp_options = {
                    # Transport settings
                    "rtsp_transport": "tcp",     # Force TCP mode
                    "buffer_size": "0",          # Minimize buffering
                    "max_delay": "0",            # Minimize latency
                    "stimeout": "5000000",       # Socket timeout in microseconds
                    "reorder_queue_size": "0",   # Disable reordering
                    
                    # Connection settings
                    "timeout": str(config.reconnect_timeout),  # Connection timeout
                    "rw_timeout": "5000000",     # Read/write timeout in microseconds
                    "fflags": "nobuffer",        # Disable input buffering
                    "flags": "low_delay",        # Minimize latency
                    
                    # Protocol settings
                    "rtsp_flags": "prefer_tcp",  # Prefer TCP for all RTSP streams
                    "allowed_media_types": "video", # Only receive video streams
                }
                
                if "?" not in stream_url:
                    stream_url += "?"
                else:
                    stream_url += "&"
                stream_url += "&".join(f"{k}={v}" for k, v in rtsp_options.items())
            elif is_mjpeg:
                # MJPEG-specific options
                mjpeg_options = {
                    "timeout": str(config.reconnect_timeout),
                    "rw_timeout": "5000000"
                }
                
                if "?" not in stream_url:
                    stream_url += "?"
                else:
                    stream_url += "&"
                stream_url += "&".join(f"{k}={v}" for k, v in mjpeg_options.items())
            
            logger.info(f"Opening {'RTSP' if is_rtsp else 'MJPEG'} stream: {url}")
            self.stream_status[url] = StreamStatus.CONNECTING
            
            try:
                cap = cv2.VideoCapture(stream_url)
                if not cap.isOpened():
                    self._handle_connection_error(url)
                    logger.error(f"Failed to open RTSP stream: {url}")
                    return None
                
                # Connection successful, reset error count
                if url in self.connection_errors:
                    del self.connection_errors[url]
                
                self.stream_status[url] = StreamStatus.CONNECTED
                logger.info(f"Successfully opened RTSP stream: {url}")
            except Exception as e:
                self._handle_connection_error(url)
                logger.error(f"Error opening RTSP stream {url}: {str(e)}")
                return None
                
            # Configure capture properties based on stream type
            if is_rtsp:
                # RTSP-specific settings
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer size
                
                # Try to set RTSP transport mode
                try:
                    transport_prop = getattr(cv2, 'CAP_PROP_RTSP_TRANSPORT', None)
                    if transport_prop is not None:
                        cap.set(transport_prop, 0)  # 0 = TCP
                except Exception as e:
                    logger.warning(f"Failed to set RTSP transport for stream {url}: {str(e)}")
                
                # Try to set FPS
                try:
                    cap.set(cv2.CAP_PROP_FPS, config.fps)
                except Exception as e:
                    logger.warning(f"Failed to set FPS for stream {url}: {str(e)}")
            else:
                # MJPEG/HTTP settings
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer size
                
                # Try to set FPS for MJPEG streams
                try:
                    cap.set(cv2.CAP_PROP_FPS, config.fps)
                except Exception as e:
                    logger.warning(f"Failed to set FPS for stream {url}: {str(e)}")
            self.captures[url] = cap
        return self.captures[url]
    
    def get_frame(self, url: str) -> Optional[str]:
        """Get the latest frame from the buffer"""
        self.last_access_times[url] = time.time()
        if url not in self.captures:
            cap = self.get_stream(url)
            if not cap:
                return None
            # Initialize frame processing thread
            if url not in self.processing_threads or not self.processing_threads[url].is_alive():
                stop_event = threading.Event()
                self.stop_flags[url] = stop_event
                thread = threading.Thread(target=self._process_frames, args=(url, stop_event))
                thread.daemon = True
                thread.start()
                self.processing_threads[url] = thread
        # Return the latest frame from buffer
        if url in self.frame_buffers and self.frame_buffers[url]:
            return self.frame_buffers[url][-1]
        return self.last_frames.get(url)

    def _handle_connection_error(self, url: str):
        """Update connection error tracking for the given stream"""
        current_time = time.time()
        if url in self.connection_errors:
            _, retry_count = self.connection_errors[url]
            self.connection_errors[url] = (current_time, retry_count + 1)
        else:
            self.connection_errors[url] = (current_time, 1)
        self.stream_status[url] = StreamStatus.ERROR

    def get_stream_status(self, index: int) -> str:
        """Get the current status of a stream by index"""
        if 0 <= index < len(config.streams):
            url = config.streams[index].url
            return self.stream_status.get(url, StreamStatus.ERROR)
        return StreamStatus.ERROR

    def get_error_count(self, url: str) -> int:
        """Get the number of connection errors for a stream"""
        if url in self.connection_errors:
            _, count = self.connection_errors[url]
            return count
        return 0

    def get_last_frame_time(self, url: str) -> Optional[float]:
        """Get the timestamp of the last received frame"""
        return self.last_frame_times.get(url)

    def _idle_checker(self):
        """Background thread to stop idle streams"""
        while True:
            current_time = time.time()
            for url in list(self.captures.keys()):
                last_access = self.last_access_times.get(url)
                if last_access and (current_time - last_access > config.idle_timeout):
                    logger.info(f"Idle timeout reached for stream {url}. Stopping stream.")
                    if url in self.stop_flags:
                        self.stop_flags[url].set()
                    if url in self.captures:
                        cap = self.captures[url]
                        cap.release()
                        del self.captures[url]
                    self.stream_status[url] = "idle"
            time.sleep(5)

stream_manager = StreamManager()

# Routes
@app.get("/", response_class=HTMLResponse)
async def root(_: HTTPBasicCredentials = Depends(verify_credentials)):
    with open("static/index.html", "r") as f:
        return f.read()

@app.get("/api/streams")
async def get_streams(_: HTTPBasicCredentials = Depends(verify_credentials)):
    streams_info = []
    for i, s in enumerate(config.streams):
        status = stream_manager.get_stream_status(i)
        streams_info.append({
            "name": s.name,
            "url": s.url,
            "status": status
        })
    
    return JSONResponse(content={
        "streams": streams_info,
        "fps": config.fps
    })

@app.get("/api/status")
async def get_status(_: HTTPBasicCredentials = Depends(verify_credentials)):
    """Get detailed status of all streams"""
    status = {}
    for i, stream in enumerate(config.streams):
        last_frame_time = stream_manager.get_last_frame_time(stream.url)
        time_since_last_frame = None
        if last_frame_time:
            time_since_last_frame = time.time() - last_frame_time
            
        status[str(i)] = {
            "name": stream.name,
            "status": stream_manager.get_stream_status(i),
            "errors": stream_manager.get_error_count(stream.url),
            "last_frame_age": round(time_since_last_frame, 1) if time_since_last_frame else None
        }
    return JSONResponse(content=status)

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

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources when the application shuts down"""
    logger.info("Shutting down RTSP2WEB server, cleaning up resources...")
    
    # Stop all frame processing threads
    for url, stop_event in stream_manager.stop_flags.items():
        stop_event.set()
        if url in stream_manager.processing_threads:
            stream_manager.processing_threads[url].join(timeout=1.0)
    
    # Release captures
    for url, cap in stream_manager.captures.items():
        try:
            cap.release()
            logger.info(f"Released stream: {url}")
        except Exception as e:
            logger.error(f"Error releasing stream {url}: {str(e)}")
    
    # Clear all data structures
    stream_manager.captures.clear()
    stream_manager.last_frames.clear()
    stream_manager.last_frame_times.clear()
    stream_manager.connection_errors.clear()
    stream_manager.stream_status.clear()
    stream_manager.frame_buffers.clear()
    stream_manager.processing_threads.clear()
    stream_manager.stop_flags.clear()
    
    logger.info("Cleanup complete")

if __name__ == "__main__":
    import uvicorn
    import signal
    import sys

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal, initiating graceful shutdown...")
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"Starting RTSP2WEB server on {config.host}:{config.port}")
    logger.info(f"FPS: {config.fps}, Quality: {config.quality}, Max Width: {config.max_width}px")
    logger.info(f"Retry Settings - Max: {config.max_retries}, Interval: {config.retry_interval}s, Timeout: {config.reconnect_timeout}s")
    logger.info(f"Loaded {len(config.streams)} streams")
    uvicorn.run(app, host=config.host, port=config.port, log_level=config.log_level, access_log=config.access_log)
