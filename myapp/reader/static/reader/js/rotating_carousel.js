/**
 * Rotating Carousel - Ribbon Layout
 * A 3D rotating carousel for displaying books with separated cover ribbon and metadata cards
 */

(function() {
    'use strict';

    /**
     * Initialize carousel for a specific section
     * @param {string} sectionId - Unique identifier for the carousel
     */
    function initCarousel(sectionId) {
        const ribbon = document.querySelector(`[data-carousel-id="${sectionId}"]`);
        if (!ribbon) return;

        const coverItems = ribbon.querySelectorAll('.carousel-cover-item');
        const metadataCards = document.querySelectorAll(`#${sectionId}MetadataLeft .metadata-card`);
        const descriptionCards = document.querySelectorAll(`#${sectionId}DescriptionRight .description-card`);
        const prevBtn = document.getElementById(`${sectionId}Prev`);
        const nextBtn = document.getElementById(`${sectionId}Next`);
        const indicatorsContainer = document.getElementById(`${sectionId}Indicators`);

        if (coverItems.length === 0) return;

        let currentIndex = 0;
        const totalBooks = coverItems.length;

        // Create indicators
        for (let i = 0; i < totalBooks; i++) {
            const indicator = document.createElement('button');
            indicator.classList.add('carousel-indicator');
            if (i === 0) indicator.classList.add('active');
            indicator.addEventListener('click', () => goToSlide(i));
            indicatorsContainer.appendChild(indicator);
        }

        const indicators = indicatorsContainer.querySelectorAll('.carousel-indicator');

        /**
         * Update carousel positions and active cards
         */
        function updateCarousel() {
            coverItems.forEach((item, index) => {
                // Remove all position classes
                item.classList.remove('center', 'left', 'right', 'far-left', 'far-right', 'hidden');

                const position = (index - currentIndex + totalBooks) % totalBooks;

                // Determine position class based on distance from center
                if (position === 0) {
                    item.classList.add('center');
                } else if (position === 1) {
                    item.classList.add('right');
                } else if (position === totalBooks - 1) {
                    item.classList.add('left');
                } else if (position === 2) {
                    item.classList.add('far-right');
                } else if (position === totalBooks - 2) {
                    item.classList.add('far-left');
                } else {
                    item.classList.add('hidden');
                }
            });

            // Update metadata cards
            metadataCards.forEach((card, index) => {
                card.classList.toggle('active', index === currentIndex);
            });

            // Update description cards
            descriptionCards.forEach((card, index) => {
                card.classList.toggle('active', index === currentIndex);
            });

            // Update indicators
            indicators.forEach((indicator, index) => {
                indicator.classList.toggle('active', index === currentIndex);
            });
        }

        /**
         * Go to a specific slide
         * @param {number} index - Slide index
         */
        function goToSlide(index) {
            currentIndex = index;
            updateCarousel();
            resetAutoRotate();
        }

        /**
         * Go to next slide
         */
        function nextSlide() {
            currentIndex = (currentIndex + 1) % totalBooks;
            updateCarousel();
            resetAutoRotate();
        }

        /**
         * Go to previous slide
         */
        function prevSlide() {
            currentIndex = (currentIndex - 1 + totalBooks) % totalBooks;
            updateCarousel();
            resetAutoRotate();
        }

        // Event listeners
        if (prevBtn) prevBtn.addEventListener('click', prevSlide);
        if (nextBtn) nextBtn.addEventListener('click', nextSlide);

        // Click on cover items to navigate to that book
        coverItems.forEach((item, index) => {
            // Prevent click from navigating when not centered (allow navigation when centered)
            item.addEventListener('click', (e) => {
                if (!item.classList.contains('center')) {
                    e.preventDefault();
                    goToSlide(index);
                }
                // If centered, let the link work normally
            });
        });

        // Auto-rotate every 5 seconds
        let autoRotateInterval;

        /**
         * Start auto-rotation
         */
        function startAutoRotate() {
            autoRotateInterval = setInterval(nextSlide, 5000);
        }

        /**
         * Reset auto-rotation timer
         */
        function resetAutoRotate() {
            clearInterval(autoRotateInterval);
            startAutoRotate();
        }

        // Pause auto-rotate on hover
        const carouselContainer = ribbon.closest('.featured-carousel-container');
        if (carouselContainer) {
            carouselContainer.addEventListener('mouseenter', () => {
                clearInterval(autoRotateInterval);
            });

            carouselContainer.addEventListener('mouseleave', () => {
                startAutoRotate();
            });

            // Touch/swipe support for mobile
            let touchStartX = 0;
            let touchEndX = 0;

            carouselContainer.addEventListener('touchstart', (e) => {
                touchStartX = e.changedTouches[0].screenX;
            }, {passive: true});

            carouselContainer.addEventListener('touchend', (e) => {
                touchEndX = e.changedTouches[0].screenX;
                handleSwipe();
            }, {passive: true});

            /**
             * Handle swipe gesture
             */
            function handleSwipe() {
                const swipeThreshold = 50;
                const swipeDistance = touchEndX - touchStartX;

                if (swipeDistance < -swipeThreshold) {
                    // Swipe left - go to next
                    nextSlide();
                } else if (swipeDistance > swipeThreshold) {
                    // Swipe right - go to previous
                    prevSlide();
                }
            }
        }

        // Initialize
        updateCarousel();
        startAutoRotate();
    }

    // Initialize all carousels on page load
    document.addEventListener('DOMContentLoaded', function() {
        // Find all carousel ribbons and initialize them
        const ribbons = document.querySelectorAll('[data-carousel-id]');
        ribbons.forEach(ribbon => {
            const sectionId = ribbon.getAttribute('data-carousel-id');
            if (sectionId) {
                initCarousel(sectionId);
            }
        });

        // Keyboard navigation for the first carousel (if exists)
        const firstRibbon = document.querySelector('[data-carousel-id]');
        if (firstRibbon) {
            const sectionId = firstRibbon.getAttribute('data-carousel-id');
            const prevBtn = document.getElementById(`${sectionId}Prev`);
            const nextBtn = document.getElementById(`${sectionId}Next`);

            document.addEventListener('keydown', (e) => {
                // Only handle if not typing in an input
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    return;
                }

                if (e.key === 'ArrowLeft' && prevBtn) {
                    e.preventDefault();
                    prevBtn.click();
                } else if (e.key === 'ArrowRight' && nextBtn) {
                    e.preventDefault();
                    nextBtn.click();
                }
            });
        }
    });
})();
