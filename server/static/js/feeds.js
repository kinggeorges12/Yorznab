
const guifier_selector = '#guifier'
const guifier_list = {};
let isActive = true;
let statusCheckInterval = null;
let countdownInterval = null;

// Function to check status
async function checkStatus(statusEndpoint) {
    try {
        const data = await fetch(statusEndpoint)
            .catch(error => {
                console.error('Connection failed:', error);
                return null;
            })
            .then(async response => {
                if (response === null) {
                    return { status: 'unhealthy', active: null, label: '🔌 Disconnected' };
                }
                return await response.json();
            });
        
        // Update active state
        isActive = data.active;
        
        // Update status indicator if it exists
        const statusDot = document.getElementById('status-dot');
        const statusLabel = document.getElementById('status-label');
        if (statusDot && data.status) {
            statusDot.className = 'status-dot ' + (data.status === 'healthy' ? 'healthy' : 'unhealthy');
        }
        if (statusLabel && data.label) {
            statusLabel.textContent = data.label;
        }
        
    } catch (error) {
        console.error('Error checking status:', error);
    }
}

function updateCountdown(countdownElement, targetTime) {
    const now = Date.now();
    const diff = (targetTime - now) / 1000;
    
    // Check if timer has reached 0 and active is false (not null)
    if (diff <= 0 && isActive === false) {
        // Can't refresh from the same page as the editor.
        // location.reload();
        return;
    }
    
    // Only update display if time is positive
    if (diff > 0) {
        const hours = Math.floor(diff / 3600);
        const minutes = Math.floor((diff % 3600) / 60);
        const seconds = Math.floor(diff % 60);
        
        if (countdownElement) {
            countdownElement.textContent = 
                String(hours).padStart(2, '0') + ':' + 
                String(minutes).padStart(2, '0') + ':' + 
                String(seconds).padStart(2, '0');
            
            // Change color when close to refresh
            if (diff < 60) {
                countdownElement.style.color = '#ef4444';
            } else if (diff < 300) {
                countdownElement.style.color = '#f59e0b';
            } else {
                countdownElement.style.color = '#4CAF50';
            }
        }
    }
}

function hideEditor() {
    const editorContainer = document.getElementById('editor-container');
    const mainPage = document.getElementById('main-page');
    editorContainer.style.display = 'none';
    mainPage.style.display = 'block';
};

function showEditor(name) {
    const editorContainer = document.getElementById('editor-container');
    const mainPage = document.getElementById('main-page');
    const editorTitle = document.getElementById('editor-title');
    editorContainer.style.display = 'block';
    mainPage.style.display = 'none';
    editorTitle.innerHTML = name;
    window.editorHelper.editor.focus();
};

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
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        clearInterval(loadingInterval);
        icon.textContent = '✅';
        
        setTimeout(() => {
            icon.textContent = originalText;
        }, 10000);
        
    } catch (error) {
        clearInterval(loadingInterval);
        icon.textContent = '❌';
        
        setTimeout(() => {
            icon.textContent = originalText;
        }, 3000);
    }
}

async function deleteFeed(event, feedName, url, itemId) {
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
                // Include any auth tokens if needed
                // 'Authorization': `Bearer ${token}`,
            },
            // Include credentials if using cookies for auth
            credentials: 'same-origin'  // or 'include' for cross-domain
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        // fade to 100% transparent over 1 second
        for (i = 0; i < 10; i++) {
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

document.addEventListener('DOMContentLoaded', function() {
    const countdownElement = document.getElementById('countdown');
    const targetTime = parseInt(countdown.getAttribute('data-target'));
    const statusEndpoint = countdown.getAttribute('data-status');

    // Check status every 10 seconds
    checkStatus(statusEndpoint);
    statusCheckInterval = setInterval(() => checkStatus(statusEndpoint), 10000);
    
    // Update countdown every second
    countdownInterval = setInterval(() => updateCountdown(countdownElement, targetTime), 1000);
    updateCountdown(countdownElement, targetTime);
    
    // Cleanup intervals on page unload
    window.addEventListener('beforeunload', function() {
        if (statusCheckInterval) clearInterval(statusCheckInterval);
        if (countdownInterval) clearInterval(countdownInterval);
    });
});