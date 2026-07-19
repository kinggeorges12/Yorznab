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

})();