
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
        location.reload();
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

async function refreshFeed(event, url, iconId) {
    event.preventDefault();
    
    const icon = document.getElementById(iconId);
    if (!icon) {
        console.error('Icon element not found:', iconId);
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
        }, 2000);
        
    } catch (error) {
        clearInterval(loadingInterval);
        icon.textContent = '❌';
        
        setTimeout(() => {
            icon.textContent = originalText;
        }, 10000);
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