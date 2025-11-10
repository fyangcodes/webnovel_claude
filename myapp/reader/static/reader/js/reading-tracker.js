/**
 * Reading Progress Tracker
 *
 * Tracks reading engagement metrics for chapters:
 * - Time spent on page (duration in seconds)
 * - Whether user reached the end of the chapter (completion)
 *
 * Sends data to the server when user leaves the page using navigator.sendBeacon()
 * for reliable delivery even during page unload.
 */

class ReadingTracker {
    constructor() {
        this.startTime = null;
        this.viewEventId = null;
        this.apiUrl = null;
        this.contentElement = null;
        this.hasReachedEnd = false;
        this.isTracking = false;
        this.lastSentTime = 0;
        this.minUpdateInterval = 10000; // Send updates max once per 10 seconds
    }

    /**
     * Initialize the tracker
     * @param {number|null} viewEventId - The ViewEvent ID from Django
     * @param {string} apiUrl - URL for the reading progress API
     * @param {string} contentSelector - CSS selector for the chapter content element
     */
    init(viewEventId, apiUrl, contentSelector = '#chapter-content') {
        // Validate inputs
        if (!viewEventId || !apiUrl) {
            console.log('ReadingTracker: No view_event_id or API URL provided, tracking disabled');
            return;
        }

        this.viewEventId = viewEventId;
        this.apiUrl = apiUrl;
        this.contentElement = document.querySelector(contentSelector);

        if (!this.contentElement) {
            console.warn(`ReadingTracker: Content element "${contentSelector}" not found`);
            return;
        }

        // Start tracking
        this.startTracking();
        console.log('ReadingTracker: Initialized for view_event_id:', this.viewEventId);
    }

    /**
     * Start tracking user activity
     */
    startTracking() {
        if (this.isTracking) return;

        this.isTracking = true;
        this.startTime = Date.now();

        // Set up scroll detection for completion tracking
        this.setupScrollTracking();

        // Send data when user leaves the page
        window.addEventListener('beforeunload', () => this.sendProgress());

        // Handle page visibility changes (mobile, tab switching)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.sendProgress();
            }
        });

        // Periodic save (every 30 seconds while reading)
        this.saveInterval = setInterval(() => {
            if (!document.hidden) {
                this.sendProgress(false); // false = don't stop tracking
            }
        }, 30000);
    }

    /**
     * Set up scroll tracking to detect if user reached the end
     */
    setupScrollTracking() {
        // Use IntersectionObserver for better performance
        if ('IntersectionObserver' in window) {
            // Create a sentinel element at the very end of content
            const sentinel = document.createElement('div');
            sentinel.id = 'reading-tracker-sentinel';
            sentinel.style.height = '1px';
            sentinel.style.width = '100%';
            sentinel.style.pointerEvents = 'none'; // Don't interfere with user interactions
            this.contentElement.appendChild(sentinel);

            const observer = new IntersectionObserver(
                (entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting && !this.hasReachedEnd) {
                            this.hasReachedEnd = true;
                            console.log('ReadingTracker: User reached end of content (IntersectionObserver)');
                            this.sendProgress();
                        }
                    });
                },
                {
                    threshold: 0.0, // Trigger as soon as any part is visible
                    rootMargin: '0px 0px -50px 0px' // Trigger 50px before actual bottom
                }
            );

            observer.observe(sentinel);

            // Also use scroll-based detection as backup
            this.setupScrollBackup();
        } else {
            // Fallback: use scroll event for older browsers
            this.setupScrollBackup();
        }
    }

    /**
     * Scroll-based detection as backup method
     */
    setupScrollBackup() {
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                this.checkScrollPosition();
            }, 150);
        }, { passive: true });
    }

    /**
     * Check if user has scrolled near the bottom (fallback method)
     */
    checkScrollPosition() {
        if (this.hasReachedEnd) return;

        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight;

        // Consider "reached end" if within 100px of bottom
        if (scrollTop + windowHeight >= documentHeight - 100) {
            this.hasReachedEnd = true;
            console.log('ReadingTracker: User reached end (scroll detection)');
            this.sendProgress();
        }
    }

    /**
     * Calculate time spent reading (in seconds)
     */
    getDuration() {
        if (!this.startTime) return 0;
        return Math.floor((Date.now() - this.startTime) / 1000);
    }

    /**
     * Send reading progress to server
     * @param {boolean} isUnloading - Whether page is unloading (use sendBeacon)
     */
    sendProgress(isUnloading = true) {
        const duration = this.getDuration();

        // Don't send if duration is too short (< 3 seconds)
        if (duration < 3) {
            return;
        }

        // Rate limiting: don't send updates more than once per 10 seconds
        const now = Date.now();
        if (!isUnloading && (now - this.lastSentTime) < this.minUpdateInterval) {
            return;
        }

        const data = {
            view_event_id: this.viewEventId,
            duration: duration,
            completed: this.hasReachedEnd
        };

        console.log('ReadingTracker: Sending progress:', data);

        try {
            if (isUnloading && navigator.sendBeacon) {
                // Use sendBeacon for reliable delivery during page unload
                const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
                const sent = navigator.sendBeacon(this.apiUrl, blob);
                if (sent) {
                    console.log('ReadingTracker: Progress sent via sendBeacon');
                }
            } else {
                // Use fetch for periodic updates (works with CSRF token if needed)
                fetch(this.apiUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data),
                    keepalive: true // Keep connection alive during unload
                }).then(response => {
                    if (response.ok) {
                        console.log('ReadingTracker: Progress sent via fetch');
                        this.lastSentTime = now;
                    }
                }).catch(error => {
                    console.error('ReadingTracker: Error sending progress:', error);
                });
            }
        } catch (error) {
            console.error('ReadingTracker: Error in sendProgress:', error);
        }
    }

    /**
     * Stop tracking and clean up
     */
    stop() {
        if (this.saveInterval) {
            clearInterval(this.saveInterval);
        }
        this.sendProgress();
        this.isTracking = false;
    }
}

// Create global instance
window.readingTracker = new ReadingTracker();
