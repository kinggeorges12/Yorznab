// terminal.js - Interactive Terminal Controls

let ws = null;
let isRunning = false;
let statusTimeout = null;
let currentStatusType = '';
let currentStatusText = '';
const defaultStatusType = 'idle';
const defaultStatusText = 'Ready';
const clearStatusDuration = 1500;
// Message resending when unresponsive
const ws_message_timeout = 3000;
let ws_message_received = false;
let ws_last_message = { timestamp: Date.now(), message: '', echo: '' };
// Show disconnect button when reconnect is clicked
let disconnectTimeout = null;

// Event subscription system
const eventHandlers = {
    'connect': [],
    'disconnect': [],
    'error': [],
    'exit': [],
    'message': []
};

function subscribe(event, callback) {
    if (eventHandlers[event]) {
        eventHandlers[event].push(callback);
    }
}

function emit(event, data) {
    if (eventHandlers[event]) {
        eventHandlers[event].forEach(callback => callback(data));
    }
}

// Make sendInput globally accessible
function sendInput(text) {
    console.log('📤 Starting WS:', JSON.stringify(ws));
    console.log('📤 Sending text:', JSON.stringify(text));
    if (ws && ws.readyState === WebSocket.OPEN) {
        const currentTimestamp = Date.now();
        if (!text.trim()) {
            text = '=';
        }
        ws_last_message = { timestamp: currentTimestamp, message: text };
        ws_message_received = false;
        console.log('📤 Sending:', text);
        // Send as JSON with type 'input'
        ws.send(JSON.stringify({ type: 'input', message: text }));
        setTimeout(() => {
            if (currentTimestamp === ws_last_message.timestamp && !ws_message_received) {
                console.warn('⏳ No response from server after sending input:', text);
                setStatus('⏳ Resending message...', 'warning');
                sendInput(text)
            }
        }, ws_message_timeout);
    } else {
        console.warn('WebSocket is not open. Cannot send input.');
        addTerminalLine('error', `❌ Connect before sending input: ${text}`);
    }
}

function canSendMessage() {
    if (!ws_message_received) {
        setStatus(`⏳ Waiting for server response...`, 'warning');
        return false;
    }
    ws_message_received = false;
    return true;
}

// Handle sending input
function sendInputFromField() {
    const terminalInput = document.getElementById('terminalInput');
    if (!terminalInput) return
    // Check rate limit first, then leave message in input
    if (!canSendMessage()) {
        const sendBtn = document.getElementById('sendBtn');
        sendBtn.focus();
        return;
    }

    let text = terminalInput.value;
    // Handle Ctrl+C: Not implemented
    if (text === '\x03') {
        sendInput('\x03');
        terminalInput.value = '';
        terminalInput.focus();
        return;
    }
    
    // Don't add any special characters - just send the raw text
    console.log('📤 Sending input from field:', JSON.stringify(text));
    sendInput(text);
    terminalInput.value = '';
    terminalInput.focus();
}

// Handle send button in the input field
function handleClickSendButton(event) {
    event.preventDefault();
    sendInputFromField();
}

// Handle Enter key in the input field
function handleTerminalInputKeydown(event) {
    if (event.key === 'Enter') {
        if (!isRunning) { return; }
        event.preventDefault();
        sendInputFromField();
    }
}

