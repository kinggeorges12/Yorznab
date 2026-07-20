let isActive = true;
let statusCheckInterval = null;
let countdownInterval = null;
let targetTimestamp = null;

// Function to check status
async function checkStatus(statusEndpoint) {
    try {
        const response = await fetch(statusEndpoint);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        // Update active state
        isActive = data.active;
        
        // Update status dot and label
        updateStatusDisplay(data);
        
        // Update countdown with new target time
        if (data.next) {
            const nextDate = new Date(data.next);
            targetTimestamp = nextDate.getTime();
            updateCountdownDisplay(targetTimestamp);
        }
        
        // Update scheduled time
        updateScheduledTime(data);
        
        // Update server time
        updateServerTime(data);
        
        return data;
    } catch (error) {
        console.error('Error checking status:', error);
        // Show error state
        const statusDot = document.getElementById('status-dot');
        const statusLabel = document.getElementById('status-label');
        if (statusDot) statusDot.className = 'status-dot error';
        if (statusLabel) statusLabel.textContent = '🔌 Disconnected';
        return null;
    }
}

function updateStatusDisplay(data) {
    const statusDot = document.getElementById('status-dot');
    const statusLabel = document.getElementById('status-label');
    
    if (!statusDot || !statusLabel) return;
    
    // Update dot color based on status
    if (data.status === 'healthy') {
        statusDot.className = 'status-dot healthy';
    } else if (data.status === 'warning') {
        statusDot.className = 'status-dot warning';
    } else {
        statusDot.className = 'status-dot error';
    }
    
    // Update label with activity status
    let statusText = data.label || '❓ Unknown';
    statusLabel.textContent = statusText;
}

function updateScheduledTime(data) {
    const scheduledEl = document.querySelector('#scheduled');
    if (!scheduledEl) return;
    
    const nextTime = data.next;
    if (!nextTime) {
        scheduledEl.textContent = 'No schedule';
        return;
    }
    
    const date = new Date(nextTime);
    scheduledEl.textContent = formatDateTime(date);
    scheduledEl.title = `Scheduled: ${date.toLocaleString()}`;
}

function updateServerTime(data) {
    const serverTimeEl = document.querySelector('#server-time');
    if (!serverTimeEl) return;
    
    const serverTime = data.time;
    if (!serverTime) {
        serverTimeEl.textContent = 'No server time';
        return;
    }
    
    const date = new Date(serverTime);
    serverTimeEl.textContent = formatDateTime(date);
    serverTimeEl.title = `Server time: ${date.toLocaleString()}`;
}

function formatDateTime(date) {
    if (!(date instanceof Date) || isNaN(date)) {
        return 'Invalid date';
    }
    
    const options = {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZoneName: 'short'
    };
    
    return date.toLocaleString('en-US', options);
}

function updateCountdownDisplay(targetTime) {
    const countdownElement = document.getElementById('countdown');
    if (!countdownElement) return;
    
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
        
        // Update each part of the countdown
        const hoursSpan = countdownElement.querySelector('.hours');
        const minutesSpan = countdownElement.querySelector('.minutes');
        const secondsSpan = countdownElement.querySelector('.seconds');
        
        if (hoursSpan) hoursSpan.textContent = String(hours).padStart(2, '0');
        if (minutesSpan) minutesSpan.textContent = String(minutes).padStart(2, '0');
        if (secondsSpan) secondsSpan.textContent = String(seconds).padStart(2, '0');
        
        // Remove all color classes
        if (hoursSpan) {
            hoursSpan.classList.remove('short', 'mid', 'long');
            if (diff < 60) {
                hoursSpan.classList.add('short');
            } else if (diff < 300) {
                hoursSpan.classList.add('mid');
            } else {
                hoursSpan.classList.add('long');
            }
        }
        if (minutesSpan) {
            minutesSpan.classList.remove('short', 'mid', 'long');
            if (diff < 60) {
                minutesSpan.classList.add('short');
            } else if (diff < 300) {
                minutesSpan.classList.add('mid');
            } else {
                minutesSpan.classList.add('long');
            }
        }
        if (secondsSpan) {
            secondsSpan.classList.remove('short', 'mid', 'long');
            if (diff < 60) {
                secondsSpan.classList.add('short');
            } else if (diff < 300) {
                secondsSpan.classList.add('mid');
            } else {
                secondsSpan.classList.add('long');
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

function showEditor() {
    const editorContainer = document.getElementById('editor-container');
    const mainPage = document.getElementById('main-page');
    editorContainer.style.display = 'block';
    mainPage.style.display = 'none';
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
            throw new Error(`HTTP error! status: ${response.status}`);
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

function startCountdownTimer() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
    }
    
    countdownInterval = setInterval(() => {
        if (targetTimestamp) {
            updateCountdownDisplay(targetTimestamp);
        }
    }, 1000);
}

document.addEventListener('DOMContentLoaded', function() {
    const countdownElement = document.getElementById('countdown');
    if (!countdownElement) {
        console.error('Countdown element not found');
        return;
    }
    
    const statusEndpoint = countdownElement.dataset.status;
    if (!statusEndpoint) {
        console.error('Status endpoint not found');
        return;
    }

    // Initial status check
    checkStatus(statusEndpoint).then(data => {
        // Set initial target timestamp from the response
        if (data && data.next) {
            targetTimestamp = new Date(data.next).getTime();
            updateCountdownDisplay(targetTimestamp);
        }
    });
    
    // Check status every 10 seconds
    statusCheckInterval = setInterval(() => checkStatus(statusEndpoint), 10000);
    
    // Start countdown timer
    startCountdownTimer();
    
    // Cleanup intervals on page unload
    window.addEventListener('beforeunload', function() {
        if (statusCheckInterval) clearInterval(statusCheckInterval);
        if (countdownInterval) clearInterval(countdownInterval);
    });
});