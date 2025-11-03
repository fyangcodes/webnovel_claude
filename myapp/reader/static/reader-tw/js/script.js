// <!-- Theme Switcher Script -->
(function () {
    const themeToggle = document.getElementById('theme-toggle');
    const moonIcon = document.getElementById('theme-icon-moon');
    const sunIcon = document.getElementById('theme-icon-sun');

    // Update icon based on current theme
    function updateIcon() {
        if (document.documentElement.classList.contains('dark')) {
            moonIcon.style.display = 'none';
            sunIcon.style.display = 'inline-block';
        } else {
            moonIcon.style.display = 'inline-block';
            sunIcon.style.display = 'none';
        }
    }

    // Initialize icon on page load
    updateIcon();

    // Toggle theme on button click
    themeToggle.addEventListener('click', function () {
        if (document.documentElement.classList.contains('dark')) {
            // Switch to light mode
            document.documentElement.classList.remove('dark');
            localStorage.theme = 'light';
            console.log('Theme changed to:', localStorage.theme);
        } else {
            // Switch to dark mode
            document.documentElement.classList.add('dark');
            localStorage.theme = 'dark';
            console.log('Theme changed to:', localStorage.theme);
        }
        updateIcon();
    });
})();

// < !--Auto - hide Navbar Script-- >
(function () {
    let lastScrollTop = 0;
    let scrollThreshold = 5; // Minimum scroll distance to trigger hide/show
    const navbar = document.querySelector('.navbar');

    window.addEventListener('scroll', function () {
        let scrollTop = window.pageYOffset || document.documentElement.scrollTop;

        // Don't hide navbar when at the top of the page
        if (scrollTop <= 100) {
            navbar.classList.remove('navbar-hidden');
            return;
        }

        // Check scroll direction
        if (Math.abs(scrollTop - lastScrollTop) > scrollThreshold) {
            if (scrollTop > lastScrollTop) {
                // Scrolling down - hide navbar
                navbar.classList.add('navbar-hidden');
            } else {
                // Scrolling up - show navbar
                navbar.classList.remove('navbar-hidden');
            }
            lastScrollTop = scrollTop;
        }
    }, { passive: true });
})();

// Dropdown Menu Script
(function () {
    const dropdowns = [
        { toggleId: 'language-toggle', dropdownId: 'language-dropdown' },
        { toggleId: 'genres-toggle', dropdownId: 'genres-dropdown' }
    ];

    // Store all dropdown elements
    const allDropdowns = [];

    // Close all dropdowns
    function closeAllDropdowns() {
        allDropdowns.forEach(dropdown => {
            dropdown.classList.add('hidden');
        });
    }

    // Initialize each dropdown
    dropdowns.forEach(({ toggleId, dropdownId }) => {
        const toggle = document.getElementById(toggleId);
        const dropdown = document.getElementById(dropdownId);

        if (!toggle || !dropdown) return;

        // Store dropdown reference
        allDropdowns.push(dropdown);

        // Toggle dropdown on button click
        toggle.addEventListener('click', function (e) {
            e.stopPropagation();

            // Close all other dropdowns first
            allDropdowns.forEach(d => {
                if (d !== dropdown) {
                    d.classList.add('hidden');
                }
            });

            // Toggle current dropdown
            dropdown.classList.toggle('hidden');
        });
    });

    // Close all dropdowns when clicking anywhere on the page
    document.addEventListener('click', function (e) {
        // Check if click is outside all dropdowns
        const clickedInsideDropdown = allDropdowns.some(dropdown =>
            dropdown.contains(e.target)
        );

        if (!clickedInsideDropdown) {
            closeAllDropdowns();
        }
    });

    // Close all dropdowns when pressing Escape
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeAllDropdowns();
        }
    });

    // Close dropdowns before page navigation (back/forward/refresh)
    window.addEventListener('beforeunload', function () {
        closeAllDropdowns();
    });

    // Close dropdowns when using browser back/forward buttons
    window.addEventListener('pageshow', function (e) {
        // If page is loaded from cache (back/forward navigation)
        if (e.persisted) {
            closeAllDropdowns();
        }
    });

    // Close dropdowns when page becomes visible again (tab switching)
    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            closeAllDropdowns();
        }
    });
})();