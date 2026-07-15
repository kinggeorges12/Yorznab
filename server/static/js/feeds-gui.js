// ===== EDITOR.JS =====
let editor;
let schemaData = null;
let allSuggestions = [];
let currentFile = '';
let yamlContent = '';
let apiEndpoints = {
    list: '/feeds/list',
    load: '/feeds/load',
    save: '/feeds/save'
};
let valueSuggestions = [];

// ===== SHOW TOAST - GLOBAL SCOPE =====
function showToast(message, type) {
    const toast = document.getElementById('toast');
    if (!toast) {
        console.warn('Toast element not found:', message);
        return;
    }
    toast.textContent = message;
    toast.className = 'yaml-toast ' + type + ' show';
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(function() {
        toast.classList.remove('show');
    }, 3000);
}

// ===== GET API ENDPOINTS FROM WRAPPER =====
function getApiEndpoints() {
    const wrapper = document.querySelector('.yaml-editor-wrapper');
    if (wrapper) {
        const listUrl = wrapper.dataset.list;
        const loadUrl = wrapper.dataset.load;
        const saveUrl = wrapper.dataset.save;
        
        console.log('🔍 Data attributes found:', { listUrl, loadUrl, saveUrl });
        
        // Only override if the data attributes have values
        if (listUrl) {
            apiEndpoints.list = listUrl;
            console.log('✅ Set list endpoint to:', listUrl);
        }
        if (loadUrl) {
            apiEndpoints.load = loadUrl;
            console.log('✅ Set load endpoint to:', loadUrl);
        }
        if (saveUrl) {
            apiEndpoints.save = saveUrl;
            console.log('✅ Set save endpoint to:', saveUrl);
        }
        
        console.log('📡 API Endpoints configured:', apiEndpoints);
    } else {
        console.warn('⚠️ No .yaml-editor-wrapper found, using default endpoints');
    }
}

// ===== DETECT THEME FROM URL =====
function detectTheme() {
    const url = window.location.hash + window.location.pathname + window.location.search;
    
    if (url.includes('gh_light') || url.includes('light') || url.includes('?light') || url.includes('#light')) {
        return 'github_light_default';
    }
    if (url.includes('ghdark') || url.includes('dark') || url.includes('?dark') || url.includes('#dark')) {
        return 'github_dark';
    }
    return 'github_dark';
}

// ===== LOAD SCHEMA FROM TEXTAREA =====
function loadSchemaFromTextarea() {
    const textarea = document.querySelector('.yaml-schema');
    if (!textarea) {
        console.error('No textarea with class "yaml-schema" found');
        return null;
    }
    
    try {
        const raw = textarea.value;
        const content = raw.replace('{template_config_editor}', '').trim();
        if (!content) {
            console.warn('Schema textarea is empty');
            return null;
        }
        const parsed = JSON.parse(content);
        console.log('✅ Schema loaded:', Object.keys(parsed.schema.properties));
        return parsed;
    } catch (e) {
        console.error('Failed to parse schema JSON:', e);
        return null;
    }
}

// ===== BUILD AUTOCOMPLETE SUGGESTIONS FROM SCHEMA =====
function buildSuggestions(schema, path = '') {
    const suggestions = [];
    
    if (!schema || typeof schema !== 'object') return suggestions;
    
    if (schema.properties) {
        Object.keys(schema.properties).forEach(key => {
            const prop = schema.properties[key];
            
            let typeDesc = Array.isArray(prop.type) ? prop.type.join('|') : prop.type;
            typeDesc = typeDesc || 'property';
            
            suggestions.push({
                caption: key,
                value: `${key}: `,
                meta: prop.title || typeDesc,
                score: 100,
                type: 'property',
                description: prop.description || ''
            });
            
            if (prop.type === 'object' || (Array.isArray(prop.type) && prop.type.includes('object'))) {
                if (prop.properties) {
                    suggestions.push(...buildSuggestions(prop, key));
                }
            }
        });
    }
    
    return suggestions;
}

