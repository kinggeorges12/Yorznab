// terminal.js - Interactive Terminal Controls

let ws = null;
let isRunning = false;
let statusTimeout = null;
let currentStatusType = '';
let currentStatusText = '';
const defaultStatusType = 'idle';
const defaultStatusText = 'Ready';
const clearStatusDuration = 1500;
// Rate limiting for sending messages
let lastSendTime = 0;
const SEND_COOLDOWN_MS = 2000; // 2 second cooldown

// Make sendInput globally accessible
function sendInput(text, error = true) {
    console.log('📤 Starting WS:', JSON.stringify(ws));
    console.log('📤 Sending text:', JSON.stringify(text));
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(text);
        console.log('📤 Sending:', text);
    } else if (error) {
        console.warn('WebSocket is not open. Cannot send input.');
        addTerminalLine('error', `❌ Connect before sending input: ${text}`);
    }
}

function canSendMessage() {
    const now = Date.now();
    if (now - lastSendTime < SEND_COOLDOWN_MS) {
        const remainingMs = SEND_COOLDOWN_MS - (now - lastSendTime);
        const remainingSeconds = Math.ceil(remainingMs / 1000);
        setStatus(`⏳ Slow down and try again in ${remainingSeconds}s`, 'error');
        return false;
    }
    lastSendTime = now;
    return true;
}

// Handle sending input from both Enter key and Send button
function sendInputFromField(sendBtn = null) {
    const terminalInput = document.getElementById('terminalInput');
    if (!terminalInput) return
    // Check rate limit first, then leave message in input
    if (!canSendMessage()) {
        const sendBtn = document.getElementById('sendBtn');
        sendBtn.focus();
        return;
    }

    const text = terminalInput.value + (sendBtn ? '\f' : '');
    console.log('📤 Sending input from field:', JSON.stringify(text));
    sendInput(text);
    terminalInput.value = '';
    terminalInput.focus();
}

