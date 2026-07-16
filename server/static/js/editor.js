// ===== YAML EDITOR HELPER CLASS =====
class YAMLEditorHelper {
    constructor() {
        this.editor = null;
        this.schemaData = null;
        this.allSuggestions = [];
        this.currentFile = '';
        this.yamlContent = '';
        this.apiEndpoints = {};
        this.valueSuggestions = [];
        this.schemaHierarchy = {};
        this.completer = null;
        this.isInitialized = false;
        this.TokenIterator = null;
        this.existingKeys = new Set();
        this.lastContext = null;
    }

    // ===== INITIALIZATION =====
    async initialize() {
        if (this.isInitialized) {
            console.warn('⚠️ Editor already initialized');
            return;
        }

        console.log('🚀 Initializing YAML Editor Helper...');
        
        try {
            await this.loadACEExtensions();
            this.getApiEndpoints();
            await this.loadSchema();
            this.buildSuggestionsAndHierarchy();
            this.setupEditor();
            this.registerCompleter();
            this.setupACECommands();
            this.setupUIEventListeners();
            await this.loadFileList();
            this.updateStatusBar();
            
            this.isInitialized = true;
            console.log('✅ YAML Editor Helper initialized successfully');
            this.showReadyState();
        } catch (error) {
            console.error('❌ Failed to initialize editor:', error);
            this.showToast('Failed to initialize editor: ' + error.message, 'error');
        }
    }

    // ===== ACE EXTENSIONS =====
    async loadACEExtensions() {
        try {
            ace.require("ace/ext/language_tools");
            console.log('✅ ACE language tools loaded');
        } catch (e) {
            console.warn('Could not load ACE language tools:', e);
        }
        try {
            this.TokenIterator = ace.require("ace/token_iterator").TokenIterator;
            console.log('✅ ACE token iterator loaded');
        } catch (e) {
            console.warn('Could not load ACE token iterator:', e);
        }
    }

    // ===== API ENDPOINTS =====
    getApiEndpoints() {
        const wrapper = document.querySelector('.yaml-editor-wrapper');
        if (wrapper) {
            this.apiEndpoints.schema = wrapper.dataset.schema || '';
            this.apiEndpoints.list = wrapper.dataset.list || '';
            this.apiEndpoints.load = wrapper.dataset.load || '';
            this.apiEndpoints.save = wrapper.dataset.save || '';
            console.log('📡 API Endpoints configured:', this.apiEndpoints);
        } else {
            console.warn('⚠️ No .yaml-editor-wrapper found');
        }
    }

    // ===== SCHEMA LOADING =====
    async loadSchema() {
        try {
            const schemaUrl = this.apiEndpoints.schema;
            if (!schemaUrl) {
                console.warn('No schema endpoint configured');
                this.schemaData = { schema: {}, data: {} };
                return;
            }

            console.log('📡 Loading schema from:', schemaUrl);
            const response = await fetch(schemaUrl);
            
            if (!response.ok) {
                console.error('Failed to load schema:', response.status);
                this.schemaData = { schema: {}, data: {} };
                return;
            }

            const data = await response.json();
            
            if (data.schema) {
                this.schemaData = data;
            } else if (data.properties) {
                this.schemaData = { schema: data, data: {} };
            } else {
                this.schemaData = { schema: data, data: {} };
            }
            
            console.log('✅ Schema loaded successfully');
            console.log('📊 Schema properties:', Object.keys(this.schemaData.schema.properties || {}));
        } catch (e) {
            console.error('Failed to load schema from endpoint:', e);
            this.schemaData = { schema: {}, data: {} };
            this.showToast('⚠️ Failed to load schema, using empty schema', 'error');
        }
    }

    // ===== SUGGESTIONS AND HIERARCHY =====
    buildSuggestionsAndHierarchy() {
        this.schemaHierarchy = this.buildSchemaHierarchy(this.schemaData.schema);
        this.allSuggestions = this.buildSuggestions(this.schemaData.schema);
        this.valueSuggestions = this.getValueSuggestions();
        console.log(`📝 Built ${this.allSuggestions.length} property suggestions and ${this.valueSuggestions.length} value suggestions`);
    }