// ===== GENERATE VALUE SUGGESTIONS FROM DATA =====
function getValueSuggestions() {
    const words = [];
    if (!schemaData || !schemaData.data) return words;
    
    function collectValues(obj) {
        if (!obj || typeof obj !== 'object') return;
        
        Object.values(obj).forEach(value => {
            if (typeof value === 'string' && value.length > 0 && value.length < 50) {
                words.push(value);
            }
            if (typeof value === 'number') {
                words.push(String(value));
            }
            if (typeof value === 'boolean') {
                words.push(String(value));
            }
            if (Array.isArray(value)) {
                value.forEach(item => {
                    if (typeof item === 'string' && item.length < 50) words.push(item);
                    if (typeof item === 'object' && item !== null) collectValues(item);
                });
            }
            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                collectValues(value);
            }
        });
    }
    
    collectValues(schemaData.data);
    return [...new Set(words)];
}

// ===== YAML DUMP =====
function yamlDump(obj, indent = 0) {
    if (obj === null || obj === undefined) return 'null';
    if (typeof obj === 'boolean') return obj ? 'true' : 'false';
    if (typeof obj === 'number') return String(obj);
    if (typeof obj === 'string') {
        if (obj.includes('\n')) {
            return '|\n' + obj.split('\n').map(line => '  ' + line).join('\n');
        }
        return obj;
    }
    if (Array.isArray(obj)) {
        if (obj.length === 0) return '[]';
        const items = obj.map(item => {
            if (typeof item === 'object' && item !== null) {
                return '- ' + yamlDump(item, indent + 2);
            }
            return '- ' + yamlDump(item, indent + 2);
        });
        return items.join('\n');
    }
    if (typeof obj === 'object') {
        const lines = [];
        const prefix = '  '.repeat(indent);
        for (const [key, value] of Object.entries(obj)) {
            if (value === null || value === undefined) {
                lines.push(`${prefix}${key}: null`);
            } else if (typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length > 0) {
                lines.push(`${prefix}${key}:`);
                lines.push(yamlDump(value, indent + 1));
            } else if (Array.isArray(value) && value.length > 0) {
                lines.push(`${prefix}${key}:`);
                const arrayStr = yamlDump(value, indent + 1);
                lines.push(arrayStr.split('\n').map(line => '  ' + line).join('\n'));
            } else {
                lines.push(`${prefix}${key}: ${yamlDump(value, 0)}`);
            }
        }
        return lines.join('\n');
    }
    return String(obj);
}

// ===== LIST FILES FROM SERVER =====
async function listFiles() {
    try {
        console.log('📡 Fetching file list from:', apiEndpoints.list);
        const response = await fetch(apiEndpoints.list);
        if (!response.ok) {
            console.error('Failed to list files:', response.status);
            return [];
        }
        const result = await response.json();
        console.log('📡 File list response:', result);
        if (typeof result === 'string' && result.includes('No YAML files found')) {
            return [];
        }
        return Array.isArray(result) ? result : [];
    } catch (e) {
        console.error('Error listing files:', e);
        return [];
    }
}

// ===== LOAD FILE FROM SERVER =====
async function loadFileFromServer(filename) {
    if (!filename) return;
    currentFile = filename;
    
    try {
        const loadUrl = apiEndpoints.load.endsWith('/') 
            ? apiEndpoints.load + encodeURIComponent(filename)
            : apiEndpoints.load + '/' + encodeURIComponent(filename);
        
        console.log('📡 Loading file from:', loadUrl);
        const response = await fetch(loadUrl);
        
        if (!response.ok) {
            if (response.status === 404) {
                showToast('❌ File not found: ' + filename, 'error');
            } else {
                showToast('❌ Error loading file: ' + response.status, 'error');
            }
            return;
        }
        
        const content = await response.text();
        editor.setValue(content, -1);
        yamlContent = content;
        
        const fileDisplay = document.getElementById('currentFileDisplay');
        if (fileDisplay) fileDisplay.textContent = '📄 ' + filename;
        
        showToast('✅ Loaded: ' + filename, 'success');
        console.log('📝 Loaded file:', filename);
        
    } catch (e) {
        console.error('Failed to load file:', e);
        showToast('❌ Network error loading file', 'error');
    }
}

