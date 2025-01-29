class StreamViewer {
    constructor() {
        this.streams = [];
        this.streamGrid = document.getElementById('streamGrid');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.fullscreenBtn = document.getElementById('fullscreenBtn');
        this.container = document.querySelector('.container');
        this.frameRequests = new Map();
        this.currentSingleStreamIndex = null;
        
        // Single stream view elements
        this.singleStreamView = document.getElementById('singleStreamView');
        this.singleStreamTitle = document.getElementById('singleStreamTitle');
        this.singleStreamImage = document.getElementById('singleStreamImage');
        this.backToGridBtn = document.getElementById('backToGrid');
        
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
        } catch (error) {
            console.error('Initialization error:', error);
            this.showError('Failed to initialize stream viewer');
        }
    }

    async loadStreams() {
        try {
            const response = await fetch('/api/streams');
            if (!response.ok) throw new Error('Failed to load streams');
            this.streams = await response.json();
        } catch (error) {
            console.error('Error loading streams:', error);
            throw error;
        }
    }

    createStreamElements() {
        this.streamGrid.innerHTML = '';
        this.streamGrid.setAttribute('data-count', this.streams.length);

        this.streams.forEach((stream, index) => {
            const container = document.createElement('div');
            container.className = 'stream-container';
            
            const title = document.createElement('div');
            title.className = 'stream-title';
            title.textContent = stream.name;
            
            const img = document.createElement('img');
            img.className = 'stream-image';
            img.alt = stream.name;
            
            container.appendChild(title);
            container.appendChild(img);
            
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

        const frame = await this.fetchFrame(index);
        this.updateStreamImage(index, frame);

        // Schedule next frame
        this.frameRequests.set(index, 
            requestAnimationFrame(() => this.streamLoop(index))
        );
    }

    startStreaming() {
        this.streams.forEach((_, index) => {
            this.frameRequests.set(index, true);
            this.streamLoop(index);
        });
    }

    stopStreaming() {
        this.frameRequests.forEach((requestId, index) => {
            cancelAnimationFrame(requestId);
            this.frameRequests.delete(index);
        });
    }

    showSingleStream(index) {
        this.currentSingleStreamIndex = index;
        const stream = this.streams[index];
        
        // Update single stream view
        this.singleStreamTitle.textContent = stream.name;
        this.singleStreamView.classList.remove('hidden');
        
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