function connectTerminal() {
    console.log('🔗 Attempting to connect to terminal...');
    const terminalConfig = document.getElementById('terminalConfig');
    const ws_url = terminalConfig.getAttribute('data-ws');
    const terminalOutput = document.getElementById('terminalOutput');
    const inputField = document.getElementById('terminalInput');

    // Focus on input
    inputField.focus();

    // Prevent multiple connections
    if (isRunning) {
        setStatus('⚠️ Terminal is already connected...', 'running');
        return;
    }
    
    // Close any existing connection
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
    }
    
    // Clear previous output and start fresh
    terminalOutput.innerHTML = '';
    addTerminalLine('system', '⏳ Connecting to terminal session...');
    
    // Emit connecting event
    emit('connect', { status: 'connecting' });
    
    // Create WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}${ws_url}`);
    
    ws.onopen = function() {
        console.log('✅ WebSocket connection opened');
        console.log('WebSocket readyState:', ws.readyState);
        setStatus('🔗 Connected', 'success');
        
        // Emit connected event
        emit('connect', { status: 'connected' });
        
        // Send a ready message to the server
        const readyMsg = JSON.stringify({ type: 'ready' });
        console.log('Sending ready message:', readyMsg);
        ws.send(readyMsg);
        
        setStatus('🤖 Running...', 'running', true);
    };

    ws.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('Received message:', data);
            
            // Update received flag for any message from server
            ws_message_received = true;
            
            try {
                if (data.type === 'exit') {
                    addTerminalLine('system', '━'.repeat(80));
                    if (data.code === 0) {
                        addTerminalLine('success', `✅ Session completed successfully! (exit code: ${data.code})`);
                        setStatus('✅ Session completed', 'success', true);
                    } else {
                        addTerminalLine('error', `☠️ Session failed with exit code: ${data.code}`);
                        setStatus('☠️ Session failed', 'error', true);
                    }
                    isRunning = false;
                    // Emit exit event
                    emit('exit', data);
                    ws.close();
                } else if (data.type === 'error') {
                    addTerminalLine('error', `❌ Error: ${data.message}`);
                    setStatus('❌ Error occurred', 'error');
                    emit('error', data);
                } else if (data.type === 'echo') {
                    // Store the response for error-checking
                    ws_last_message.echo = data.message;
                    console.log('✅ Echo received for:', data.message);
                } else {
                    if (!data.type) {
                        data.type = 'output';
                    }
                    console.log('✅ Message processed:', data.message);
                    addTerminalLine(data.type, data.message);
                    emit('message', data);
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
        addTerminalLine('error', `🚨 WebSocket error: ${error.message || 'Connection error'}`);
        setStatus('🚨 Connection error', 'error', true);
        isRunning = false;
        emit('error', error);
    };
    
    ws.onclose = function() {
        if (isRunning) {
            addTerminalLine('system', '⛓️‍💥 Connection closed');
            setStatus('⛓️‍💥 Connection lost', 'idle', true);
            isRunning = false;
        }
        emit('disconnect', {});
    };
}

