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
        this.HoverTooltip = null;
        this.tooltip = null;
        this.typeEmojis = {
            'string': '📝',
            'number': '🔢',
            'integer': '🔢',
            'boolean': '✓',
            'object': '📁',
            'array': '📋',
            'null': '⬜'
        };
        this.typeLabels = {
            'string': 'String',
            'number': 'Number',
            'integer': 'Integer',
            'boolean': 'Boolean',
            'object': 'Object',
            'array': 'Array',
            'null': 'Null'
        };
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
            // this.setupHoverTooltip();
            this.setupFeedLoadListeners();
            
            this.isInitialized = true;
            console.log('✅ YAML Editor Helper initialized successfully');
            this.showReadyState();
            this.updatePropertyLegend();
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
        try {
            this.HoverTooltip = ace.require("ace/tooltip").HoverTooltip;
            console.log('✅ ACE hover tooltip loaded');
        } catch (e) {
            console.warn('Could not load ACE hover tooltip:', e);
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
                    parent: path || null,
                    additionalProperties: prop.additionalProperties || null
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

    getTypeInfo(prop) {
        let type = 'unknown';
        let typeDesc = '';
        let isObject = false;
        let isArray = false;
        let isString = false;
        let isNumber = false;
        let isBoolean = false;
        let isNull = false;
        let additionalProperties = null;
        
        if (!prop) {
            return { type: 'unknown', typeDesc: 'Unknown', isObject: false, isArray: false, isString: false, isNumber: false, isBoolean: false, isNull: false, additionalProperties: null };
        }
        
        const propType = prop.type;
        if (Array.isArray(propType)) {
            if (propType.includes('object')) isObject = true;
            if (propType.includes('string')) isString = true;
            if (propType.includes('number') || propType.includes('integer')) isNumber = true;
            if (propType.includes('boolean')) isBoolean = true;
            if (propType.includes('null')) isNull = true;
            if (propType.includes('array')) isArray = true;
            type = propType.join('|');
        } else {
            if (propType === 'object') isObject = true;
            else if (propType === 'string') isString = true;
            else if (propType === 'number' || propType === 'integer') isNumber = true;
            else if (propType === 'boolean') isBoolean = true;
            else if (propType === 'array') isArray = true;
            else if (propType === 'null') isNull = true;
            type = propType || 'unknown';
        }
        
        if (prop.additionalProperties) {
            additionalProperties = prop.additionalProperties;
            if (typeof additionalProperties === 'object' && additionalProperties.type) {
                if (additionalProperties.type === 'string' || additionalProperties.type.includes('string')) {
                    typeDesc = 'Map (str→str)';
                } else if (additionalProperties.type === 'number' || additionalProperties.type === 'integer' || additionalProperties.type.includes('number')) {
                    typeDesc = 'Map (str→num)';
                } else if (additionalProperties.type === 'boolean' || additionalProperties.type.includes('boolean')) {
                    typeDesc = 'Map (str→bool)';
                } else {
                    typeDesc = 'Map (str→' + (additionalProperties.type || 'any') + ')';
                }
            } else {
                typeDesc = 'Map (str→any)';
            }
        } else if (prop.items) {
            if (Array.isArray(prop.items)) {
                typeDesc = 'Array of ' + prop.items.map(i => i.type || 'any').join('|');
            } else if (prop.items.type) {
                const itemType = prop.items.type;
                if (itemType === 'string' || itemType.includes('string')) {
                    typeDesc = 'Array of strings';
                } else if (itemType === 'number' || itemType === 'integer' || itemType.includes('number')) {
                    typeDesc = 'Array of numbers';
                } else if (itemType === 'boolean' || itemType.includes('boolean')) {
                    typeDesc = 'Array of booleans';
                } else if (itemType === 'object' || itemType.includes('object')) {
                    typeDesc = 'Array of objects';
                } else {
                    typeDesc = 'Array of ' + itemType;
                }
            }
            isArray = true;
        } else if (isObject) {
            if (prop.properties) {
                const propCount = Object.keys(prop.properties).length;
                typeDesc = propCount > 0 ? `Object (${propCount} props)` : 'Object';
            } else {
                typeDesc = 'Object';
            }
        } else if (isString) {
            typeDesc = 'String';
        } else if (isNumber) {
            typeDesc = 'Number';
        } else if (isBoolean) {
            typeDesc = 'Boolean';
        } else if (isNull) {
            typeDesc = 'Null';
        } else {
            typeDesc = type || 'Property';
        }
        
        return {
            type: type,
            typeDesc: typeDesc,
            isObject: isObject,
            isArray: isArray,
            isString: isString,
            isNumber: isNumber,
            isBoolean: isBoolean,
            isNull: isNull,
            additionalProperties: additionalProperties
        };
    }

    getTypeEmoji(typeInfo) {
        if (typeInfo.isObject) return '📁';
        if (typeInfo.isArray) return '📋';
        if (typeInfo.isString) return '📝';
        if (typeInfo.isNumber) return '🔢';
        if (typeInfo.isBoolean) return '✓';
        if (typeInfo.isNull) return '⬜';
        return '❓';
    }

    buildSuggestions(schema, path = '') {
        const suggestions = [];
        if (!schema || typeof schema !== 'object') return suggestions;
        
        if (schema.properties) {
            Object.keys(schema.properties).forEach(key => {
                const prop = schema.properties[key];
                const typeInfo = this.getTypeInfo(prop);
                
                if (key.startsWith('#') || key.startsWith('//') || key.startsWith('/*')) {
                    return;
                }
                
                const emoji = this.getTypeEmoji(typeInfo);
                const meta = typeInfo.typeDesc || 'Property';
                
                suggestions.push({
                    caption: key,
                    value: `${key}: `,
                    meta: `${emoji} ${meta}`,
                    score: 100,
                    type: 'property',
                    description: prop.description || '',
                    path: path ? `${path}.${key}` : key,
                    parentPath: path || null,
                    depth: path ? path.split('.').length : 0,
                    isObject: typeInfo.isObject,
                    typeInfo: typeInfo,
                    schema: prop
                });
                
                if (typeInfo.isObject && prop.properties) {
                    const nestedPath = path ? `${path}.${key}` : key;
                    suggestions.push(...this.buildSuggestions(prop, nestedPath));
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
        
        for (let i = pos.row - 1; i >= 0; i--) {
            const line = session.getLine(i);
            const trimmed = line.trim();
            
            if (!trimmed || trimmed.startsWith('#')) continue;
            
            const indent = line.match(/^\s*/)[0].length;
            const match = trimmed.match(/^([a-zA-Z_][a-zA-Z0-9_\-]*)\s*:/);
            
            if (match && indent === currentIndent) {
                existingKeys.add(match[1]);
            }
            
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
        
        const existingKeys = this.getExistingKeysAtLevel(pos);
        this.existingKeys = existingKeys;
        
        let contextPath = '';
        let foundContext = false;
        let isOnKeyLine = false;
        let parentContext = null;
        
        const keyMatch = trimmedLine.match(/^([a-zA-Z_][a-zA-Z0-9_\-]*)\s*:/);
        if (keyMatch) {
            isOnKeyLine = true;
            const key = keyMatch[1];
            const suggestion = this.allSuggestions.find(s => s.caption === key);
            contextPath = suggestion ? suggestion.path || key : key;
            foundContext = true;
        }
        
        if (!foundContext) {
            if (currentIndent > 0) {
                const parent = this.getParentContext(pos);
                if (parent) {
                    parentContext = parent;
                    const parentSuggestion = this.allSuggestions.find(s => s.caption === parent.key);
                    if (parentSuggestion && parentSuggestion.isObject) {
                        contextPath = parentSuggestion.path || parent.key;
                        foundContext = true;
                    } else {
                        contextPath = '';
                        foundContext = false;
                    }
                }
            }
            
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
        
        let siblingProperties = [];
        let childProperties = [];
        let valueType = null;
        
        if (foundContext && contextPath) {
            const contextSuggestion = this.allSuggestions.find(s => s.path === contextPath);
            const parentPath = contextSuggestion ? contextSuggestion.parentPath : null;
            
            if (contextSuggestion && contextSuggestion.isObject) {
                childProperties = this.allSuggestions.filter(s => 
                    s.parentPath === contextPath &&
                    !existingKeys.has(s.caption)
                );
                if (contextSuggestion.typeInfo) {
                    valueType = contextSuggestion.typeInfo;
                }
            }
            
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
        
        let suggestedProperties = [];
        
        if (isOnKeyLine) {
            suggestedProperties = childProperties;
        } else if (currentIndent > 0 && !trimmedLine) {
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
                suggestedProperties = this.allSuggestions.filter(s => 
                    !s.parentPath &&
                    !existingKeys.has(s.caption)
                );
            }
        } else if (currentIndent === 0 && !trimmedLine) {
            suggestedProperties = this.allSuggestions.filter(s => 
                !s.parentPath &&
                !existingKeys.has(s.caption)
            );
        } else {
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
            parentContext: parentContext,
            valueType: valueType
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

    // ===== UPDATE PROPERTY LEGEND =====
    updatePropertyLegend() {
        const legendEl = document.getElementById('propertyLegend');
        if (!legendEl) return;
        
        const types = [
            { emoji: '📁', label: 'Object' },
            { emoji: '📋', label: 'Array' },
            { emoji: '📝', label: 'String' },
            { emoji: '🔢', label: 'Number' },
            { emoji: '✓', label: 'Boolean' },
            { emoji: '⬜', label: 'Null' },
            { emoji: '🗺️', label: 'Map (str→str)' },
            { emoji: '🗺️', label: 'Map (str→num)' }
        ];
        
        let html = '<span style="font-size: 0.9em; opacity: 0.7;">Legend: </span>';
        types.forEach(t => {
            html += `<span style="margin: 0 8px; font-size: 0.85em;">${t.emoji} ${t.label}</span>`;
        });
        
        legendEl.innerHTML = html;
    }

    // ===== SETUP HOVER TOOLTIP =====
    setupHoverTooltip() {
        if (!this.HoverTooltip) {
            console.warn('HoverTooltip not available');
            return;
        }

        const self = this;
        
        // Create tooltip instance
        this.tooltip = new this.HoverTooltip(this.editor);
        
        // Custom tooltip content provider
        this.tooltip.setContentProvider(function(editor, pos) {
            const session = editor.session;
            const token = session.getTokenAt(pos.row, pos.column);
            
            if (!token) return null;
            
            // Get the current line and check for YAML key
            const line = session.getLine(pos.row);
            const match = line.match(/^([a-zA-Z_][a-zA-Z0-9_\-]*)\s*:/);
            
            if (!match) return null;
            
            const key = match[1];
            const suggestion = self.allSuggestions.find(s => s.caption === key);
            
            if (!suggestion) return null;
            
            // Build tooltip content
            let content = `<div style="max-width: 400px; padding: 8px;">`;
            content += `<strong>${suggestion.caption}</strong><br>`;
            
            if (suggestion.description) {
                content += `<span style="color: #888; font-size: 0.9em;">${suggestion.description}</span><br>`;
            }
            
            // Show type info
            const typeInfo = suggestion.typeInfo;
            if (typeInfo) {
                const emoji = self.getTypeEmoji(typeInfo);
                content += `<span style="font-size: 0.9em;">${emoji} Type: ${typeInfo.typeDesc}</span><br>`;
            }
            
            // Show children if it's an object
            if (suggestion.isObject) {
                const children = self.getChildProperties(suggestion.path);
                if (children.length > 0) {
                    content += `<br><span style="font-weight: bold;">Children:</span><br>`;
                    content += `<div style="padding-left: 10px; font-size: 0.9em;">`;
                    children.slice(0, 10).forEach(child => {
                        const childEmoji = child.typeInfo ? self.getTypeEmoji(child.typeInfo) : '📄';
                        content += `<span>${childEmoji} ${child.caption}</span><br>`;
                    });
                    if (children.length > 10) {
                        content += `<span style="color: #888;">... and ${children.length - 10} more</span>`;
                    }
                    content += `</div>`;
                }
            }
            
            // Show parent info
            if (suggestion.parentPath) {
                const parent = self.allSuggestions.find(s => s.path === suggestion.parentPath);
                if (parent) {
                    content += `<br><span style="font-size: 0.85em; color: #888;">Parent: ${parent.caption}</span>`;
                }
            }
            
            content += `</div>`;
            return content;
        });
        
        // Enable tooltip
        this.tooltip.enable();
    }

    // ===== SETUP FEED LOAD LISTENERS =====
    setupFeedLoadListeners() {
        const feedElements = document.querySelectorAll('.edit-feed');
        feedElements.forEach(el => {
            // Add our event listener
            el.addEventListener('click', (e) => {
                const feedName = el.getAttribute('name');
                if (feedName) {
                    this.loadFeed(feedName);
                }
            });
            // Add cursor pointer
            el.style.cursor = 'pointer';
        });
        console.log(`📡 Added feed load listeners to ${feedElements.length} elements`);
    }


    // ===== LOAD FEED =====
    loadFeed(feedName) {
        if (!feedName) {
            this.showToast('❌ No feed name provided', 'error');
            return;
        }
        
        console.log(`📂 Loading feed: ${feedName}`);
        this.showToast(`📂 Loading feed: ${feedName}...`, 'info');
        
        // Find the file in the list
        const fileSelect = document.getElementById('fileSelector');
        if (fileSelect) {
            // Check if the feed exists in the list
            let found = false;
            for (let i = 0; i < fileSelect.options.length; i++) {
                if (fileSelect.options[i].value === feedName) {
                    fileSelect.value = feedName;
                    found = true;
                    break;
                }
            }
            
            if (found) {
                // Call selectFile directly to load the file
                this.selectFile();
            } else {
                // Try loading directly
                this.loadFileFromServer(feedName);
            }
        } else {
            this.loadFileFromServer(feedName);
        }
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
        
        if (url.includes('light')) {
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
            enableSnippets: true,
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
        this.editor.completers = [this.completer];
    }

    handleCompletions(editor, session, pos, prefix, callback) {
        const line = session.getLine(pos.row);
        const before = line.substring(0, pos.column);
        const trimmedLine = line.trim();
        const context = this.getCurrentContext(pos);
        const searchPrefix = prefix.toLowerCase();
        const afterColon = /:\s*$/.test(before) || /:\s+/.test(before) || /:\s*$/.test(trimmedLine);
        
        let suggestions = [];
        
        // Check if we're after a colon or at the start of a value (after space)
        if (afterColon || (trimmedLine.includes(':') && prefix.length > 0)) {
            // Get the type info for the current context
            let typeInfo = context.valueType;
            if (!typeInfo) {
                const contextSuggestion = this.allSuggestions.find(s => s.path === context.path);
                if (contextSuggestion && contextSuggestion.typeInfo) {
                    typeInfo = contextSuggestion.typeInfo;
                }
            }
            
            // Add type-specific suggestions
            if (typeInfo) {
                if (typeInfo.isBoolean) {
                    suggestions.push({
                        caption: 'true',
                        value: ' true',
                        meta: '✓ Boolean',
                        score: 100
                    });
                    suggestions.push({
                        caption: 'false',
                        value: ' false',
                        meta: '✓ Boolean',
                        score: 100
                    });
                }
                if (typeInfo.isNumber || typeInfo.isString) {
                    if (typeInfo.isNumber) {
                        suggestions.push({
                            caption: '0',
                            value: ' 0',
                            meta: '🔢 Number',
                            score: 90
                        });
                        suggestions.push({
                            caption: '0.0',
                            value: ' 0.0',
                            meta: '🔢 Float',
                            score: 90
                        });
                    }
                    if (typeInfo.isString) {
                        suggestions.push({
                            caption: '""',
                            value: ' ""',
                            meta: '📝 String (empty)',
                            score: 90
                        });
                    }
                }
                if (typeInfo.isObject) {
                    // If object has properties, suggest a template with children
                    const contextSuggestion = this.allSuggestions.find(s => s.path === context.path);
                    if (contextSuggestion) {
                        const children = this.getChildProperties(context.path);
                        if (children.length > 0) {
                            // Determine the current indentation level
                            const currentLine = session.getLine(pos.row);
                            const currentIndent = currentLine.match(/^\s*/)[0].length;
                            const indentStr = '  '.repeat(currentIndent / 2 + 1); // Add one level of indentation
                            
                            // Build template with proper indentation
                            let template = '\n';
                            children.forEach((child) => {
                                // Determine child type for value hint
                                let valueHint = '';
                                if (child.typeInfo) {
                                    if (child.typeInfo.isString) valueHint = ' ""';
                                    else if (child.typeInfo.isNumber) valueHint = ' 0';
                                    else if (child.typeInfo.isBoolean) valueHint = ' false';
                                    else if (child.typeInfo.isObject) valueHint = ' {}';
                                    else if (child.typeInfo.isArray) valueHint = ' []';
                                    else if (child.typeInfo.isNull) valueHint = ' null';
                                }
                                template += `${indentStr}${child.caption}:${valueHint}\n`;
                            });
                            // Remove trailing newline for cleaner display
                            template = template.trimEnd();
                            
                            suggestions.push({
                                caption: '📁 Object Template',
                                value: template,
                                meta: '📁 Object with ' + children.length + ' props',
                                score: 85
                            });
                        }
                    }
                    
                    // Check for additionalProperties (Map/object with key-value pairs)
                    if (typeInfo.additionalProperties) {
                        const addProps = typeInfo.additionalProperties;
                        if (typeof addProps === 'object' && addProps.type) {
                            let valueType = addProps.type;
                            if (Array.isArray(valueType)) {
                                valueType = valueType.join('|');
                            }
                            
                            // Determine the current indentation level
                            const currentLine = session.getLine(pos.row);
                            const currentIndent = currentLine.match(/^\s*/)[0].length;
                            const indentStr = '  '.repeat(currentIndent / 2 + 1);
                            
                            // Suggest a key-value pair template
                            let template = '\n' + indentStr + 'key: ';
                            if (valueType === 'string' || valueType.includes('string')) {
                                template += '""';
                                suggestions.push({
                                    caption: '🗺️ Map (str→str)',
                                    value: template,
                                    meta: '🗺️ Add string key → string value',
                                    score: 85
                                });
                            } else if (valueType === 'number' || valueType === 'integer' || valueType.includes('number')) {
                                template += '0';
                                suggestions.push({
                                    caption: '🗺️ Map (str→num)',
                                    value: template,
                                    meta: '🗺️ Add string key → number value',
                                    score: 85
                                });
                            } else if (valueType === 'boolean' || valueType.includes('boolean')) {
                                template += 'false';
                                suggestions.push({
                                    caption: '🗺️ Map (str→bool)',
                                    value: template,
                                    meta: '🗺️ Add string key → boolean value',
                                    score: 85
                                });
                            } else {
                                template += 'value';
                                suggestions.push({
                                    caption: '🗺️ Map (str→any)',
                                    value: template,
                                    meta: '🗺️ Add string key → any value',
                                    score: 85
                                });
                            }
                        }
                    }
                }

                if (typeInfo.isArray) {
                    // Array with items based on type
                    const contextSuggestion = this.allSuggestions.find(s => s.path === context.path);
                    if (contextSuggestion && contextSuggestion.schema) {
                        const schema = contextSuggestion.schema;
                        if (schema.items) {
                            const itemsType = schema.items;
                            let itemType = 'any';
                            let isObjectItem = false;
                            let isStringItem = false;
                            let isNumberItem = false;
                            let isBooleanItem = false;
                            
                            if (Array.isArray(itemsType)) {
                                itemType = itemsType.map(i => i.type || 'any').join('|');
                            } else if (itemsType.type) {
                                const type = itemsType.type;
                                if (Array.isArray(type)) {
                                    itemType = type.join('|');
                                    if (type.includes('object')) isObjectItem = true;
                                    if (type.includes('string')) isStringItem = true;
                                    if (type.includes('number') || type.includes('integer')) isNumberItem = true;
                                    if (type.includes('boolean')) isBooleanItem = true;
                                } else {
                                    itemType = type;
                                    if (type === 'object' || type.includes('object')) isObjectItem = true;
                                    else if (type === 'string' || type.includes('string')) isStringItem = true;
                                    else if (type === 'number' || type === 'integer' || type.includes('number')) isNumberItem = true;
                                    else if (type === 'boolean' || type.includes('boolean')) isBooleanItem = true;
                                }
                            }
                            
                            // Determine the current indentation level
                            const currentLine = session.getLine(pos.row);
                            const currentIndent = currentLine.match(/^\s*/)[0].length;
                            const indentStr = '  '.repeat(currentIndent / 2 + 1);
                            
                            // Suggest an array item on the next line with proper indentation
                            if (isObjectItem) {
                                // Object item - look for its properties
                                let template = '\n' + indentStr + '- ';
                                if (itemsType.properties) {
                                    const objProps = Object.keys(itemsType.properties);
                                    if (objProps.length > 0) {
                                        // Show first property as example
                                        const firstProp = objProps[0];
                                        const firstPropSchema = itemsType.properties[firstProp];
                                        let valueHint = '';
                                        if (firstPropSchema) {
                                            const type = firstPropSchema.type;
                                            if (type === 'string' || (Array.isArray(type) && type.includes('string'))) {
                                                valueHint = ' ""';
                                            } else if (type === 'number' || type === 'integer' || (Array.isArray(type) && (type.includes('number') || type.includes('integer')))) {
                                                valueHint = ' 0';
                                            } else if (type === 'boolean' || (Array.isArray(type) && type.includes('boolean'))) {
                                                valueHint = ' false';
                                            } else if (type === 'object' || (Array.isArray(type) && type.includes('object'))) {
                                                valueHint = ' {}';
                                            }
                                        }
                                        template += `${firstProp}:${valueHint}`;
                                        if (objProps.length > 1) {
                                            template += `  # +${objProps.length - 1} more props`;
                                        }
                                    } else {
                                        template += '"key": 0.0';
                                    }
                                } else {
                                    template += '"key": 0.0';
                                }
                                suggestions.push({
                                    caption: '📋 Object item',
                                    value: template,
                                    meta: '📋 Add object item to array',
                                    score: 85
                                });
                            } else if (isStringItem) {
                                suggestions.push({
                                    caption: '📋 String item',
                                    value: '\n' + indentStr + '- ""',
                                    meta: '📋 Add string item to array',
                                    score: 85
                                });
                            } else if (isNumberItem) {
                                suggestions.push({
                                    caption: '📋 Number item',
                                    value: '\n' + indentStr + '- 0',
                                    meta: '📋 Add number item to array',
                                    score: 85
                                });
                            } else if (isBooleanItem) {
                                suggestions.push({
                                    caption: '📋 Boolean item',
                                    value: '\n' + indentStr + '- false',
                                    meta: '📋 Add boolean item to array',
                                    score: 85
                                });
                            } else {
                                // Generic item
                                suggestions.push({
                                    caption: '📋 Array item',
                                    value: '\n' + indentStr + '- ',
                                    meta: '📋 Add item to array',
                                    score: 85
                                });
                            }
                        }
                    }
                }
                if (typeInfo.isNull) {
                    suggestions.push({
                        caption: 'null',
                        value: 'null',
                        meta: '⬜ Null',
                        score: -100
                    });
                }
            }
            
            // Value suggestions from data
            this.valueSuggestions.forEach(val => {
                if (String(val).toLowerCase().startsWith(searchPrefix)) {
                    suggestions.push({
                        caption: val,
                        value: val,
                        meta: '📊 Value',
                        score: 80
                    });
                }
            });
        }
        
        // Property suggestions (when not after colon)
        if (!afterColon || suggestions.length === 0) {
            const suggestedProps = context.suggestedProperties || [];
            
            suggestedProps.forEach(sug => {
                const lineContent = line.trim();
                if (lineContent.includes(sug.caption + ':')) return;
                
                if (sug.caption.toLowerCase().startsWith(searchPrefix) || searchPrefix === '') {
                    const depthBonus = sug.depth ? 100 - (sug.depth * 10) : 0;
                    const score = sug.isObject ? 1000 + depthBonus : 900 + depthBonus;
                    
                    suggestions.push({
                        caption: sug.caption,
                        value: sug.value,
                        meta: sug.meta || 'Property',
                        score: score,
                        description: sug.description || ''
                    });
                }
            });
            
            if (suggestions.length === 0) {
                this.allSuggestions.forEach(sug => {
                    const lineContent = line.trim();
                    if (lineContent.includes(sug.caption + ':')) return;
                    
                    if (sug.caption.toLowerCase().startsWith(searchPrefix) || searchPrefix === '') {
                        const exists = context.existingKeys && context.existingKeys.has(sug.caption);
                        const score = exists ? 50 : 100;
                        
                        const meta = exists ? '⚠️ ' + sug.meta : sug.meta;
                        
                        suggestions.push({
                            caption: sug.caption,
                            value: sug.value,
                            meta: meta || 'Property',
                            score: score,
                            description: sug.description || ''
                        });
                    }
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
        window.loadFeed = (feedName) => this.loadFeed(feedName);
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
                ? 'github_dark' 
                : 'github_light_default';
            editorHelper.changeTheme(newTheme);
        });
    }
});