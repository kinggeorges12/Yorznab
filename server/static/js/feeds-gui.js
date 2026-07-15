// ===== EDITOR.JS =====
class YAMLEditor {
    constructor() {
        this.editor = null;
        this.schemaData = null;
        this.allSuggestions = [];
        this.currentFile = '';
        this.yamlContent = '';
        this.apiEndpoints = {
            list: '/feeds/list',
            load: '/feeds/load',
            save: '/feeds/save'
        };
        
        this.initialize();
    }

    // ===== GET API ENDPOINTS FROM WRAPPER =====
    getApiEndpoints() {
        const wrapper = document.querySelector('.yaml-editor-wrapper');
        if (wrapper) {
            const listUrl = wrapper.dataset.list;
            const loadUrl = wrapper.dataset.load;
            const saveUrl = wrapper.dataset.save;
            
            if (listUrl) this.apiEndpoints.list = listUrl;
            if (loadUrl) this.apiEndpoints.load = loadUrl;
            if (saveUrl) this.apiEndpoints.save = saveUrl;
            
            console.log('📡 API Endpoints configured:', this.apiEndpoints);
        }
    }

    // ===== DETECT THEME FROM URL =====
    detectTheme() {
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
    loadSchemaFromTextarea() {
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
    buildSuggestions(schema, path = '') {
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
                        suggestions.push(...this.buildSuggestions(prop, key));
                    }
                }
            });
        }
        
        return suggestions;
    }

    // ===== GENERATE VALUE SUGGESTIONS FROM DATA =====
    getValueSuggestions() {
        const words = [];
        if (!this.schemaData || !this.schemaData.data) return words;
        
        const collectValues = (obj) => {
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
        };
        
        collectValues(this.schemaData.data);
        return [...new Set(words)];
    }

    // ===== YAML DUMP =====
    yamlDump(obj, indent = 0) {
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
                    return '- ' + this.yamlDump(item, indent + 2);
                }
                return '- ' + this.yamlDump(item, indent + 2);
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
                    lines.push(this.yamlDump(value, indent + 1));
                } else if (Array.isArray(value) && value.length > 0) {
                    lines.push(`${prefix}${key}:`);
                    const arrayStr = this.yamlDump(value, indent + 1);
                    lines.push(arrayStr.split('\n').map(line => '  ' + line).join('\n'));
                } else {
                    lines.push(`${prefix}${key}: ${this.yamlDump(value, 0)}`);
                }
            }
            return lines.join('\n');
        }
        return String(obj);
    }

    // ===== LIST FILES FROM SERVER =====
    async listFiles() {
        try {
            const response = await fetch(this.apiEndpoints.list);
            if (!response.ok) {
                console.error('Failed to list files:', response.status);
                return [];
            }
            const result = await response.json();
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
    async loadFileFromServer(filename) {
        if (!filename) return;
        this.currentFile = filename;
        
        try {
            const loadUrl = this.apiEndpoints.load.endsWith('/') 
                ? this.apiEndpoints.load + encodeURIComponent(filename)
                : this.apiEndpoints.load + '/' + encodeURIComponent(filename);
                
            const response = await fetch(loadUrl);
            
            if (!response.ok) {
                if (response.status === 404) {
                    this.showToast('❌ File not found: ' + filename, 'error');
                } else {
                    this.showToast('❌ Error loading file: ' + response.status, 'error');
                }
                return;
            }
            
            const content = await response.text();
            this.editor.setValue(content, -1);
            this.yamlContent = content;
            this.showToast('✅ Loaded: ' + filename, 'success');
            console.log('📝 Loaded file:', filename);
            
        } catch (e) {
            console.error('Failed to load file:', e);
            this.showToast('❌ Network error loading file', 'error');
        }
    }

    // ===== SAVE YAML TO SERVER =====
    async saveYAML() {
        if (!this.currentFile) {
            this.showToast('❌ No file selected', 'error');
            return;
        }
        
        const content = this.editor.getValue();
        
        try {
            const saveUrl = this.apiEndpoints.save.endsWith('/') 
                ? this.apiEndpoints.save + encodeURIComponent(this.currentFile)
                : this.apiEndpoints.save + '/' + encodeURIComponent(this.currentFile);
                
            const response = await fetch(saveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: content
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                this.showToast('❌ Error: ' + (errorData.detail || 'Unknown error'), 'error');
                return;
            }
            
            const result = await response.json();
            if (result.message) {
                this.showToast(result.message, 'success');
                this.yamlContent = content;
            } else {
                this.showToast('✅ Saved: ' + this.currentFile, 'success');
                this.yamlContent = content;
            }
        } catch (e) {
            this.showToast('❌ Network error: ' + e.message, 'error');
            console.error('Save error:', e);
        }
    }

    // ===== LOAD FILE (from file selector) =====
    async loadFile(filename) {
        if (!filename) return;
        await this.loadFileFromServer(filename);
    }

    // ===== SHOW SUGGESTIONS AND FOCUS EDITOR =====
    showSuggestions() {
        this.editor.focus();
        this.editor.execCommand('startAutocomplete');
    }

    // ===== SHOW TOAST =====
    showToast(message, type) {
        const toast = document.getElementById('toast');
        if (!toast) return;
        toast.textContent = message;
        toast.className = 'yaml-toast ' + type + ' show';
        clearTimeout(toast._timeout);
        toast._timeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 2000);
    }

    // ===== UPDATE STATUS BAR =====
    updateStatusBar() {
        const cursor = this.editor.getCursorPosition();
        const selectedText = this.editor.getSelectedText();
        const totalLines = this.editor.session.getLength();
        
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

    // ===== INITIALIZE EDITOR =====
    async initialize() {
        // Get API endpoints from wrapper
        this.getApiEndpoints();
        
        // Load schema from textarea
        this.schemaData = this.loadSchemaFromTextarea();
        
        if (!this.schemaData) {
            console.warn('No valid schema found');
            this.schemaData = { schema: {}, data: {} };
        }
        
        // Build all suggestions from schema
        this.allSuggestions = this.buildSuggestions(this.schemaData.schema);
        console.log('📝 Schema suggestions built:', this.allSuggestions.map(s => s.caption).join(', '));
        
        // Get value suggestions from data
        const valueSuggestions = this.getValueSuggestions();
        console.log('📝 Value suggestions:', valueSuggestions.slice(0, 10).join(', '));
        
        // Detect theme from URL
        const detectedTheme = this.detectTheme();
        console.log('🎨 Detected theme:', detectedTheme);
        
        // Initialize editor with default content
        let initialContent = '# YAML Configuration\n\n';
        if (this.schemaData.data) {
            initialContent = this.yamlDump(this.schemaData.data);
            console.log('📄 Loaded initial data into editor');
        }
        
        // Initialize editor
        this.editor = ace.edit("editor");
        this.editor.setTheme("ace/theme/" + detectedTheme);
        this.editor.session.setMode("ace/mode/yaml");
        this.editor.setValue(initialContent, -1);
        this.yamlContent = initialContent;
        
        // Fix aria-hidden warning
        const gutter = document.querySelector('.ace_gutter');
        if (gutter) {
            gutter.removeAttribute('aria-hidden');
        }
        
        // Set theme selector
        const themeSelector = document.getElementById('themeSelector');
        if (themeSelector) {
            themeSelector.value = detectedTheme;
        }
        
        // ===== AUTOCOMPLETE =====
        const completer = {
            getCompletions: (editor, session, pos, prefix, callback) => {
                const line = session.getLine(pos.row);
                const before = line.substring(0, pos.column);
                
                let suggestions = [];
                const searchPrefix = prefix.toLowerCase();
                
                const afterColon = /:\s*$/.test(before) || /:\s+/.test(before);
                
                if (afterColon && prefix.length > 0) {
                    valueSuggestions.forEach(val => {
                        if (val.toLowerCase().startsWith(searchPrefix)) {
                            suggestions.push({
                                caption: val,
                                value: val,
                                meta: 'value',
                                score: 80
                            });
                        }
                    });
                }
                
                this.allSuggestions.forEach(sug => {
                    const lineContent = line.trim();
                    if (lineContent.includes(sug.caption + ':')) return;
                    
                    if (sug.caption.toLowerCase().startsWith(searchPrefix) || searchPrefix === '') {
                        suggestions.push({
                            caption: sug.caption,
                            value: sug.value,
                            meta: sug.meta || 'property',
                            score: sug.score || 100,
                            description: sug.description || ''
                        });
                    }
                });
                
                if (suggestions.length === 0 && prefix.length > 1) {
                    valueSuggestions.forEach(val => {
                        if (val.toLowerCase().startsWith(searchPrefix)) {
                            suggestions.push({
                                caption: val,
                                value: val,
                                meta: 'value',
                                score: 50
                            });
                        }
                    });
                }
                
                suggestions.sort((a, b) => (b.score || 0) - (a.score || 0));
                suggestions = suggestions.slice(0, 30);
                
                callback(null, suggestions);
            },
            
            getDocTooltip: function(item) {
                if (item.description) {
                    item.docHTML = `<div style="max-width:300px;padding:4px;">${item.description}</div>`;
                }
                return item;
            }
        };
        
        if (!this.editor.completers) {
            this.editor.completers = [];
        }
        this.editor.completers.push(completer);
        
        // ===== KEYBOARD SHORTCUT =====
        this.editor.commands.addCommand({
            name: 'showAutocomplete',
            bindKey: { win: 'Ctrl-Space', mac: 'Ctrl-Space' },
            exec: (editor) => {
                editor.execCommand('startAutocomplete');
            }
        });
        
        // ===== STATUS BAR =====
        this.editor.session.selection.on('changeCursor', () => this.updateStatusBar());
        this.editor.session.on('change', () => this.updateStatusBar());
        
        // ===== EXPORT FUNCTIONS =====
        this.editor.commands.addCommand({
            name: 'undo',
            bindKey: { win: 'Ctrl-Z', mac: 'Cmd-Z' },
            exec: () => this.editor.undo()
        });
        
        this.editor.commands.addCommand({
            name: 'redo',
            bindKey: { win: 'Ctrl-Y', mac: 'Cmd-Y' },
            exec: () => this.editor.redo()
        });
        
        // ===== THEME CHANGE =====
        const themeSelectorEl = document.getElementById('themeSelector');
        if (themeSelectorEl) {
            themeSelectorEl.addEventListener('change', (e) => {
                const theme = e.target.value;
                this.editor.setTheme('ace/theme/' + theme);
                this.showToast('Theme: ' + theme, 'info');
            });
        }
        
        // ===== MODE CHANGE =====
        const modeSelector = document.getElementById('modeSelector');
        if (modeSelector) {
            modeSelector.addEventListener('change', (e) => {
                const mode = e.target.value;
                this.editor.session.setMode('ace/mode/' + mode);
                const modeEl = document.getElementById('currentMode');
                if (modeEl) modeEl.textContent = mode.toUpperCase();
                this.showToast('Mode: ' + mode.toUpperCase(), 'info');
            });
        }
        
        // ===== FONT SIZE CHANGE =====
        const fontSizeSelector = document.getElementById('fontSizeSelector');
        if (fontSizeSelector) {
            fontSizeSelector.addEventListener('change', (e) => {
                const size = parseInt(e.target.value);
                this.editor.setFontSize(size + 'px');
                this.showToast('Font size: ' + size + 'px', 'info');
            });
        }
        
        // ===== WRAP TOGGLE =====
        const wrapBtn = document.getElementById('wrapBtn');
        if (wrapBtn) {
            wrapBtn.addEventListener('click', () => {
                const wrap = this.editor.session.getUseWrapMode();
                this.editor.session.setUseWrapMode(!wrap);
                wrapBtn.classList.toggle('active');
                this.showToast(wrap ? 'Wrap off' : 'Wrap on', 'info');
            });
        }
        
        // ===== READ ONLY TOGGLE =====
        const readonlyBtn = document.getElementById('readonlyBtn');
        if (readonlyBtn) {
            readonlyBtn.addEventListener('click', () => {
                const readonly = this.editor.getReadOnly();
                this.editor.setReadOnly(!readonly);
                readonlyBtn.classList.toggle('active');
                this.showToast(readonly ? 'Editable' : 'Read Only', 'info');
            });
        }
        
        // ===== KEYBOARD SHORTCUTS =====
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.saveYAML();
            }
            if ((e.ctrlKey || e.metaKey) && e.key === 'o') {
                e.preventDefault();
                const fileSelect = document.getElementById('fileSelector');
                if (fileSelect) fileSelect.click();
            }
            if ((e.ctrlKey || e.metaKey) && e.key === ' ') {
                e.preventDefault();
                this.editor.execCommand('startAutocomplete');
            }
        });
        
        // ===== SET UP FILE SELECTOR =====
        const fileSelect = document.getElementById('fileSelector');
        if (fileSelect) {
            const files = await this.listFiles();
            
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
            
            // File selection change handler
            fileSelect.addEventListener('change', (e) => {
                const filename = e.target.value;
                if (filename) {
                    this.loadFileFromServer(filename);
                }
            });
            
            if (files.length > 0) {
                fileSelect.value = files[0];
                this.currentFile = files[0];
                await this.loadFileFromServer(files[0]);
            }
        }
        
        this.updateStatusBar();
        
        console.log('✅ Editor ready');
        console.log('🎨 Theme:', detectedTheme);
        console.log('🔑 Press Ctrl+Space or click 💡 for autocomplete');
        console.log('📝 Available schema properties:', this.allSuggestions.map(s => s.caption).join(', '));
        console.log('📡 Using endpoints:', this.apiEndpoints);
    }
}

// ===== INITIALIZE ON DOM READY =====
document.addEventListener('DOMContentLoaded', function() {
    const editor = new YAMLEditor();
});