    buildSchemaHierarchy(schema, path = '') {
        const hierarchy = {};
        if (!schema || typeof schema !== 'object') return hierarchy;
        
        if (schema.properties) {
            Object.keys(schema.properties).forEach(key => {
                const prop = schema.properties[key];
                const fullPath = path ? `${path}.${key}` : key;
                
                hierarchy[fullPath] = {
                    key: key,
                    path: fullPath,
                    type: prop.type,
                    properties: prop.properties ? Object.keys(prop.properties) : [],
                    description: prop.description || '',
                    title: prop.title || key,
                    parent: path || null
                };
                
                if (prop.type === 'object' || (Array.isArray(prop.type) && prop.type.includes('object'))) {
                    if (prop.properties) {
                        const nested = this.buildSchemaHierarchy(prop, fullPath);
                        Object.assign(hierarchy, nested);
                    }
                }
            });
        }
        return hierarchy;
    }

    buildSuggestions(schema, path = '') {
        const suggestions = [];
        if (!schema || typeof schema !== 'object') return suggestions;
        
        if (schema.properties) {
            Object.keys(schema.properties).forEach(key => {
                const prop = schema.properties[key];
                let typeDesc = Array.isArray(prop.type) ? prop.type.join('|') : prop.type;
                typeDesc = typeDesc || 'property';
                
                if (key.startsWith('#') || key.startsWith('//') || key.startsWith('/*')) {
                    return;
                }
                
                suggestions.push({
                    caption: key,
                    value: `${key}: `,
                    meta: prop.title || typeDesc,
                    score: 100,
                    type: 'property',
                    description: prop.description || '',
                    path: path ? `${path}.${key}` : key,
                    parentPath: path || null,
                    depth: path ? path.split('.').length : 0,
                    isObject: prop.type === 'object' || (Array.isArray(prop.type) && prop.type.includes('object'))
                });
                
                if (prop.type === 'object' || (Array.isArray(prop.type) && prop.type.includes('object'))) {
                    if (prop.properties) {
                        const nestedPath = path ? `${path}.${key}` : key;
                        suggestions.push(...this.buildSuggestions(prop, nestedPath));
                    }
                }
            });
        }
        return suggestions;
    }

    getValueSuggestions() {
        const words = [];
        if (!this.schemaData || !this.schemaData.data) return words;
        
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
        
        collectValues(this.schemaData.data);
        return [...new Set(words)];
    }

    // ===== GET EXISTING KEYS AT CURRENT LEVEL =====
    getExistingKeysAtLevel(pos) {
        const session = this.editor.session;
        const currentLine = session.getLine(pos.row);
        const currentIndent = currentLine.match(/^\s*/)[0].length;
        const existingKeys = new Set();
        
        // Scan upward to find all keys at the same indent level
        for (let i = pos.row - 1; i >= 0; i--) {
            const line = session.getLine(i);
            const trimmed = line.trim();
            
            if (!trimmed || trimmed.startsWith('#')) continue;
            
            const indent = line.match(/^\s*/)[0].length;
            const match = trimmed.match(/^([a-zA-Z_][a-zA-Z0-9_\-]*)\s*:/);
            
            if (match && indent === currentIndent) {
                existingKeys.add(match[1]);
            }
            
            // Stop if we hit a line with less indent (parent level)
            if (indent < currentIndent) {
                break;
            }
        }
        
        return existingKeys;
    }

    // ===== GET PARENT CONTEXT =====
    getParentContext(pos) {
        const session = this.editor.session;
        const currentLine = session.getLine(pos.row);
        const currentIndent = currentLine.match(/^\s*/)[0].length;
        
        // If we're on an indented line, look for the parent
        if (currentIndent > 0) {
            for (let i = pos.row - 1; i >= 0; i--) {
                const line = session.getLine(i);
                const trimmed = line.trim();
                
                if (!trimmed || trimmed.startsWith('#')) continue;
                
                const indent = line.match(/^\s*/)[0].length;
                const match = trimmed.match(/^([a-zA-Z_][a-zA-Z0-9_\-]*)\s*:/);
                
                if (match && indent < currentIndent) {
                    const key = match[1];
                    const suggestion = this.allSuggestions.find(s => s.caption === key);
                    return {
                        key: key,
                        path: suggestion ? suggestion.path || key : key,
                        indent: indent
                    };
                }
            }
        }
        
        return null;
    }

