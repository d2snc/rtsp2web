# RTSP2WEB

English | [Russian](README.ru.md)  

A web-based system for viewing RTSP streams in a browser with the ability to display multiple streams simultaneously in a mosaic layout.

![RTSP2WEB Screenshot](https://i.imgur.com/GNL3ebp.png)

## How It Works

The system consists of two main components:

1. **Backend (Python/FastAPI)**
   - Retrieves RTSP streams from cameras using OpenCV
   - Converts frames to JPEG and sends them via HTTP
   - Implements basic authentication
   - Automatically reconnects after a stream disconnection

2. **Frontend (HTML/CSS/JavaScript)**
   - Displays streams in a responsive grid
   - Automatically adjusts cell sizes based on the number of streams
   - Supports fullscreen mode
   - Shows stream names on hover

## Installation

1. Install Python 3.8 or later if it's not already installed.

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the streams in the `config.json` file:
```json
[
  {
    "url": "rtsp://login:password@ip:port/path",
    "name": "Camera Name"
  },
  {
    "url": "rtsp://login:password@ip:port/path",
    "name": "Camera Name"
  }
]
```

4. Create a `.env` file with system settings or put them in the environment section of `docker-compose.yml`:
```env
# Login credentials for the web interface
RTSP2WEB_LOGIN=user
RTSP2WEB_PASSWORD=pass

# Network settings
RTSP2WEB_HOST=0.0.0.0  # 0.0.0.0 to allow access from all interfaces
RTSP2WEB_PORT=8080     # Web server port

# Quality and performance settings
RTSP2WEB_FPS=10               # Frames per second
RTSP2WEB_QUALITY=80           # JPEG quality (1-100)
RTSP2WEB_MAX_WIDTH=1280       # Maximum frame width (in pixels)

# Reconnection parameters
RTSP2WEB_MAX_RETRIES=3        # Maximum number of reconnection attempts
RTSP2WEB_RETRY_INTERVAL=5     # Interval between reconnection attempts (sec)
RTSP2WEB_RECONNECT_TIMEOUT=5  # Reconnection timeout (sec)

# Logging
RTSP2WEB_LOG_LEVEL=info       # Logging level (debug, info, warning, error)
RTSP2WEB_ACCESS_LOG=false     # Request logging (true or false)

# Idle stream management
RTSP2WEB_IDLE_TIMEOUT=120      # Idle time (sec) before a stream is closed
```

## Running the Server

1. Start the server:
```bash
python main.py
```

2. Open the browser and go to:
```
http://localhost:8080
```

3. Enter the login and password specified in the `.env` file.

## Project Structure

- `main.py` - The main server file
  - RTSP stream processing
  - API endpoints
  - Authentication
  - Frame conversion

- `static/`
  - `index.html` - Interface HTML layout
  - `styles.css` - Styles and responsive grid
  - `script.js` - Client-side logic
    - Fetching the list of streams
    - Displaying frames
    - Layout management
    - Error handling

- `config.json` - RTSP stream configuration
- `.env` - System settings
- `requirements.txt` - Python dependencies

## Implementation Features

### Backend

1. **Stream Processing**
   - Each stream is opened via OpenCV.
   - Frames are converted to JPEG and sent via HTTP.
   - Automatic reconnection occurs if the connection is lost.
   - The last successfully received frame is cached.

2. **API**
   - `/api/streams` - List of available streams
   - `/api/frame/{index}` - Fetch a frame for a specific stream
   - All requests require basic authentication.

### Frontend

1. **Responsive Grid**
   - Automatically calculates cell sizes.
   - Supports 1 to 16 streams.
   - Maintains video aspect ratio.

2. **Performance Optimization**
   - Uses requestAnimationFrame for frame updates.
   - Cancels requests when a stream is stopped.
   - DOM elements are cached.

3. **User Interface**
   - Dark mode.
   - Fullscreen mode.
   - Stream names on hover.
   - Loading and error indicators.

## Security

1. **Authentication**
   - Basic HTTP authentication.
   - Protection for all endpoints.
   - Secure password comparison.

2. **Recommendations**
   - Use HTTPS when accessing over the internet.
   - Keep the `.env` file secure.
   - Restrict access to `config.json`.
   - Run the server in a secure environment.

## Limitations

- Maximum of 16 simultaneous streams.
- RTSP streams must be accessible from the server.
- Performance depends on:
  - Server power.
  - Network bandwidth.
  - Number and quality of streams.
  - Browser capabilities.

## Troubleshooting

1. **Streams are not displaying**
   - Check if RTSP streams are accessible from the server.
   - Ensure credentials in `config.json` are correct.
   - Check server logs for errors.

2. **Low performance**
   - Lower JPEG quality.
   - Reduce the number of simultaneous streams.
   - Monitor CPU and network usage.

3. **Authentication errors**
   - Verify credentials in `.env`.
   - Ensure the browser supports basic authentication.
   - Clear the browser cache.

## System Requirements

- Python 3.8+
- OpenCV with RTSP support
- Modern browser 