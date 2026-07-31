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

function toggleSettings(templateId) {
    const template = document.getElementById(templateId);
    const mainMenu = document.getElementById('main-menu');
    const settings = document.getElementById('settings');
    
    if (settings.style.display === 'none' || settings.innerHTML === '') {
        const clone = document.importNode(template.content, true);
        settings.innerHTML = '';
        settings.appendChild(clone);
        settings.style.display = 'block';
        mainMenu.style.display = 'none';
        // reattach after creating template
        document.querySelectorAll('form.app-settings-form').forEach(function(form) {
            form.addEventListener('submit', onSettingsFormSubmit);
        });
    } else {
        settings.innerHTML = '';
        settings.style.display = 'none';
        mainMenu.style.display = 'block';
    }
}

/**
 * Handle settings form submission event
 */
async function onSettingsFormSubmit(e) {
    e.preventDefault();
    
    const form = e.target;
    const submitBtn = form.querySelector('.app-save-btn');
    if (!submitBtn) return;
    
    // Get error div from data-error attribute
    const errorDivId = submitBtn.getAttribute('data-error');
    const errorDiv = errorDivId ? document.getElementById(errorDivId) : null;
    
    // Clear previous error
    if (errorDiv) {
        errorDiv.style.display = 'none';
        errorDiv.textContent = '';
    }
    
    // Get form data
    const formData = new FormData(form);

    // If any input is empty, use its placeholder as the value
    form.querySelectorAll('input').forEach(function(input) {
        if (input.value === '' && input.placeholder) {
            formData.set(input.name, input.placeholder);
        }
    });

    try {
        const response = await fetch(form.action || window.location.href, {
            method: form.method || 'POST',
            body: formData,
            headers: {
                'X-CSRF-Token': document.querySelector('input[name="csrf_token"]')?.value || ''
            }
        });
        
        // Handle 204 No Content (success with no body)
        if (response.status === 204) {
            window.location.reload();
            return;
        }

        const result = await response.json();
        
        if (response.ok && result.success) {
            window.location.reload();
        } else {
            const errorMsg = result.detail || result.error || result.message || 'An unknown error occurred';
            if (errorDiv) {
                errorDiv.style.display = 'block';
                errorDiv.innerHTML = errorMsg.replace(/\n/g, '<br>');
            } else {
                alert(errorMsg);
            }
        }
    } catch (error) {
        console.error('Form submission error:', error);
        if (errorDiv) {
            errorDiv.style.display = 'block';
            errorDiv.textContent = 'Network error. Please try again.';
        } else {
            alert('Network error. Please try again.');
        }
    }
}

// ====== DOM READY EXECUTION ======

document.addEventListener('DOMContentLoaded', function() {
    
    document.querySelectorAll('input[type="password"]').forEach(function(input) {
        // Find the toggle button next to this input
        const toggleBtn = input.closest('.info-value')?.querySelector('.toggle-btn');
        
        if (toggleBtn) {
            togglePasswordVisibility(input, toggleBtn);
        }
    });
});