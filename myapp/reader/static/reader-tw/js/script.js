// <!-- Theme Switcher Script -->
(function () {
    const themeToggle = document.getElementById('theme-toggle');
    const moonIcon = document.getElementById('theme-icon-moon');
    const sunIcon = document.getElementById('theme-icon-sun');
    const htmlElement = document.documentElement;

    // Initialize theme from localStorage or default to light
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);

    // Toggle theme on button click
    themeToggle.addEventListener('click', function () {
        const currentTheme = htmlElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        setTheme(newTheme);
        localStorage.setItem('theme', newTheme);
    });

    function setTheme(theme) {
        if (theme === 'dark') {
            htmlElement.setAttribute('data-theme', 'dark');
            moonIcon.style.display = 'none';
            sunIcon.style.display = 'inline-block';
        } else {
            htmlElement.setAttribute('data-theme', 'light');
            moonIcon.style.display = 'inline-block';
            sunIcon.style.display = 'none';
        }
    }
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