function connectTerminal() {
    console.log('🔗 Attempting to connect to terminal...');
    const terminalConfig = document.getElementById('terminalConfig');
    const ws_url = terminalConfig.getAttribute('data-ws');
    const runBtn = document.getElementById('runSetupBtn');
    const terminalOutput = document.getElementById('terminalOutput');
    const inputField = document.getElementById('terminalInput');

    // Focus on input
    inputField.focus();

    // Prevent multiple connections
    if (isRunning) {
        setStatus('⚠️ Terminal is already connected...', type = 'error');
        return;
        ws.close();
    }
    
    // Clear any pending status timeout
    clearStatusTimeout();
    
    // Clear previous output and start fresh
    terminalOutput.innerHTML = '';
    addTerminalLine('system', '⏳ Connecting to terminal session...');
    
    // Update UI state
    isRunning = true;
    if (runBtn) {
        runBtn.disabled = true;
        runBtn.textContent = '⏳ Connecting...';
    }
    
    // Close any existing connection
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
    }
    
    // Create WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}${ws_url}`);
    
    ws.onopen = function() {
        setStatus('✅ Connected', 'success');
        
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.textContent = '🔄 Reconnect';
        }
        
        // Send a ready message to the server
        ws.send(JSON.stringify({ type: 'ready' }));
        
        setStatus('🤖 Running...', 'running', true);
    };
    
    ws.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('Received message:', data);
            try {
                if (data.type === 'exit') {
                    addTerminalLine('system', `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
                    if (data.code === 0) {
                        addTerminalLine('success', `✅ Session completed successfully! (exit code: ${data.code})`);
                        setStatus('✅ Session completed', 'success', true);
                    } else {
                        addTerminalLine('error', `❌ Session failed with exit code: ${data.code}`);
                        setStatus('❌ Session failed', 'error', true);
                    }
                    isRunning = false;
                    if (runBtn) {
                        runBtn.disabled = false;
                        runBtn.textContent = '▶️ Connect';
                    }
                    ws.close();
                } else if (data.type === 'error') {
                    addTerminalLine('error', `❌ Error: ${data.message}`);
                    setStatus('❌ Error occurred', 'error');
                } else if (data.type === 'system') {
                    addTerminalLine('system', data.message);
                } else if (data.type === 'output') {
                    addTerminalLine('output', data.message);
                } else if (data.type === 'success') {
                    addTerminalLine('success', data.message);
                } else {
                    addTerminalLine('output', JSON.stringify(data));
                }
            } catch (e) {
                console.error('❌ WS error while handling message:', event.data);
                console.error('❌ Error:', e);
                addTerminalLine('output', event.data);
            }
        } catch (e) {
            console.error('❌ Error parsing WebSocket message:', e);
            addTerminalLine('output', event.data);
        }
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
    };
    
    ws.onerror = function(error) {
        addTerminalLine('error', `❌ WebSocket error: ${error.message || 'Connection error'}`);
        setStatus('❌ Connection error', 'error', true);
        isRunning = false;
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.textContent = '▶️ Connect';
        }
    };
    
    ws.onclose = function() {
        if (isRunning) {
            addTerminalLine('system', '⚠️ Connection closed');
            setStatus('⚠️ Connection lost', 'idle', true);
            isRunning = false;
            if (runBtn) {
                runBtn.disabled = false;
                runBtn.textContent = '▶️ Connect';
            }
        }
    };
}

// Handle send button in the input field
function handleClickSendButton(event) {
    event.preventDefault();
    sendInputFromField(sendBtn = true);
}

// Handle Enter key in the input field
function handleTerminalInputKeydown(event) {
    if (event.key === 'Enter') {
        if (!isRunning) { return; }
        event.preventDefault();
        sendInputFromField();
    }
}

function addTerminalLine(type, message) {
    const terminalOutput = document.getElementById('terminalOutput');
    if (!terminalOutput) return;
    
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    
    if (type !== 'system' && type !== 'output' && type !== 'success' && type !== 'error') {
        const timestamp = new Date().toLocaleTimeString();
        line.textContent = `[${timestamp}] ${message}`;
    } else {
        line.textContent = message;
    }
    
    terminalOutput.appendChild(line);
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
}

function clearTerminal() {
    if (isRunning) {
        if (!confirm('Terminal is currently active. Are you sure you want to clear the output?')) {
            return;
        }
    }
    const terminalOutput = document.getElementById('terminalOutput');
    terminalOutput.innerHTML = '';
    addTerminalLine('system', '🗑️ Terminal cleared');
    addTerminalLine('system', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
}

function copyTerminalOutput() {
    const terminalOutput = document.getElementById('terminalOutput');
    const text = terminalOutput.innerText;
    
    navigator.clipboard.writeText(text).then(() => {
        setStatus('✅ Copied!', 'success');
    }).catch(err => {
        setStatus('❌ Copy failed', 'error');
        console.log('Error copying to clipboard: ', err);
    });
}

function clearStatusTimeout(text, type) {
}

function setStatus(text, type, persist = false) {
    const statusText = document.getElementById('statusText');
    const statusIndicator = document.querySelector('.status-indicator');

    if (statusTimeout) {
        clearTimeout(statusTimeout);
        statusTimeout = null;
    }

    if (!text && !type) {
        text = defaultStatusText;
        type = defaultStatusType;
    }
    statusText.textContent = text;
    statusIndicator.className = `status-indicator ${type}`;
    
    if (!persist) {
        statusTimeout = setTimeout(() => {
            setStatus(currentStatusText, currentStatusType);
        }, clearStatusDuration);
    } else {
        currentStatusText = text;
        currentStatusType = type;
    }
}

// Toggle visibility of containers
function toggleButtons() {
    const buttons = document.querySelectorAll('.nav-toggle-button');
    
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active from all buttons
            buttons.forEach(btn => btn.classList.remove('active'));
            // Add active to clicked button
            this.classList.add('active');
            
            // Hide all containers
            document.querySelectorAll('#appIconsContainer, #terminalConfig')
                .forEach(el => el.style.display = 'none');
            // Show the matching container
            document.getElementById(this.dataset.container).style.display = 'block';
        });
    });
    
    // Set initial state
    if (buttons.length) {
        buttons[0].click();
    }
}
function showTerminal() {
    const containerId = 'terminalConfig';
    const targetButton = document.querySelector(`[data-container="${containerId}"]`);
    if (targetButton) {
        targetButton.click();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Change container display
    toggleButtons();

    // Initialize status indicator and text
    clearStatusTimeout()
    
    // Attach Enter key handler to the input field
    const inputField = document.getElementById('terminalInput');
    if (inputField) {
        inputField.addEventListener('keydown', handleTerminalInputKeydown);
        inputField.focus();
    }
    
    // Attach click handler to the Send button
    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) {
        sendBtn.addEventListener('click', handleClickSendButton);
    }
});
