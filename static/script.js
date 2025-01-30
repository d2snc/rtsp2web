class StreamViewer {
    constructor() {
        this.streams = [];
        this.streamGrid = document.getElementById('streamGrid');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.fullscreenBtn = document.getElementById('fullscreenBtn');
        this.container = document.querySelector('.container');
        this.frameRequests = new Map();
        this.currentSingleStreamIndex = null;
        this.statusCheckInterval = null;
        this.frameTimers = new Map();
        this.fps = 10; // Will be updated from server

        // Single stream view elements
        this.singleStreamView = document.getElementById('singleStreamView');
        this.singleStreamTitle = document.getElementById('singleStreamTitle');
        this.singleStreamImage = document.getElementById('singleStreamImage');
        this.backToGridBtn = document.getElementById('backToGrid');
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', () => this.cleanup());
        
        this.init();
    }

    async init() {
        try {
            // Setup event listeners
            this.fullscreenBtn.addEventListener('click', () => this.toggleFullscreen());
            this.backToGridBtn.addEventListener('click', () => this.hideSingleStream());
            window.addEventListener('resize', () => this.updateLayout());

            // Load streams
            await this.loadStreams();
            this.createStreamElements();
            this.startStreaming();
            this.updateLayout();
            this.hideLoading();
            
            // Start status monitoring
            this.startStatusMonitoring();
        } catch (error) {
            console.error('Initialization error:', error);
            this.showError('Failed to initialize stream viewer');
        }
    }

    cleanup() {
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
        }
        this.stopStreaming();
    }

    async loadStreams() {
        try {
            const response = await fetch('/api/streams');
            if (!response.ok) throw new Error('Failed to load streams');
            const data = await response.json();
            this.streams = data.streams || [];
            
            // Update FPS from server
            if (data.fps) {
                this.fps = data.fps;
            }
        } catch (error) {
            console.error('Error loading streams:', error);
            throw error;
        }
    }

    async startStatusMonitoring() {
        // Initial status check
        await this.checkStreamStatus();
        
        // Start periodic status checks
        this.statusCheckInterval = setInterval(() => this.checkStreamStatus(), 5000);
    }
    
    async checkStreamStatus() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) throw new Error('Failed to fetch status');
            const status = await response.json();
            
            Object.entries(status).forEach(([index, streamStatus]) => {
                this.updateStreamStatus(parseInt(index), streamStatus);
            });
        } catch (error) {
            console.error('Error checking stream status:', error);
        }
    }
    
    updateStreamStatus(index, status) {
        // Update grid view status
        const container = this.streamGrid.children[index];
        if (container) {
            // Remove old status classes
            container.classList.remove('status-error', 'status-connecting', 'status-reconnecting', 'status-cooldown');
            
            // Add new status class
            if (status.status !== 'connected') {
                container.classList.add(`status-${status.status}`);
            }
            
            // Update status indicator
            let statusIndicator = container.querySelector('.stream-status');
            if (!statusIndicator) {
                statusIndicator = document.createElement('div');
                statusIndicator.className = 'stream-status';
                container.appendChild(statusIndicator);
            }
            
            // Update status text
            let statusText = status.status;
            if (status.status === 'error') {
                statusText += ` (${status.errors} errors)`;
            }
            if (status.last_frame_age !== null) {
                statusText += ` - ${status.last_frame_age}s ago`;
            }
            statusIndicator.textContent = statusText;
        }

        // Update single stream view status if this is the current stream
        if (this.currentSingleStreamIndex === index) {
            const singleViewStatus = this.singleStreamView.querySelector('.stream-status');
            if (singleViewStatus) {
                singleViewStatus.textContent = status.status;
                singleViewStatus.className = `stream-status status-${status.status}`;
            }
        }
    }

    createStreamElements() {
        this.streamGrid.innerHTML = '';
        this.streamGrid.setAttribute('data-count', this.streams.length);

        this.streams.forEach((stream, index) => {
            const container = document.createElement('div');
            container.className = 'stream-container';
            container.setAttribute('data-index', index);
            
            const title = document.createElement('div');
            title.className = 'stream-title';
            title.textContent = stream.name;
            
            const img = document.createElement('img');
            img.className = 'stream-image';
            img.alt = stream.name;
            
            const status = document.createElement('div');
            status.className = 'stream-status';
            status.textContent = 'Connecting...';
            
            container.appendChild(title);
            container.appendChild(img);
            container.appendChild(status);
            
            // Add click handler for single stream view
            container.addEventListener('click', () => this.showSingleStream(index));
            
            this.streamGrid.appendChild(container);
        });
    }

    async fetchFrame(index) {
        try {
            const response = await fetch(`/api/frame/${index}`);
            if (!response.ok) throw new Error('Failed to fetch frame');
            const data = await response.json();
            return data.frame;
        } catch (error) {
            console.error(`Error fetching frame for stream ${index}:`, error);
            return null;
        }
    }

    updateStreamImage(index, frame) {
        if (this.currentSingleStreamIndex === index) {
            // Update single stream view image
            if (this.singleStreamImage && frame) {
                this.singleStreamImage.src = `data:image/jpeg;base64,${frame}`;
            }
        } else {
            // Update grid view image
            const img = this.streamGrid.children[index]?.querySelector('img');
            if (img && frame) {
                img.src = `data:image/jpeg;base64,${frame}`;
            }
        }
    }

    async streamLoop(index) {
        if (!this.frameRequests.has(index)) {
            return; // Streaming stopped for this index
        }

        try {
            const frame = await this.fetchFrame(index);
            if (frame) {
                this.updateStreamImage(index, frame);
            }
        } catch (error) {
            console.error(`Error in stream loop for index ${index}:`, error);
        }

        // Schedule next frame using setTimeout for precise timing
        if (this.frameRequests.has(index)) {
            this.frameTimers.set(index,
                setTimeout(() => this.streamLoop(index), 1000 / this.fps)
            );
        }
    }

    startStreaming() {
        this.streams.forEach((_, index) => {
            if (!this.frameRequests.has(index)) {
                this.frameRequests.set(index, true);
                this.streamLoop(index);
            }
        });
    }

    stopStreaming() {
        // Clear all frame requests and timers
        this.frameRequests.clear();
        this.frameTimers.forEach((timer) => clearTimeout(timer));
        this.frameTimers.clear();
    }

    showSingleStream(index) {
        this.currentSingleStreamIndex = index;
        const stream = this.streams[index];
        
        // Update single stream view
        this.singleStreamTitle.textContent = stream.name;
        this.singleStreamView.classList.remove('hidden');
        
        // Create status indicator for single view if it doesn't exist
        const streamContent = this.singleStreamView.querySelector('.stream-content');
        if (!streamContent.querySelector('.stream-status')) {
            const status = document.createElement('div');
            status.className = 'stream-status';
            streamContent.appendChild(status);
        }
        
        // Stop streaming all other streams
        this.stopStreaming();
        
        // Start streaming only the selected stream
        this.frameRequests.set(index, true);
        this.streamLoop(index);
    }

    hideSingleStream() {
        this.singleStreamView.classList.add('hidden');
        this.currentSingleStreamIndex = null;
        
        // Restart streaming all streams
        this.startStreaming();
    }

    updateLayout() {
        // Layout is handled by CSS grid
        this.streamGrid.setAttribute('data-count', this.streams.length);
    }

    async toggleFullscreen() {
        if (!document.fullscreenElement) {
            try {
                await this.container.requestFullscreen();
                this.container.classList.add('fullscreen');
            } catch (error) {
                console.error('Error attempting to enable fullscreen:', error);
            }
        } else {
            if (document.exitFullscreen) {
                await document.exitFullscreen();
                this.container.classList.remove('fullscreen');
            }
        }
    }

    hideLoading() {
        this.loadingOverlay.style.display = 'none';
    }

    showError(message) {
        this.loadingOverlay.innerHTML = `
            <div class="error-message">
                <p>Error: ${message}</p>
                <button onclick="location.reload()">Retry</button>
            </div>
        `;
    }
}

// Initialize the stream viewer when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new StreamViewer();
});