function addTerminalLine(type, message) {
    const terminalOutput = document.getElementById('terminalOutput');
    if (!terminalOutput) return;
    if (!message.trim()) message = ' ';
    
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    
    if (type !== 'system' && type !== 'output' && type !== 'success' && type !== 'warning' && type !== 'error') {
        const timestamp = new Date().toLocaleTimeString();
        line.innerHTML = `[${timestamp}] ${message}`;
    } else {
        line.innerHTML = message;
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
    addTerminalLine('system', '━'.repeat(80));
}

function copyTerminalOutput() {
    const terminalOutput = document.getElementById('terminalOutput');
    const text = terminalOutput.innerText;
    
    navigator.clipboard.writeText(text).then(() => {
        setStatus('📑 Copied!', 'success');
    }).catch(err => {
        setStatus('❌ Copy failed', 'error');
        console.log('Error copying to clipboard: ', err);
    });
}

function setStatus(text, type, persist = false) {
    const statusText = document.getElementById('statusText');
    const terminalContainer = document.querySelector('.terminal-container');

    if (statusTimeout) {
        clearTimeout(statusTimeout);
        statusTimeout = null;
    }

    if (!text && !type) {
        text = defaultStatusText;
        type = defaultStatusType;
    }
    statusText.textContent = text;
    terminalContainer.className = `terminal-container ${type}`;
    
    if (!persist) {
        statusTimeout = setTimeout(() => {
            setStatus(currentStatusText, currentStatusType);
        }, clearStatusDuration);
    } else {
        currentStatusText = text;
        currentStatusType = type;
    }
}

// Main button handler - handles all button states
function handleRunButtonClick() {
    const runBtn = document.getElementById('runSetupBtn');
    if (!runBtn) return;
    
    // State: Disconnect warning mode
    if (runBtn.textContent === '⚠️ Disconnect?') {
        // Actually disconnect
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.close();
        }
        isRunning = false;
        runBtn.textContent = '▶️ Connect';
        runBtn.style.backgroundColor = '';
        runBtn.style.color = '';
        if (disconnectTimeout) {
            clearTimeout(disconnectTimeout);
            disconnectTimeout = null;
        }
        setStatus('⛓️‍💥 Disconnected', 'idle', true);
        addTerminalLine('system', '⛓️‍💥 Disconnected by user');
        return;
    }
    
    // State: Connected - show disconnect warning
    if (runBtn.textContent === '🔄 Reconnect') {
        runBtn.textContent = '⚠️ Disconnect?';
        runBtn.style.backgroundColor = '#dc3545';
        runBtn.style.color = 'white';
        if (disconnectTimeout) clearTimeout(disconnectTimeout);
        disconnectTimeout = setTimeout(() => {
            runBtn.textContent = '🔄 Reconnect';
            runBtn.style.backgroundColor = '';
            runBtn.style.color = '';
            disconnectTimeout = null;
        }, 3000);
        return;
    }
    
    // State: Disconnected - connect
    if (runBtn.textContent === '▶️ Connect') {
        connectTerminal();
        return;
    }
    
    // State: Connecting - do nothing (button is disabled)
    if (runBtn.textContent === '⏳ Connecting...') {
        return;
    }
}

// Subscribe to events to update button state
subscribe('connect', function(data) {
    const runBtn = document.getElementById('runSetupBtn');
    if (!runBtn) return;
    if (data.status === 'connecting') {
        runBtn.disabled = true;
        runBtn.textContent = '⏳ Connecting...';
    } else if (data.status === 'connected') {
        runBtn.disabled = false;
        runBtn.textContent = '🔄 Reconnect';
        runBtn.style.backgroundColor = '';
        runBtn.style.color = '';
        if (disconnectTimeout) {
            clearTimeout(disconnectTimeout);
            disconnectTimeout = null;
        }
        isRunning = true;
    }
});

subscribe('disconnect', function() {
    const runBtn = document.getElementById('runSetupBtn');
    if (!runBtn) return;
    runBtn.disabled = false;
    runBtn.textContent = '▶️ Connect';
    runBtn.style.backgroundColor = '';
    runBtn.style.color = '';
    if (disconnectTimeout) {
        clearTimeout(disconnectTimeout);
        disconnectTimeout = null;
    }
    isRunning = false;
});

subscribe('exit', function() {
    const runBtn = document.getElementById('runSetupBtn');
    if (!runBtn) return;
    runBtn.disabled = false;
    runBtn.textContent = '▶️ Connect';
    runBtn.style.backgroundColor = '';
    runBtn.style.color = '';
    if (disconnectTimeout) {
        clearTimeout(disconnectTimeout);
        disconnectTimeout = null;
    }
    isRunning = false;
});

subscribe('error', function() {
    const runBtn = document.getElementById('runSetupBtn');
    if (!runBtn) return;
    runBtn.disabled = false;
    runBtn.textContent = '▶️ Connect';
    runBtn.style.backgroundColor = '';
    runBtn.style.color = '';
    if (disconnectTimeout) {
        clearTimeout(disconnectTimeout);
        disconnectTimeout = null;
    }
    isRunning = false;
});

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
    setStatus('Ready', 'idle', true);
    
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

    // Attach click handler to the Run button
    const runBtn = document.getElementById('runSetupBtn');
    if (runBtn) {
        runBtn.textContent = '▶️ Connect';
        runBtn.addEventListener('click', handleRunButtonClick);
    }
});