    // ===== CONTEXT DETECTION =====
    getCurrentContext(pos) {
        const session = this.editor.session;
        const currentLine = session.getLine(pos.row);
        const trimmedLine = currentLine.trim();
        const currentIndent = currentLine.match(/^\s*/)[0].length;
        
        // Get existing keys at this level
        const existingKeys = this.getExistingKeysAtLevel(pos);
        this.existingKeys = existingKeys;
        
        let contextPath = '';
        let foundContext = false;
        let isOnKeyLine = false;
        let parentContext = null;
        
        // Check if we're on a line that already has a key
        const keyMatch = trimmedLine.match(/^([a-zA-Z_][a-zA-Z0-9_\-]*)\s*:/);
        if (keyMatch) {
            isOnKeyLine = true;
            const key = keyMatch[1];
            const suggestion = this.allSuggestions.find(s => s.caption === key);
            contextPath = suggestion ? suggestion.path || key : key;
            foundContext = true;
        }
        
        // If we're not on a key line, try to find the parent
        if (!foundContext) {
            // Check if this is an indented line (child of something)
            if (currentIndent > 0) {
                const parent = this.getParentContext(pos);
                if (parent) {
                    parentContext = parent;
                    // If the parent is an object, we should show its properties
                    const parentSuggestion = this.allSuggestions.find(s => s.caption === parent.key);
                    if (parentSuggestion && parentSuggestion.isObject) {
                        contextPath = parentSuggestion.path || parent.key;
                        foundContext = true;
                    } else {
                        // Parent is not an object, treat as root context
                        contextPath = '';
                        foundContext = false;
                    }
                }
            }
            
            // If no parent found, check if there's a key on the same line
            if (!foundContext) {
                const match = currentLine.match(/^([a-zA-Z_][a-zA-Z0-9_\-]*)\s*:/);
                if (match) {
                    const key = match[1];
                    const suggestion = this.allSuggestions.find(s => s.caption === key);
                    contextPath = suggestion ? suggestion.path || key : key;
                    foundContext = true;
                    isOnKeyLine = true;
                }
            }
        }
        
        // Get sibling properties from schema
        let siblingProperties = [];
        let childProperties = [];
        
        if (foundContext && contextPath) {
            const contextSuggestion = this.allSuggestions.find(s => s.path === contextPath);
            const parentPath = contextSuggestion ? contextSuggestion.parentPath : null;
            
            // Get child properties (if context is an object)
            if (contextSuggestion && contextSuggestion.isObject) {
                childProperties = this.allSuggestions.filter(s => 
                    s.parentPath === contextPath &&
                    !existingKeys.has(s.caption)
                );
            }
            
            // Get sibling properties (same parent)
            if (parentPath !== null) {
                siblingProperties = this.allSuggestions.filter(s => 
                    s.parentPath === parentPath && 
                    s.path !== contextPath &&
                    !existingKeys.has(s.caption)
                );
            } else {
                siblingProperties = this.allSuggestions.filter(s => 
                    !s.parentPath && 
                    s.path !== contextPath &&
                    !existingKeys.has(s.caption)
                );
            }
        }
        
        // Determine what to suggest based on cursor position
        let suggestedProperties = [];
        
        if (isOnKeyLine) {
            // We're on a line with a key - suggest children
            suggestedProperties = childProperties;
        } else if (currentIndent > 0 && !trimmedLine) {
            // We're on an empty indented line - suggest children of the parent
            if (parentContext) {
                const parentSuggestion = this.allSuggestions.find(s => s.caption === parentContext.key);
                if (parentSuggestion && parentSuggestion.isObject) {
                    suggestedProperties = this.allSuggestions.filter(s => 
                        s.parentPath === (parentSuggestion.path || parentContext.key) &&
                        !existingKeys.has(s.caption)
                    );
                } else {
                    suggestedProperties = this.allSuggestions.filter(s => 
                        !s.parentPath &&
                        !existingKeys.has(s.caption)
                    );
                }
            } else {
                // No parent context, show root properties
                suggestedProperties = this.allSuggestions.filter(s => 
                    !s.parentPath &&
                    !existingKeys.has(s.caption)
                );
            }
        } else if (currentIndent === 0 && !trimmedLine) {
            // Empty line at root - show root properties
            suggestedProperties = this.allSuggestions.filter(s => 
                !s.parentPath &&
                !existingKeys.has(s.caption)
            );
        } else {
            // Fallback: show context children or siblings
            if (childProperties.length > 0) {
                suggestedProperties = childProperties;
            } else if (siblingProperties.length > 0) {
                suggestedProperties = siblingProperties;
            } else {
                suggestedProperties = this.allSuggestions.filter(s => 
                    !existingKeys.has(s.caption)
                );
            }
        }
        
        return { 
            path: contextPath, 
            indent: currentIndent, 
            found: foundContext,
            isOnKeyLine: isOnKeyLine,
            existingKeys: existingKeys,
            suggestedProperties: suggestedProperties,
            childProperties: childProperties,
            siblingProperties: siblingProperties,
            parentContext: parentContext
        };
    }

