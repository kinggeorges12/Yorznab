// Simple theme toggle with persistence
(function() {
    'use strict';
    
    function getCurrentTheme() {
        const hash = window.location.hash;
        if (hash === '#dark') return 'dark';
        if (hash === '#light') return 'light';
        
        const saved = localStorage.getItem('preferredTheme');
        if (saved === 'dark' || saved === 'light') return saved;
        
        return 'dark';
    }
    
    function applyTheme(theme) {
        // Set data attribute on html element
        document.documentElement.setAttribute('data-theme', theme);
        
        // Only set body className if body exists
        if (document.body) {
            document.body.className = `theme-${theme}`;
        }
        
        // Set background immediately
        document.documentElement.style.backgroundColor = theme === 'light' ? '#ffffff' : '#1a1a1a';
        
        // Store preference
        localStorage.setItem('preferredTheme', theme);
        
        // Update URL hash
        if (window.location.hash !== `#${theme}`) {
            history.pushState(null, null, `#${theme}`);
        }
        
        console.log(`🎨 Theme applied: ${theme}`);
    }
    
    function toggleTheme() {
        const current = getCurrentTheme();
        const next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        updateToggleButton();
    }
    
    function updateToggleButton() {
        const toggleBtn = document.querySelector('.theme-toggle-btn');
        if (!toggleBtn) return;
        
        const theme = getCurrentTheme();
        if (theme === 'dark') {
            toggleBtn.innerHTML = `
                <span class="btn-icon">🌙</span>
                <span class="btn-label">Light</span>
            `;
            toggleBtn.dataset.theme = 'dark';
        } else {
            toggleBtn.innerHTML = `
                <span class="btn-icon">☀️</span>
                <span class="btn-label">Dark</span>
            `;
            toggleBtn.dataset.theme = 'light';
        }
    }
    
    // Run IMMEDIATELY
    const theme = getCurrentTheme();
    applyTheme(theme);
    
    // Make toggle function globally available
    window.toggleTheme = toggleTheme;
    
    // Listen for hash changes
    window.addEventListener('hashchange', function() {
        const hash = window.location.hash;
        if (hash === '#dark') applyTheme('dark');
        else if (hash === '#light') applyTheme('light');
        updateToggleButton();
    });
    
    // Update toggle button when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            updateToggleButton();
        });
    } else {
        updateToggleButton();
    }
    
    console.log('✅ Theme system initialized');
})();