// ===== SAVE YAML TO SERVER =====
window.saveYAML = async function() {
    if (!currentFile) {
        showToast('❌ No file selected', 'error');
        return;
    }
    
    const content = editor.getValue();
    
    try {
        const saveUrl = apiEndpoints.save.endsWith('/') 
            ? apiEndpoints.save + encodeURIComponent(currentFile)
            : apiEndpoints.save + '/' + encodeURIComponent(currentFile);
        
        console.log('📡 Saving to:', saveUrl);
        const response = await fetch(saveUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: content
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            showToast('❌ Error: ' + (errorData.detail || 'Unknown error'), 'error');
            return;
        }
        
        const result = await response.json();
        if (result.message) {
            showToast(result.message, 'success');
            yamlContent = content;
        } else {
            showToast('✅ Saved: ' + currentFile, 'success');
            yamlContent = content;
        }
    } catch (e) {
        showToast('❌ Network error: ' + e.message, 'error');
        console.error('Save error:', e);
    }
};

// ===== LOAD FILE (from file selector) =====
window.selectFile = async function() {
    const fileSelect = document.getElementById('fileSelector');
    if (fileSelect && fileSelect.value) {
        console.log('📂 Selected file:', fileSelect.value);
        await loadFileFromServer(fileSelect.value);
    }
};

// ===== SHOW SUGGESTIONS AND FOCUS EDITOR =====
window.showSuggestions = function() {
    console.log('💡 Suggestion button clicked');
    editor.focus();
    const propCount = allSuggestions.length;
    const valueCount = valueSuggestions.length;
    console.log(`💡 Available: ${propCount} properties, ${valueCount} values`);
    showToast(`💡 ${propCount} properties, ${valueCount} values available`, 'info');
    
    // Check if completer is registered
    console.log('🔍 Editor completers:', editor.completers ? editor.completers.length : 0);
    console.log('🔍 Editor session:', editor.session);
    
    // Try multiple methods to trigger autocomplete
    try {
        console.log('🔍 Attempting to trigger autocomplete...');
        editor.execCommand('startAutocomplete');
        console.log('✅ Autocomplete triggered via execCommand');
    } catch (e) {
        console.error('❌ Failed to trigger autocomplete:', e);
    }
    
    // Check if autocomplete is enabled
    console.log('🔍 Editor options:', editor.getOption('enableBasicAutocompletion'));
};