    getChildProperties(contextPath) {
        if (!contextPath) return [];
        
        const existingKeys = this.existingKeys || new Set();
        
        const children = this.allSuggestions.filter(sug => {
            const parentPath = sug.parentPath || '';
            return parentPath === contextPath && !existingKeys.has(sug.caption);
        });
        
        if (children.length === 0) {
            const contextSuggestion = this.allSuggestions.find(s => s.path === contextPath);
            if (contextSuggestion) {
                const hierarchyKeys = Object.keys(this.schemaHierarchy);
                const contextKey = hierarchyKeys.find(k => k === contextPath);
                if (contextKey && this.schemaHierarchy[contextKey]) {
                    const propNames = this.schemaHierarchy[contextKey].properties || [];
                    return this.allSuggestions.filter(sug => {
                        return propNames.includes(sug.caption) && 
                               sug.parentPath === contextPath &&
                               !existingKeys.has(sug.caption);
                    });
                }
            }
        }
        return children;
    }

    // ===== YAML UTILITIES =====
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

    // ===== FILE OPERATIONS =====
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
            
            const fileDisplay = document.getElementById('currentFileDisplay');
            if (fileDisplay) fileDisplay.textContent = '📄 ' + filename;
            
            this.showToast('✅ Loaded: ' + filename, 'success');
            
        } catch (e) {
            console.error('Failed to load file:', e);
            this.showToast('❌ Network error loading file', 'error');
        }
    }

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
                headers: { 'Content-Type': 'text/plain' },
                body: content
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                this.showToast('❌ Error: ' + (errorData.detail || 'Unknown error'), 'error');
                return;
            }
            
            const result = await response.json();
            this.yamlContent = content;
            this.showToast(result.message || '✅ Saved: ' + this.currentFile, 'success');
            
        } catch (e) {
            this.showToast('❌ Network error: ' + e.message, 'error');
            console.error('Save error:', e);
        }
    }

    async loadFileList() {
        const fileSelect = document.getElementById('fileSelector');
        if (!fileSelect) return;
        
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
        
        if (files.length > 0) {
            fileSelect.value = files[0];
            this.currentFile = files[0];
            await this.loadFileFromServer(files[0]);
        }
    }

    // ===== THEME DETECTION =====
    detectTheme() {
        const url = window.location.hash + window.location.pathname + window.location.search;
        
        if (url.includes('gh_light') || url.includes('light')) {
            return 'github_light_default';
        }
        return 'github_dark';
    }

    // ===== EDITOR SETUP =====
    setupEditor() {
        const detectedTheme = this.detectTheme();
        
        let initialContent = '# YAML Configuration\n\n';
        if (this.schemaData.data && Object.keys(this.schemaData.data).length > 0) {
            initialContent = this.yamlDump(this.schemaData.data);
        }
        
        this.editor = ace.edit("editor");
        this.editor.setTheme("ace/theme/" + detectedTheme);
        this.editor.session.setMode("ace/mode/yaml");
        this.editor.session.setNewLineMode("auto");
        this.editor.setValue(initialContent, -1);
        this.yamlContent = initialContent;
        this.editor.session.setTabSize(2);
        this.editor.session.setUseSoftTabs(true);
        this.editor.setOptions({
            enableBasicAutocompletion: true,
            enableSnippets: false,
            enableLiveAutocompletion: true
        });
        
        const gutter = document.querySelector('.ace_gutter');
        if (gutter) {
            gutter.removeAttribute('aria-hidden');
        }
        
        const themeSelector = document.getElementById('themeSelector');
        if (themeSelector) {
            themeSelector.value = detectedTheme;
        }
    }

    // ===== COMPLETER REGISTRATION =====
    registerCompleter() {
        const self = this;
        
        this.completer = {
            getCompletions: (editor, session, pos, prefix, callback) => {
                self.handleCompletions(editor, session, pos, prefix, callback);
            },
            getDocTooltip: (item) => item.description
        };
        
        if (!this.editor.completers) {
            this.editor.completers = [];
        }
        this.editor.completers = [
            //langTools.snippetCompleter,
            //langTools.textCompleter,
            //langTools.keyWordCompleter,
            this.completer
        ];
    }

    handleCompletions(editor, session, pos, prefix, callback) {
        const line = session.getLine(pos.row);
        const before = line.substring(0, pos.column);
        const trimmedLine = line.trim();
        const context = this.getCurrentContext(pos);
        const searchPrefix = prefix.toLowerCase();
        const afterColon = /:\s*$/.test(before) || /:\s+/.test(before);
        
        let suggestions = [];
        
        // Check if we're after a colon (value context)
        if (afterColon && prefix.length > 0) {
            // Value suggestions
            this.valueSuggestions.forEach(val => {
                if (String(val).toLowerCase().startsWith(searchPrefix)) {
                    suggestions.push({
                        caption: val,
                        value: val,
                        meta: 'value',
                        score: 80
                    });
                }
            });
            
            // Also suggest boolean values
            ['true', 'false'].forEach(val => {
                if (val.startsWith(searchPrefix)) {
                    suggestions.push({
                        caption: val,
                        value: val,
                        meta: 'boolean',
                        score: 90
                    });
                }
            });
        } else {
            // Property suggestions - use the context's suggested properties
            const suggestedProps = context.suggestedProperties || [];
            
            // Add suggestions from context
            suggestedProps.forEach(sug => {
                const lineContent = line.trim();
                if (lineContent.includes(sug.caption + ':')) return;
                
                if (sug.caption.toLowerCase().startsWith(searchPrefix) || searchPrefix === '') {
                    const depthBonus = sug.depth ? 100 - (sug.depth * 10) : 0;
                    const score = sug.isObject ? 1000 + depthBonus : 900 + depthBonus;
                    
                    suggestions.push({
                        caption: sug.caption,
                        value: sug.value,
                        meta: sug.isObject ? '📁 ' + (sug.meta || 'object') : '📄 ' + (sug.meta || 'property'),
                        score: score,
                        description: sug.description || ''
                    });
                }
            });
            
            // If no suggestions from context, show root properties
            if (suggestions.length === 0) {
                this.allSuggestions.forEach(sug => {
                    const lineContent = line.trim();
                    if (lineContent.includes(sug.caption + ':')) return;
                    
                    if (sug.caption.toLowerCase().startsWith(searchPrefix) || searchPrefix === '') {
                        const exists = context.existingKeys && context.existingKeys.has(sug.caption);
                        const score = exists ? 50 : 100;
                        
                        suggestions.push({
                            caption: sug.caption,
                            value: sug.value,
                            meta: (exists ? '⚠️ ' : '') + (sug.meta || 'property'),
                            score: score,
                            description: sug.description || ''
                        });
                    }
                });
            }
        }
        
        // Always add value suggestions as fallback for numbers/booleans
        if (suggestions.length === 0 && prefix.length > 1) {
            this.valueSuggestions.forEach(val => {
                if (String(val).toLowerCase().startsWith(searchPrefix)) {
                    suggestions.push({
                        caption: val,
                        value: val,
                        meta: 'value',
                        score: 50
                    });
                }
            });
            
            // Add number suggestions
            if (/^\d*$/.test(prefix)) {
                suggestions.push({
                    caption: '0',
                    value: '0',
                    meta: 'number',
                    score: 40
                });
            }
        }
        
        // Sort by score and limit
        suggestions.sort((a, b) => (b.score || 0) - (a.score || 0));
        suggestions = suggestions.slice(0, 30);
        
        callback(null, suggestions);
    }

    // ===== ACE COMMANDS =====
    setupACECommands() {
        this.editor.commands.addCommand({
            name: 'saveYAML',
            bindKey: { win: 'Ctrl-S', mac: 'Cmd-S' },
            exec: () => this.saveYAML()
        });

        this.editor.commands.addCommand({
            name: 'openFile',
            bindKey: { win: 'Ctrl-O', mac: 'Cmd-O' },
            exec: () => {
                const fileSelect = document.getElementById('fileSelector');
                if (fileSelect) fileSelect.click();
            }
        });

        this.editor.commands.addCommand({
            name: 'showAutocomplete',
            bindKey: 'Ctrl-Space',
            exec: () => this.editor.execCommand('startAutocomplete')
        });

        this.editor.commands.addCommand({
            name: 'find',
            bindKey: { win: 'Ctrl-F', mac: 'Cmd-F' },
            exec: () => this.editor.execCommand('find')
        });

        this.editor.commands.addCommand({
            name: 'replace',
            bindKey: { win: 'Ctrl-H', mac: 'Cmd-Option-F' },
            exec: () => this.editor.execCommand('replace')
        });
    }

    // ===== UI EVENT LISTENERS =====
    setupUIEventListeners() {
        const updateStatusBar = () => this.updateStatusBar();
        this.editor.session.selection.on('changeCursor', updateStatusBar);
        this.editor.session.on('change', updateStatusBar);

        const fileSelect = document.getElementById('fileSelector');
        if (fileSelect) {
            fileSelect.addEventListener('change', () => this.selectFile());
        }

        this.exposeToWindow();
    }

    exposeToWindow() {
        window.saveYAML = () => this.saveYAML();
        window.selectFile = () => this.selectFile();
        window.showSuggestions = () => this.showSuggestions();
        window.undo = () => this.editor.undo();
        window.redo = () => this.editor.redo();
        window.find = () => this.editor.execCommand('find');
        window.replace = () => this.editor.execCommand('replace');
        window.changeTheme = (theme) => this.changeTheme(theme);
        window.changeMode = (mode) => this.changeMode(mode);
        window.changeFontSize = (size) => this.changeFontSize(size);
        window.toggleWrap = () => this.toggleWrap();
        window.toggleReadOnly = () => this.toggleReadOnly();
    }

    // ===== UI FUNCTIONS =====
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

    showSuggestions() {
        this.editor.focus();
        this.editor.execCommand('startAutocomplete');
    }

    selectFile() {
        const fileSelect = document.getElementById('fileSelector');
        if (fileSelect && fileSelect.value) {
            this.loadFileFromServer(fileSelect.value);
        }
    }

    changeTheme(theme) {
        this.editor.setTheme('ace/theme/' + theme);
        this.showToast('Theme: ' + theme, 'info');
    }

    changeMode(mode) {
        this.editor.session.setMode('ace/mode/' + mode);
        const modeEl = document.getElementById('currentMode');
        if (modeEl) modeEl.textContent = mode.toUpperCase();
        this.showToast('Mode: ' + mode.toUpperCase(), 'info');
    }

    changeFontSize(size) {
        this.editor.setFontSize(size + 'px');
        this.showToast('Font size: ' + size + 'px', 'info');
    }

    toggleWrap() {
        const wrap = this.editor.session.getUseWrapMode();
        this.editor.session.setUseWrapMode(!wrap);
        const wrapBtn = document.getElementById('wrapBtn');
        if (wrapBtn) wrapBtn.classList.toggle('active');
        this.showToast(wrap ? 'Wrap off' : 'Wrap on', 'info');
    }

    toggleReadOnly() {
        const readonly = this.editor.getReadOnly();
        this.editor.setReadOnly(!readonly);
        const readonlyBtn = document.getElementById('readonlyBtn');
        if (readonlyBtn) readonlyBtn.classList.toggle('active');
        this.showToast(readonly ? 'Editable' : 'Read Only', 'info');
    }

    showReadyState() {
        setTimeout(() => {
            const propCount = this.allSuggestions.length;
            const valueCount = this.valueSuggestions.length;
            console.log(`💡 ${propCount} properties, ${valueCount} values available`);
        }, 500);
    }

    // ===== TOAST SYSTEM =====
    showToast(message, type) {
        const toast = document.getElementById('toast');
        if (!toast) {
            console.warn('Toast element not found:', message);
            return;
        }
        toast.textContent = message;
        toast.className = 'yaml-toast ' + type + ' show';
        clearTimeout(toast._timeout);
        toast._timeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
}

// ===== INITIALIZE =====
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🚀 Starting YAML Editor...');
    const editorHelper = new YAMLEditorHelper();
    await editorHelper.initialize();
    window.editorHelper = editorHelper;
    
    const themeToggleBtn = document.querySelector('.theme-toggle-btn');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function() {
            const currentTheme = this.dataset.theme;
            const newTheme = currentTheme && currentTheme.includes('dark') 
                ? 'github_light_default' 
                : 'github_dark';
            editorHelper.changeTheme(newTheme);
        });
    }
});