# RTSP2WEB

A simple web-based RTSP stream viewer that allows viewing multiple RTSP streams in a responsive grid layout through a web interface.

## Features

- View multiple RTSP streams simultaneously in a grid layout
- Automatic grid layout adjustment based on number of streams (1-16)
- Basic authentication for secure access
- Responsive design with fullscreen support
- Hover to view stream titles
- Automatic reconnection on stream failure
- Frame rate and quality control through environment variables

## Requirements

- Python 3.8+
- OpenCV with RTSP support
- Modern web browser with JavaScript enabled

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd rtsp2web
```

2. Install the required Python packages:
```bash
pip install -r requirements.txt
```

3. Configure your streams in `config.json`:
```json
[
  {
    "url": "rtsp://username:password@hostname:port/stream",
    "name": "Stream Name"
  }
]
```

4. Set up environment variables in `.env`:
```env
RTSP2WEB_LOGIN=user
RTSP2WEB_PASSWORD=pass
RTSP2WEB_HOST=0.0.0.0
RTSP2WEB_PORT=8080
RTSP2WEB_QUALITY=80
```

## Usage

1. Start the server:
```bash
python main.py
```

2. Open your web browser and navigate to:
```
http://localhost:8080
```

3. Enter the credentials configured in your `.env` file when prompted.

## Environment Variables

- `RTSP2WEB_LOGIN`: Username for web interface authentication
- `RTSP2WEB_PASSWORD`: Password for web interface authentication
- `RTSP2WEB_HOST`: Host to bind the server to (default: 0.0.0.0)
- `RTSP2WEB_PORT`: Port to run the server on (default: 8080)
- `RTSP2WEB_QUALITY`: JPEG quality for stream frames (1-100, default: 80)

## Browser Support

The application works best with modern browsers that support:
- CSS Grid Layout
- Fullscreen API
- Fetch API
- async/await
- ES6+ features

## Security Considerations

- The application uses basic authentication. Consider running behind a reverse proxy with HTTPS for production use.
- RTSP credentials are stored in plain text in config.json. Ensure proper file permissions are set.
- The server should be run in a secure environment as it needs access to RTSP streams.

## Limitations

- Maximum of 16 simultaneous streams supported
- RTSP streams must be accessible from the server
- Performance depends on server capabilities and network conditions
