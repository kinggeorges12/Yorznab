

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