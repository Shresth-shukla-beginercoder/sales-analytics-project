// Theme Toggle
(function() {
    const THEME_KEY = 'sales-analytics-theme';

    // Set the theme attribute and notify the page (charts etc. listen for 'themechange')
    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: theme } }));
    }

    // Initialize theme on page load
    function initTheme() {
        const savedTheme = localStorage.getItem(THEME_KEY);

        if (savedTheme) {
            // User has a saved preference
            setTheme(savedTheme);
        } else {
            // Check system preference
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            if (prefersDark) {
                setTheme('dark');
            }
        }
    }

    // Toggle theme
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

        setTheme(newTheme);
        localStorage.setItem(THEME_KEY, newTheme);

        // Optional: Add a brief animation
        const btn = document.getElementById('themeToggle');
        if (btn) {
            btn.style.transform = 'rotate(360deg) scale(1.1)';
            setTimeout(() => {
                btn.style.transform = '';
            }, 300);
        }
    }

    // Initialize on DOM load
    initTheme();

    // Wait for DOM to be fully loaded before attaching event
    document.addEventListener('DOMContentLoaded', function() {
        const toggleBtn = document.getElementById('themeToggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', toggleTheme);
        }
    });

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        // Only update if user hasn't set a manual preference
        if (!localStorage.getItem(THEME_KEY)) {
            setTheme(e.matches ? 'dark' : 'light');
        }
    });
})();
