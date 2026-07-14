
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
const data = {
    name: {
        _value: "Alice",
        _valueType: "string",
        _fieldType: "text",
        _params: {
            description: "The user's full name"  // ← Add description here
        }
    },
    age: {
        _value: 25,
        _valueType: "number",
        _fieldType: "number",
        _params: {
            description: "Age in years"  // ← Description for age
        }
    },
    email: {
        _value: "alice@example.com",
        _valueType: "string",
        _fieldType: "text",
        _params: {
            description: "Email address for notifications"  // ← Hint text
        }
    }
};

function saveYaml(){
    document.getElementById('save-feed-button').addEventListener('click', function() {
        const yamlContent = guifier_list['feed.yaml.sample'].getData('yaml');
        const yamlOutput = document.querySelector('textarea[name="guifier-output"]');
        yamlOutput.innerHTML = yamlContent;
    });
}

function showYaml(name) {
    name = name || 'feed.yaml.sample';
    const guifier_div = document.getElementById('guifier')
    guifier_div.style.display = 'block';
    guifier_div.innerHTML = '';
    const textarea = document.querySelector(`textarea.guifier[name="${name}"]`);
    const yamlJson = textarea.value;
    // Load yaml from cached Guifier
    if (guifier_list[textarea.name]) {
        const yamlJson = guifier_list[textarea.name].getData('yaml');
    }
    const params = {
        rootContainerName: textarea.name,
        // To select a container element, you can use a selector
        // such as a hashtag followed by the element's id (similar to CSS selectors).
        elementSelector: '#guifier',
        // Here, you need to specify the JSON string.
        // data: JSON.stringify(data),
        data: yamlJson,
        // You should specify the data type (in this case, JSON)
        // as Guifier supports five data formats: 'json', 'yaml', 'xml', 'toml' and 'js' (javascipt object).
        dataType: 'json'
    }
    guifier_list[textarea.name] = new Guifier(params)
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
    
    // Load YAML
    for (const button of document.getElementsByClassName('feed-button')) {
        button.addEventListener('click', function() {
            const name = this.name;
            showYaml(name);
        });
    }
});