// ===== INITIALIZE EDITOR =====
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🚀 Initializing editor...');
    
    getApiEndpoints();
    
    schemaData = loadSchemaFromTextarea();
    
    if (!schemaData) {
        console.warn('No valid schema found');
        schemaData = { schema: {}, data: {} };
    }
    
    allSuggestions = buildSuggestions(schemaData.schema);
    console.log('📝 Schema suggestions built:', allSuggestions.map(s => s.caption).join(', '));
    console.log('📝 Total suggestions:', allSuggestions.length);
    
    valueSuggestions = getValueSuggestions();
    console.log('📝 Value suggestions:', valueSuggestions.slice(0, 10).join(', '));
    console.log('📝 Total values:', valueSuggestions.length);
    
    const detectedTheme = detectTheme();
    console.log('🎨 Detected theme:', detectedTheme);
    
    let initialContent = '# YAML Configuration\n\n';
    if (schemaData.data) {
        initialContent = yamlDump(schemaData.data);
        console.log('📄 Loaded initial data into editor');
    }
    
    // Create editor
    console.log('🔧 Creating ACE editor...');
    editor = ace.edit("editor");
    console.log('✅ ACE editor created');
    
    editor.setTheme("ace/theme/" + detectedTheme);
    editor.session.setMode("ace/mode/yaml");
    editor.setValue(initialContent, -1);
    yamlContent = initialContent;
    
    // ===== SET TAB SIZE TO 2 =====
    editor.session.setTabSize(2);
    editor.session.setUseSoftTabs(true);
    
    // ===== ENABLE AUTOCOMPLETE - USING CORRECT OPTION NAMES =====
    console.log('🔧 Enabling autocomplete...');
    try {
        // Enable autocomplete
        editor.setOption('enableBasicAutocompletion', true);
        console.log('✅ enableBasicAutocompletion set to true');
    } catch (e) {
        console.warn('Could not set enableBasicAutocompletion:', e);
    }
    
    try {
        editor.setOption('enableLiveAutocompletion', true);
        console.log('✅ enableLiveAutocompletion set to true');
    } catch (e) {
        console.warn('Could not set enableLiveAutocompletion:', e);
    }
    
    // Check if options were applied
    console.log('🔍 Editor getOption enableBasicAutocompletion:', editor.getOption('enableBasicAutocompletion'));
    console.log('🔍 Editor getOption enableLiveAutocompletion:', editor.getOption('enableLiveAutocompletion'));
    
    const gutter = document.querySelector('.ace_gutter');
    if (gutter) {
        gutter.removeAttribute('aria-hidden');
    }
    
    const themeSelector = document.getElementById('themeSelector');
    if (themeSelector) {
        themeSelector.value = detectedTheme;
    }
    
    // ===== AUTOCOMPLETE =====
    console.log('🔧 Registering completer...');
    const completer = {
        getCompletions: function(editor, session, pos, prefix, callback) {
            console.log(`🔍 Completer called with prefix: "${prefix}" at line ${pos.row}, col ${pos.column}`);
            
            const line = session.getLine(pos.row);
            const before = line.substring(0, pos.column);
            
            let suggestions = [];
            const searchPrefix = prefix.toLowerCase();
            
            const afterColon = /:\s*$/.test(before) || /:\s+/.test(before);
            console.log(`🔍 afterColon: ${afterColon}`);
            
            if (afterColon && prefix.length > 0) {
                console.log(`🔍 Looking for value suggestions matching "${searchPrefix}"`);
                valueSuggestions.forEach(val => {
                    if (String(val).toLowerCase().startsWith(searchPrefix)) {
                        suggestions.push({
                            caption: val,
                            value: val,
                            meta: 'value',
                            score: 80
                        });
                        console.log(`  ✅ Added value suggestion: "${val}"`);
                    }
                });
            }
            
            console.log(`🔍 Looking for property suggestions matching "${searchPrefix}"`);
            allSuggestions.forEach(sug => {
                const lineContent = line.trim();
                if (lineContent.includes(sug.caption + ':')) {
                    console.log(`  ⏭️ Skipping "${sug.caption}" (already in line)`);
                    return;
                }
                
                if (sug.caption.toLowerCase().startsWith(searchPrefix) || searchPrefix === '') {
                    suggestions.push({
                        caption: sug.caption,
                        value: sug.value,
                        meta: sug.meta || 'property',
                        score: sug.score || 100,
                        description: sug.description || ''
                    });
                    console.log(`  ✅ Added property suggestion: "${sug.caption}"`);
                }
            });
            
            if (suggestions.length === 0 && prefix.length > 1) {
                console.log(`🔍 Looking for fallback value suggestions matching "${searchPrefix}"`);
                valueSuggestions.forEach(val => {
                    if (String(val).toLowerCase().startsWith(searchPrefix)) {
                        suggestions.push({
                            caption: val,
                            value: val,
                            meta: 'value',
                            score: 50
                        });
                        console.log(`  ✅ Added fallback value: "${val}"`);
                    }
                });
            }
            
            suggestions.sort((a, b) => (b.score || 0) - (a.score || 0));
            suggestions = suggestions.slice(0, 30);
            
            console.log(`💡 Returning ${suggestions.length} suggestions for "${prefix}"`);
            if (suggestions.length > 0) {
                console.log('💡 First 5 suggestions:', suggestions.slice(0, 5).map(s => s.caption).join(', '));
            } else {
                console.log('⚠️ No suggestions found!');
            }
            
            callback(null, suggestions);
        },
        
        getDocTooltip: function(item) {
            if (item.description) {
                item.docHTML = `<div style="max-width:300px;padding:4px;">${item.description}</div>`;
            }
            return item;
        }
    };
    
    // Add completer
    if (!editor.completers) {
        editor.completers = [];
        console.log('🔧 Created new completers array');
    }
    editor.completers.push(completer);
    console.log(`✅ Completer registered. Total completers: ${editor.completers.length}`);
    
    // ===== KEYBOARD SHORTCUT =====
    editor.commands.addCommand({
        name: 'showAutocomplete',
        bindKey: { win: 'Ctrl-Space', mac: 'Ctrl-Space' },
        exec: function(editor) {
            console.log('⌨️ Ctrl+Space pressed (via ACE command)');
            const propCount = allSuggestions.length;
            const valueCount = valueSuggestions.length;
            console.log(`💡 ${propCount} properties, ${valueCount} values available`);
            showToast(`💡 ${propCount} properties, ${valueCount} values available`, 'info');
            editor.execCommand('startAutocomplete');
        }
    });
    
    // ===== STATUS BAR =====
    function updateStatusBar() {
        const cursor = editor.getCursorPosition();
        const selectedText = editor.getSelectedText();
        const totalLines = editor.session.getLength();
        
        const lineEl = document.getElementById('cursorLine');
        const colEl = document.getElementById('cursorCol');
        const selEl = document.getElementById('selectedChars');
        const linesEl = document.getElementById('totalLines');
        const modeEl = document.getElementById('currentMode');
        
        if (lineEl) lineEl.textContent = cursor.row + 1;
        if (colEl) colEl.textContent = cursor.column + 1;
        if (selEl) selEl.textContent = selectedText.length;
        if (linesEl) linesEl.textContent = totalLines;
        if (modeEl) modeEl.textContent = 'YAML';
    }
    
    editor.session.selection.on('changeCursor', updateStatusBar);
    editor.session.on('change', updateStatusBar);
    
    // ===== EXPORT FUNCTIONS =====
    window.undo = function() { editor.undo(); };
    window.redo = function() { editor.redo(); };
    window.find = function() { editor.execCommand('find'); };
    window.replace = function() { editor.execCommand('replace'); };
    
    window.changeTheme = function(theme) {
        editor.setTheme('ace/theme/' + theme);
        showToast('Theme: ' + theme, 'info');
    };
    
    window.changeMode = function(mode) {
        editor.session.setMode('ace/mode/' + mode);
        const modeEl = document.getElementById('currentMode');
        if (modeEl) modeEl.textContent = mode.toUpperCase();
        showToast('Mode: ' + mode.toUpperCase(), 'info');
    };
    
    window.changeFontSize = function(size) {
        editor.setFontSize(size + 'px');
        showToast('Font size: ' + size + 'px', 'info');
    };
    
    window.toggleWrap = function() {
        const wrap = editor.session.getUseWrapMode();
        editor.session.setUseWrapMode(!wrap);
        document.getElementById('wrapBtn').classList.toggle('active');
        showToast(wrap ? 'Wrap off' : 'Wrap on', 'info');
    };
    
    window.toggleReadOnly = function() {
        const readonly = editor.getReadOnly();
        editor.setReadOnly(!readonly);
        document.getElementById('readonlyBtn').classList.toggle('active');
        showToast(readonly ? 'Editable' : 'Read Only', 'info');
    };
    
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            window.saveYAML();
        }
        if ((e.ctrlKey || e.metaKey) && e.key === 'o') {
            e.preventDefault();
            const fileSelect = document.getElementById('fileSelector');
            if (fileSelect) fileSelect.click();
        }
        if ((e.ctrlKey || e.metaKey) && e.key === ' ') {
            e.preventDefault();
            console.log('⌨️ Ctrl+Space detected via keydown');
            const propCount = allSuggestions.length;
            const valueCount = valueSuggestions.length;
            showToast(`💡 ${propCount} properties, ${valueCount} values available`, 'info');
            editor.execCommand('startAutocomplete');
        }
    });
    
    // ===== SET UP FILE SELECTOR =====
    const fileSelect = document.getElementById('fileSelector');
    if (fileSelect) {
        console.log('📂 Loading file list...');
        const files = await listFiles();
        
        while (fileSelect.options.length > 0) {
            fileSelect.remove(0);
        }
        
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Select a file...';
        fileSelect.appendChild(placeholder);
        
        if (files.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'No files available';
            option.disabled = true;
            fileSelect.appendChild(option);
        } else {
            files.forEach(filename => {
                const option = document.createElement('option');
                option.value = filename;
                option.textContent = filename;
                fileSelect.appendChild(option);
            });
        }
        
        if (files.length > 0) {
            fileSelect.value = files[0];
            currentFile = files[0];
            console.log('📂 Loading default file:', files[0]);
            await loadFileFromServer(files[0]);
        }
    }
    
    updateStatusBar();
    
    console.log('✅ Editor ready');
    console.log('🎨 Theme:', detectedTheme);
    console.log('🔑 Press Ctrl+Space or click 💡 for autocomplete');
    console.log('📝 Available schema properties:', allSuggestions.map(s => s.caption).join(', '));
    console.log('📡 Using endpoints:', apiEndpoints);
    console.log('🔍 Total completers registered:', editor.completers ? editor.completers.length : 0);
    
    // Show initial suggestion count
    setTimeout(() => {
        const propCount = allSuggestions.length;
        const valueCount = valueSuggestions.length;
        showToast(`💡 ${propCount} properties, ${valueCount} values available for autocomplete`, 'info');
    }, 1000);
});