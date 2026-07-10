// Login Page JavaScript

(function() {
    'use strict';

    // Define copyKey globally
    window.copyKey = function(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        // Get the text content, but handle <br> tags properly
        const text = element.innerText || element.textContent;
        
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(function() {
                const originalBg = element.style.background;
                element.style.background = '#bbf7d0';
                setTimeout(function() {
                    element.style.background = originalBg || '';
                }, 500);
            }).catch(function() {
                fallbackCopy(text);
            });
        } else {
            fallbackCopy(text);
        }
    };

    function fallbackCopy(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
        } catch (err) {
            alert('Failed to copy. Please select and copy manually.');
        }
        document.body.removeChild(textarea);
    }

    // Wait for DOM to be ready
    document.addEventListener('DOMContentLoaded', function() {
        // Get elements
        const input = document.querySelector('input[name="passkey"]');
        const toggleBtn = document.getElementById('toggleBtn');
        const eyeIcon = toggleBtn?.querySelector('.eye-icon');
        const form = document.querySelector('form');
        
        // Password toggle functionality
        if (input && toggleBtn) {
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
            
            if (toggleBtn.onload === null) {
                // Clear input on page load
                input.value = '';
            } else {
                // Simulate click to show passkey if first time
                toggleBtn.click();
            }
        }
        
        // Clear input after submit
        if (form && input) {
            form.addEventListener('submit', function() {
                if (input && input.type === 'text') {
                    input.type = 'password';
                } else {
                    setTimeout(function() {
                        input.value = '';
                    }, 100);
                }
            });
        }
        
        // Clear on page unload
        window.addEventListener('beforeunload', function() {
            if (input && input.type === 'text') {
                input.type = 'password';
            } else {
                input.value = '';
            }
        });
    });
})();