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
        } else {
            // Switch to dark mode
            document.documentElement.classList.add('dark');
            localStorage.theme = 'dark';
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
    // Generic dropdown handler
    function createDropdown(toggleId, dropdownId) {
        const toggle = document.getElementById(toggleId);
        const dropdown = document.getElementById(dropdownId);

        if (!toggle || !dropdown) return;

        // Toggle dropdown on button click
        toggle.addEventListener('click', function (e) {
            e.stopPropagation();
            dropdown.classList.toggle('hidden');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function (e) {
            if (!dropdown.classList.contains('hidden') &&
                !dropdown.contains(e.target) &&
                e.target !== toggle) {
                dropdown.classList.add('hidden');
            }
        });

        // Close dropdown when pressing Escape
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !dropdown.classList.contains('hidden')) {
                dropdown.classList.add('hidden');
            }
        });
    }

    // Initialize dropdowns
    createDropdown('language-toggle', 'language-dropdown');
    createDropdown('genres-toggle', 'genres-dropdown');
})();