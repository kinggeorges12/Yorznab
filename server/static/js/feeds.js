

function hideEditor() {
    const editorContainer = document.getElementById('editor-container');
    const mainPage = document.getElementById('main-page');
    editorContainer.style.display = 'none';
    mainPage.style.display = 'block';
};

function showEditor() {
    const editorContainer = document.getElementById('editor-container');
    const mainPage = document.getElementById('main-page');
    editorContainer.style.display = 'block';
    mainPage.style.display = 'none';
};

async function publishFeed(event, feedName, url, iconId) {
    event.preventDefault();
    
    const icon = document.getElementById(iconId);
    if (!icon) {
        console.error('Feed item not found:', feedName);
        return;
    }
    
    // Get CSRF token from the span element
    const spanElement = event.currentTarget;
    const csrfToken = spanElement.getAttribute('data-csrf');
    
    // Get error div
    const errorDiv = document.getElementById('publish-error');

    const originalText = icon.textContent;
    
    // Loading state
    icon.textContent = '⏳';
    let dots = 0;
    const loadingInterval = setInterval(() => {
        dots = (dots + 1) % 4;
        icon.textContent = '⏳' + '.'.repeat(dots);
    }, 500);
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            }
        });
        
        // Handle 204 No Content (success with no body)
        if (response.status === 204) {
            clearInterval(loadingInterval);
            icon.textContent = '✅';
            
            // Clear and hide error div on success
            if (errorDiv) {
                errorDiv.innerHTML = '';
                errorDiv.style.display = 'none';
            }
            
            // Get new CSRF token from response headers
            const newCsrfToken = response.headers.get('X-CSRF-Token');
            if (newCsrfToken) {
                spanElement.setAttribute('data-csrf', newCsrfToken);
            }
            
            setTimeout(() => {
                icon.textContent = originalText;
            }, 10000);
            
            // Refresh status after feed publish
            const countdownElement = document.getElementById('countdown');
            if (countdownElement) {
                const statusEndpoint = countdownElement.dataset.status;
                checkStatus(statusEndpoint);
            }
            
            return;
        }
        
        // Handle other successful responses with JSON body
        if (!response.ok) {
            let errorMessage = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || JSON.stringify(errorData);
            } catch (e) {}
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        
        clearInterval(loadingInterval);
        icon.textContent = '✅';
        
        // Clear and hide error div on success
        if (errorDiv) {
            errorDiv.innerHTML = '';
            errorDiv.style.display = 'none';
        }
        
        setTimeout(() => {
            icon.textContent = originalText;
        }, 10000);
        
        // Refresh status after feed publish
        const countdownElement = document.getElementById('countdown');
        if (countdownElement) {
            const statusEndpoint = countdownElement.dataset.status;
            checkStatus(statusEndpoint);
        }
        
    } catch (error) {
        clearInterval(loadingInterval);
        icon.textContent = '❌';
        
        setTimeout(() => {
            icon.textContent = originalText;
        }, 3000);
        
        // Append error to error div
        if (errorDiv) {
            const errorMsg = error.detail || error.message || 'An unknown error occurred';
            errorDiv.style.display = 'block';
            errorDiv.innerHTML += `<div style="word-break: break-all;white-space: pre-wrap;">${errorMsg.replace(/\n/g, '<br>')}</div>`;
        }
        
        console.error('Error publishing feed:', error);
    }
}

async function refreshFeed(event, feedName, url, iconId) {
    event.preventDefault();
    
    const icon = document.getElementById(iconId);
    if (!icon) {
        console.error('Feed item not found:', feedName);
        return;
    }
    
    const originalText = icon.textContent;
    
    // Loading state
    icon.textContent = '⏳';
    let dots = 0;
    const loadingInterval = setInterval(() => {
        dots = (dots + 1) % 4;
        icon.textContent = '⏳' + '.'.repeat(dots);
    }, 500);
    
    try {
        const response = await fetch(url);
        
        if (!response.ok) {
            let errorMessage = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || JSON.stringify(errorData);
            } catch (e) {}
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        
        clearInterval(loadingInterval);
        icon.textContent = '✅';
        
        setTimeout(() => {
            icon.textContent = originalText;
        }, 10000);
        
        // Refresh status after feed refresh
        const countdownElement = document.getElementById('countdown');
        if (countdownElement) {
            const statusEndpoint = countdownElement.dataset.status;
            checkStatus(statusEndpoint);
        }
        
    } catch (error) {
        clearInterval(loadingInterval);
        icon.textContent = '❌';
        
        setTimeout(() => {
            icon.textContent = originalText;
        }, 3000);
    }
}

async function deleteFeed(event, feedName, url, itemId, csrfToken) {
    event.preventDefault();
    
    const item = document.getElementById(itemId);
    if (!item) {
        console.error('Feed item not found:', feedName);
        return;
    }

    const confirmed = confirm("Are you sure you want to delete the '" + feedName + "' feed? (You can restore the backup from the config directory)");
    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch(url, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            }
        });
        
        if (!response.ok) {
            let errorMessage = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || JSON.stringify(errorData);
            } catch (e) {}
            throw new Error(errorMessage);
        }
        // fade to 100% transparent over 1 second
        for (let i = 0; i < 10; i++) {
            setTimeout(() => {
                item.style.opacity = 1 - (i / 10);
            }, i * 100);
        }
        setTimeout(() => {
            item.remove(); // Remove the feed item
        }, 1000);
        
    } catch (error) {
        alert("Failed to delete the feed: " + error.message);
        console.error('Error deleting feed: ', error);
    }
}

/**
 * Handle webhook enable/disable button clicks
 */
async function enableWebhook(button) {
    const errorDivId = button.getAttribute('data-error');
    const errorDiv = errorDivId ? document.getElementById(errorDivId) : null;
    
    // Clear previous error
    if (errorDiv) {
        errorDiv.style.display = 'none';
        errorDiv.textContent = '';
    }
    
    const csrfToken = button.getAttribute('data-csrf');
    const actionUrl = button.getAttribute('action');
    
    try {
        const response = await fetch(actionUrl || window.location.href, {
            method: 'POST',
            headers: {
                'X-CSRF-Token': csrfToken || document.querySelector('input[name="csrf_token"]')?.value || ''
            }
        });
        
        // Handle 204 No Content (success with no body)
        if (response.status === 204) {
            button.disabled = true;
            button.textContent = '✅ Webhook enabled successfully!';
            return;
        }
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            button.disabled = true;
            button.textContent = '✅ Webhook enabled successfully!';
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
        console.error('Webhook action error:', error);
        if (errorDiv) {
            errorDiv.style.display = 'block';
            errorDiv.textContent = 'Network error. Please try again.';
        } else {
            alert('Network error. Please try again.');
        }
    }
}