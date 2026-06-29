// Simple theme toggle with persistence
(function() {
    'use strict';
    
    // Get current theme from URL or localStorage
    function getCurrentTheme() {
        const hash = window.location.hash;
        if (hash === '#dark') return 'dark';
        if (hash === '#light') return 'light';
        
        const saved = localStorage.getItem('preferredTheme');
        if (saved === 'dark' || saved === 'light') return saved;
        
        return 'dark'; // Default to dark
    }
    
    // Apply theme
    function applyTheme(theme) {
        // Set data attribute on html element
        document.documentElement.setAttribute('data-theme', theme);
        document.body.className = `theme-${theme}`;
        
        // Update toggle button
        const toggleBtn = document.querySelector('.theme-toggle-btn');
        if (toggleBtn) {
            if (theme === 'dark') {
                // In dark mode, show moon (click to go light)
                toggleBtn.innerHTML = `
                    <span class="btn-icon">🌙</span>
                    <span class="btn-label">Light</span>
                `;
                toggleBtn.dataset.theme = 'dark';
            } else {
                // In light mode, show sun (click to go dark)
                toggleBtn.innerHTML = `
                    <span class="btn-icon">☀️</span>
                    <span class="btn-label">Dark</span>
                `;
                toggleBtn.dataset.theme = 'light';
            }
        }
        
        // Store preference
        localStorage.setItem('preferredTheme', theme);
        
        // Update URL hash
        if (window.location.hash !== `#${theme}`) {
            history.pushState(null, null, `#${theme}`);
        }
        
        console.log(`🎨 Theme applied: ${theme}`);
    }
    
    // Toggle theme
    function toggleTheme() {
        const current = getCurrentTheme();
        const next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next);
    }
    
    // Initialize
    function init() {
        const theme = getCurrentTheme();
        applyTheme(theme);
        
        // Add toggle function to global scope
        window.toggleTheme = toggleTheme;
        
        // Listen for hash changes
        window.addEventListener('hashchange', function() {
            const hash = window.location.hash;
            if (hash === '#dark') applyTheme('dark');
            else if (hash === '#light') applyTheme('light');
        });
        
        console.log('✅ Theme system initialized');
    }
    
    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();