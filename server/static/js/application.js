// ====== FUNCTION DEFINITIONS ======

/**
 * Toggle password visibility for any password input with toggle button
 */
function togglePasswordVisibility(input, toggleBtn) {
    if (!input || !toggleBtn) return;
    
    const eyeIcon = toggleBtn.querySelector('.eye-icon');
    if (!eyeIcon) return;
    
    toggleBtn.addEventListener('click', function() {
        if (input.type === 'password') {
            input.type = 'text';
            eyeIcon.textContent = '🙈';
            toggleBtn.classList.add('visible');
        } else {
            input.type = 'password';
            eyeIcon.textContent = '👁️';
            toggleBtn.classList.remove('visible');
        }
    });
}

function toggleSettings(settingsId) {
    const settings = document.getElementById(settingsId);
    const mainMenu = document.getElementById('main-menu');
    
    if (settings.style.display === 'none') {
        settings.style.display = 'block';
        mainMenu.style.display = 'none';
    } else {
        settings.style.display = 'none';
        mainMenu.style.display = 'block';
    }
}

// ====== DOM READY EXECUTION ======

document.addEventListener('DOMContentLoaded', function() {
    // Find all password inputs with toggle buttons
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    
    passwordInputs.forEach(function(input) {
        // Find the toggle button next to this input
        const toggleBtn = input.closest('.info-value')?.querySelector('.toggle-btn');
        
        if (toggleBtn) {
            togglePasswordVisibility(input, toggleBtn);
        }
    });
});