// Login Page JavaScript

// ====== GLOBAL FLAGS ======
let isAjaxSubmit = false;

// ====== FUNCTION DEFINITIONS ======

/**
 * Toggle password visibility
 */
function togglePasswordVisibility(input, toggleBtn, eyeIcon) {
    if (!input || !toggleBtn) return;
    
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
    
    // Handle first-time setup
    if (toggleBtn.onload === null) {
        input.value = '';
    } else {
        toggleBtn.click();
    }
}

/**
 * Clear input after traditional form submission
 */
function setupFormClear(form, input) {
    if (!form || !input) return;
    
    form.addEventListener('submit', function(e) {
        // Skip if this is an AJAX submission
        if (isAjaxSubmit) {
            return;
        }
        
        if (input.type === 'text') {
            input.type = 'password';
        } else {
            setTimeout(function() {
                input.value = '';
            }, 100);
        }
    });
}

/**
 * Clear input on page unload
 */
function setupUnloadClear(input) {
    if (!input) return;
    
    window.addEventListener('beforeunload', function() {
        if (input.type === 'text') {
            input.type = 'password';
        } else {
            input.value = '';
        }
    });
}

/**
 * Show error message in the error container
 */
function showError(errorContainer, errorMessage, message) {
    if (!errorContainer) return;
    
    errorContainer.style.display = 'block';
    if (errorMessage && message) {
        errorMessage.textContent = message;
    }
}

/**
 * Hide error message
 */
function hideError(errorContainer) {
    if (errorContainer) {
        errorContainer.style.display = 'none';
    }
}

/**
 * Set loading state on submit button
 */
function setLoadingState(button, isLoading, originalText) {
    if (!button) return;
    
    if (isLoading) {
        button.textContent = 'Logging in...';
        button.disabled = true;
    } else {
        button.textContent = originalText || 'Login';
        button.disabled = false;
    }
}

/**
 * Handle AJAX login form submission
 */
async function handleLoginSubmit(event) {
    event.preventDefault();
    
    // Set flag to prevent traditional clear
    isAjaxSubmit = true;
    
    const form = event.currentTarget;
    const errorContainer = document.querySelector('.error-container');
    const errorMessage = errorContainer?.querySelector('.error-message');
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn?.textContent;
    
    // Hide any previous error
    hideError(errorContainer);
    
    // Get form data
    const formData = new FormData(form);
    const passkey = formData.get('passkey');
    const csrfToken = formData.get('csrf_token');
    
    // Debug log
    console.log('Passkey from FormData:', passkey);
    
    // Validate passkey
    if (!passkey || passkey.trim() === '') {
        showError(errorContainer, errorMessage, 'Please enter your Login Passkey.');
        isAjaxSubmit = false; // Reset flag
        return;
    }
    
    // Set loading state
    setLoadingState(submitBtn, true, originalText);
    
    try {
        // Send request
        const response = await fetch(form.action, {
            method: 'POST',
            headers: {
                'X-CSRF-Token': csrfToken
            },
            body: formData
        });
        
        // Parse JSON response
        const data = await response.json();
        
        // Check if response was successful
        if (response.ok && data.success) {
            // Success - redirect if provided
            console.log('Login successful:', data);
            if (data.redirect) {
                window.location.href = data.redirect;
            } else {
                window.location.reload();
            }
        } else {
            // Show error from response
            const errorMsg = data.error || data.detail || 'Login failed. Please try again.';
            showError(errorContainer, errorMessage, errorMsg);
            setLoadingState(submitBtn, false, originalText);
            isAjaxSubmit = false; // Reset flag
        }
        
    } catch (error) {
        console.error('Network error:', error);
        showError(errorContainer, errorMessage, 'Network error - please check your connection and try again.');
        setLoadingState(submitBtn, false, originalText);
        isAjaxSubmit = false; // Reset flag
    }
}

// ====== DOM READY EXECUTION ======

document.addEventListener('DOMContentLoaded', function() {
    // Get elements
    const input = document.querySelector('input[name="passkey"]');
    const toggleBtn = document.getElementById('toggleBtn');
    const eyeIcon = toggleBtn?.querySelector('.eye-icon');
    const form = document.querySelector('form');
    const loginForm = document.getElementById('loginForm');
    
    // Setup password toggle
    togglePasswordVisibility(input, toggleBtn, eyeIcon);
    
    // Setup form clear
    setupFormClear(form, input);
    
    // Setup unload clear
    setupUnloadClear(input);
    
    // Setup AJAX login
    if (loginForm) {
        loginForm.removeEventListener('submit', handleLoginSubmit);
        loginForm.addEventListener('submit', handleLoginSubmit);
    }
});