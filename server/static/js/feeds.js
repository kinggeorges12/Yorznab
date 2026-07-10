document.addEventListener('DOMContentLoaded', function() {
    const countdown = document.getElementById('countdown');
    const targetTime = parseInt(countdown.getAttribute('data-target'));
    let isActive = true;
    let statusCheckInterval = null;
    let countdownInterval = null;

    // Function to check status
    async function checkStatus() {
        try {
            const data = await fetch('/status')
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

    function updateCountdown() {
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
            
            if (countdown) {
                countdown.textContent = 
                    String(hours).padStart(2, '0') + ':' + 
                    String(minutes).padStart(2, '0') + ':' + 
                    String(seconds).padStart(2, '0');
                
                // Change color when close to refresh
                if (diff < 60) {
                    countdown.style.color = '#ef4444';
                } else if (diff < 300) {
                    countdown.style.color = '#f59e0b';
                } else {
                    countdown.style.color = '#4CAF50';
                }
            }
        }
    }

    // Initial status check
    checkStatus();
    
    // Check status every 10 seconds
    statusCheckInterval = setInterval(checkStatus, 10000);
    
    // Update countdown every second
    countdownInterval = setInterval(updateCountdown, 1000);
    updateCountdown();
    
    // Cleanup intervals on page unload
    window.addEventListener('beforeunload', function() {
        if (statusCheckInterval) clearInterval(statusCheckInterval);
        if (countdownInterval) clearInterval(countdownInterval);
    });
});