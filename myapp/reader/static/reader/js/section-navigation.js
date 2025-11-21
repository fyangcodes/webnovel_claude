/**
 * Section-Aware Navigation JavaScript
 * Provides AJAX navigation, infinite scroll, and analytics for section-scoped pages
 */

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        infiniteScrollEnabled: true,
        infiniteScrollThreshold: 300, // pixels from bottom
        ajaxNavigationEnabled: true,
        analyticsEnabled: true,
        debugMode: false
    };

    // State management
    const state = {
        currentSection: null,
        currentLanguage: null,
        isLoading: false,
        hasMorePages: true,
        currentPage: 1,
        navigationHistory: []
    };

    /**
     * Initialize section navigation features
     */
    function init() {
        // Extract current section and language from page context
        extractPageContext();

        // Initialize features
        if (CONFIG.infiniteScrollEnabled) {
            initInfiniteScroll();
        }

        if (CONFIG.ajaxNavigationEnabled) {
            initAjaxNavigation();
        }

        if (CONFIG.analyticsEnabled) {
            initAnalytics();
        }

        debug('Section navigation initialized', state);
    }

    /**
     * Extract section and language context from the page
     */
    function extractPageContext() {
        // Try to get from meta tags first
        const sectionMeta = document.querySelector('meta[name="section-slug"]');
        const languageMeta = document.querySelector('meta[name="language-code"]');

        if (sectionMeta) {
            state.currentSection = sectionMeta.getAttribute('content');
        }

        if (languageMeta) {
            state.currentLanguage = languageMeta.getAttribute('content');
        }

        // Fallback: extract from URL
        if (!state.currentSection || !state.currentLanguage) {
            const pathMatch = window.location.pathname.match(/^\/([a-z]{2})\/([a-z-]+)\//);
            if (pathMatch) {
                state.currentLanguage = state.currentLanguage || pathMatch[1];
                state.currentSection = state.currentSection || pathMatch[2];
            }
        }

        debug('Page context extracted:', {
            section: state.currentSection,
            language: state.currentLanguage
        });
    }

    /**
     * Initialize infinite scroll for book lists
     */
    function initInfiniteScroll() {
        // Only activate on book list pages
        const bookGrid = document.querySelector('[data-infinite-scroll="true"]');
        if (!bookGrid) {
            debug('No infinite scroll container found');
            return;
        }

        const loadingIndicator = createLoadingIndicator();
        document.body.appendChild(loadingIndicator);

        window.addEventListener('scroll', debounce(function() {
            if (state.isLoading || !state.hasMorePages) {
                return;
            }

            const scrollPosition = window.innerHeight + window.scrollY;
            const threshold = document.documentElement.scrollHeight - CONFIG.infiniteScrollThreshold;

            if (scrollPosition >= threshold) {
                loadMoreBooks(bookGrid, loadingIndicator);
            }
        }, 200), { passive: true });

        debug('Infinite scroll initialized');
    }

    /**
     * Load more books via AJAX
     */
    function loadMoreBooks(container, loadingIndicator) {
        state.isLoading = true;
        state.currentPage++;

        showLoadingIndicator(loadingIndicator);

        const url = buildNextPageUrl();

        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.text();
        })
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newBooks = doc.querySelectorAll('.book-card');

            if (newBooks.length === 0) {
                state.hasMorePages = false;
                showEndMessage(container);
            } else {
                newBooks.forEach(book => {
                    container.appendChild(book.cloneNode(true));
                });

                // Track analytics
                trackEvent('infinite_scroll', {
                    section: state.currentSection,
                    page: state.currentPage,
                    books_loaded: newBooks.length
                });
            }
        })
        .catch(error => {
            console.error('Failed to load more books:', error);
            state.currentPage--; // Revert page increment
            state.hasMorePages = false;
        })
        .finally(() => {
            state.isLoading = false;
            hideLoadingIndicator(loadingIndicator);
        });
    }

    /**
     * Build URL for next page with section context
     */
    function buildNextPageUrl() {
        const url = new URL(window.location.href);
        url.searchParams.set('page', state.currentPage);
        return url.toString();
    }

    /**
     * Initialize AJAX navigation for section switching
     */
    function initAjaxNavigation() {
        // Intercept section navigation clicks
        document.addEventListener('click', function(e) {
            const link = e.target.closest('a[data-ajax-nav="section"]');
            if (!link) return;

            e.preventDefault();

            const targetUrl = link.getAttribute('href');
            const targetSection = link.getAttribute('data-section-slug');

            navigateToSection(targetUrl, targetSection);
        });

        // Handle browser back/forward
        window.addEventListener('popstate', function(e) {
            if (e.state && e.state.section) {
                navigateToSection(window.location.href, e.state.section, false);
            }
        });

        debug('AJAX navigation initialized');
    }

    /**
     * Navigate to a section via AJAX
     */
    function navigateToSection(url, sectionSlug, updateHistory = true) {
        const mainContent = document.querySelector('main');
        if (!mainContent) return;

        // Show loading state
        mainContent.style.opacity = '0.5';
        mainContent.style.pointerEvents = 'none';

        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newContent = doc.querySelector('main');

            if (newContent) {
                mainContent.innerHTML = newContent.innerHTML;

                // Update state
                state.currentSection = sectionSlug;
                state.currentPage = 1;
                state.hasMorePages = true;

                // Update URL
                if (updateHistory) {
                    history.pushState(
                        { section: sectionSlug },
                        '',
                        url
                    );
                }

                // Update active section in nav
                updateSectionNav(sectionSlug);

                // Track analytics
                trackEvent('section_navigation', {
                    from_section: state.navigationHistory.length > 0
                        ? state.navigationHistory[state.navigationHistory.length - 1]
                        : null,
                    to_section: sectionSlug,
                    method: 'ajax'
                });

                state.navigationHistory.push(sectionSlug);
            }
        })
        .catch(error => {
            console.error('AJAX navigation failed:', error);
            // Fallback to regular navigation
            window.location.href = url;
        })
        .finally(() => {
            mainContent.style.opacity = '1';
            mainContent.style.pointerEvents = 'auto';
        });
    }

    /**
     * Update active state in section navigation
     */
    function updateSectionNav(activeSectionSlug) {
        // Update section nav buttons
        const sectionButtons = document.querySelectorAll('.section-nav-btn');
        sectionButtons.forEach(button => {
            const buttonSectionSlug = button.getAttribute('data-section-slug');

            if (buttonSectionSlug === activeSectionSlug) {
                // This is the active section button
                button.classList.add('active');

                // Update inline background-color if data-section-color exists
                if (button.hasAttribute('data-section-color')) {
                    const borderColor = button.style.borderColor;
                    if (borderColor) {
                        button.style.backgroundColor = borderColor;
                    }
                }
            } else {
                // This is an inactive button
                button.classList.remove('active');

                // Remove background-color for inactive buttons (outline style)
                if (button.hasAttribute('data-section-color')) {
                    button.style.backgroundColor = '';
                }
            }
        });

        // Update search bar placeholder
        updateSearchPlaceholder(activeSectionSlug);
    }

    /**
     * Update search bar placeholder text and form action based on active section
     */
    function updateSearchPlaceholder(sectionSlug) {
        const searchInput = document.querySelector('input[name="q"]');
        const searchForm = searchInput ? searchInput.closest('form') : null;
        if (!searchInput || !searchForm) return;

        // Extract language code from current URL (e.g., /zh/ or /en/fiction/)
        const languageMatch = window.location.pathname.match(/^\/([a-z]{2})\//);
        const languageCode = languageMatch ? languageMatch[1] : 'en';

        if (sectionSlug) {
            // Section-specific search
            const activeButton = document.querySelector(`.section-nav-btn[data-section-slug="${sectionSlug}"]`);
            if (activeButton) {
                const sectionName = activeButton.textContent.trim();
                searchInput.placeholder = `Search in ${sectionName}...`;
                searchForm.action = `/${languageCode}/${sectionSlug}/search/`;
            }
        } else {
            // Welcome page - search all sections
            searchInput.placeholder = 'Search all books...';
            searchForm.action = `/${languageCode}/search/`;
        }
    }

    /**
     * Initialize analytics tracking
     */
    function initAnalytics() {
        // Track page view
        trackPageView();

        // Track time spent in section
        let sectionStartTime = Date.now();

        window.addEventListener('beforeunload', function() {
            const timeSpent = Math.floor((Date.now() - sectionStartTime) / 1000);
            trackEvent('section_time_spent', {
                section: state.currentSection,
                seconds: timeSpent
            });
        });

        // Track section interactions
        document.addEventListener('click', function(e) {
            const bookCard = e.target.closest('.book-card');
            if (bookCard) {
                const bookTitle = bookCard.querySelector('.book-title')?.textContent;
                trackEvent('book_click', {
                    section: state.currentSection,
                    book_title: bookTitle,
                    position: getElementPosition(bookCard)
                });
            }
        });

        debug('Analytics initialized');
    }

    /**
     * Track page view with section context
     */
    function trackPageView() {
        trackEvent('page_view', {
            section: state.currentSection,
            language: state.currentLanguage,
            url: window.location.pathname,
            referrer: document.referrer
        });
    }

    /**
     * Track custom event (integrate with your analytics service)
     */
    function trackEvent(eventName, properties = {}) {
        const event = {
            event: eventName,
            timestamp: new Date().toISOString(),
            section: state.currentSection,
            language: state.currentLanguage,
            ...properties
        };

        debug('Analytics event:', event);

        // Send to analytics service (Google Analytics, Plausible, etc.)
        if (window.gtag) {
            window.gtag('event', eventName, properties);
        } else if (window.plausible) {
            window.plausible(eventName, { props: properties });
        } else {
            // Store locally for development/testing
            const events = JSON.parse(localStorage.getItem('analytics_events') || '[]');
            events.push(event);
            // Keep only last 100 events
            if (events.length > 100) {
                events.shift();
            }
            localStorage.setItem('analytics_events', JSON.stringify(events));
        }
    }

    /**
     * Utility: Create loading indicator
     */
    function createLoadingIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'infinite-scroll-loader';
        indicator.className = 'text-center py-4';
        indicator.style.display = 'none';
        indicator.innerHTML = `
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2 text-muted">Loading more books...</p>
        `;
        return indicator;
    }

    /**
     * Utility: Show loading indicator
     */
    function showLoadingIndicator(indicator) {
        indicator.style.display = 'block';
    }

    /**
     * Utility: Hide loading indicator
     */
    function hideLoadingIndicator(indicator) {
        indicator.style.display = 'none';
    }

    /**
     * Utility: Show end of results message
     */
    function showEndMessage(container) {
        const message = document.createElement('div');
        message.className = 'text-center py-4 text-muted';
        message.innerHTML = `
            <i class="fas fa-check-circle fa-2x mb-2"></i>
            <p>You've reached the end of the list</p>
        `;
        container.after(message);
    }

    /**
     * Utility: Get element position in list
     */
    function getElementPosition(element) {
        const parent = element.parentElement;
        return Array.from(parent.children).indexOf(element) + 1;
    }

    /**
     * Utility: Debounce function
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Utility: Debug logging
     */
    function debug(...args) {
        if (CONFIG.debugMode) {
            console.log('[SectionNav]', ...args);
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose public API
    window.SectionNavigation = {
        getState: () => ({ ...state }),
        trackEvent,
        navigateToSection,
        config: CONFIG
    };
})();
