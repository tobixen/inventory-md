/**
 * md-viewer-common.js
 * Shared JavaScript utilities for markdown-based viewers
 *
 * Used by: diary-md, inventory-md
 * Source: https://github.com/tobixen/inventory-md
 * License: MIT
 *
 * @version 1.0.0
 * @date 2026-01-23
 */

class MarkdownViewerBase {
    /**
     * Base class for markdown viewers with search, filtering, and export
     * @param {string} dataUrl - URL to fetch JSON data from
     * @param {string} aliasesUrl - URL to fetch aliases JSON (optional)
     */
    constructor(dataUrl, aliasesUrl = null) {
        this.dataUrl = dataUrl;
        this.aliasesUrl = aliasesUrl;
        this.data = null;
        this.aliases = {};
    }

    /**
     * Load main JSON data
     * @returns {Promise<Object>} The loaded data
     */
    async loadData() {
        try {
            const response = await fetch(this.dataUrl);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            this.data = await response.json();
            console.log('✅ Data loaded successfully');
            return this.data;
        } catch (error) {
            console.error('❌ Failed to load data:', error);
            throw error;
        }
    }

    /**
     * Load aliases for multi-language search (optional)
     * @returns {Promise<Object>} The aliases object
     */
    async loadAliases() {
        if (!this.aliasesUrl) {
            console.log('ℹ️  No aliases URL provided, skipping');
            return {};
        }

        try {
            const response = await fetch(this.aliasesUrl);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            this.aliases = await response.json();
            console.log('✅ Loaded', Object.keys(this.aliases).length, 'search aliases');
            return this.aliases;
        } catch (error) {
            console.log('⚠️  Aliases not available:', error.message);
            this.aliases = {};
            return {};
        }
    }

    /**
     * Expand search term with aliases for multi-language search
     * Example: "gothenburg" -> ["gothenburg", "göteborg", "gøteborg"]
     *
     * @param {string} term - Search term to expand
     * @returns {string[]} Array of search terms including aliases
     */
    expandSearchWithAliases(term) {
        if (!this.aliases || Object.keys(this.aliases).length === 0) {
            return [term];
        }

        const lowerTerm = term.toLowerCase();
        const terms = [lowerTerm];

        // Add aliases if the term exists in the alias data
        if (this.aliases[lowerTerm]) {
            terms.push(...this.aliases[lowerTerm].map(alias => alias.toLowerCase()));
        }

        return terms;
    }

    /**
     * Highlight search terms in text (supports multiple terms and aliases)
     *
     * @param {string} text - Text to highlight in
     * @param {string} searchTerm - Search term (will be expanded with aliases)
     * @returns {string} HTML with highlighted terms
     */
    highlightText(text, searchTerm) {
        if (!searchTerm || !text) return text;

        // Get all search terms including aliases
        const searchTerms = this.expandSearchWithAliases(searchTerm);

        // Escape special regex characters and create pattern for all terms
        const escapedTerms = searchTerms.map(t =>
            t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        );
        const regex = new RegExp(`(${escapedTerms.join('|')})`, 'gi');

        return text.replace(regex, '<span class="highlight">$1</span>');
    }

    /**
     * Check if text matches search term (with alias support)
     *
     * @param {string} text - Text to search in
     * @param {string} searchTerm - Search term
     * @returns {boolean} True if text matches
     */
    matchesSearch(text, searchTerm) {
        if (!searchTerm) return true;
        if (!text) return false;

        const searchTerms = this.expandSearchWithAliases(searchTerm);
        const lowerText = text.toLowerCase();

        return searchTerms.some(term => lowerText.includes(term));
    }

    /**
     * Export content to a downloadable file
     *
     * @param {string} content - Content to export
     * @param {string} filename - Filename for download
     * @param {string} mimeType - MIME type (default: text/plain)
     */
    exportToFile(content, filename, mimeType = 'text/plain') {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    /**
     * Debounce a function call
     *
     * @param {Function} func - Function to debounce
     * @param {number} wait - Delay in milliseconds
     * @returns {Function} Debounced function
     */
    debounce(func, wait = 300) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Format date string to standard format
     *
     * @param {string} dateStr - Date string in various formats
     * @returns {string} Formatted date (YYYY-MM-DD)
     */
    formatDate(dateStr) {
        try {
            const date = new Date(dateStr);
            return date.toISOString().split('T')[0];
        } catch (e) {
            return dateStr;
        }
    }

    /**
     * Parse date from text (supports various formats)
     * Example: "Tuesday 2026-01-21" -> "2026-01-21"
     *
     * @param {string} text - Text containing date
     * @returns {string|null} Extracted date or null
     */
    extractDate(text) {
        const match = text.match(/\d{4}-\d{2}-\d{2}/);
        return match ? match[0] : null;
    }

    /**
     * Simple markdown to HTML converter (basic support)
     * Handles: headers, lists, bold, italic, links
     *
     * @param {string} markdown - Markdown text
     * @returns {string} HTML
     */
    markdownToHtml(markdown) {
        let html = '';
        const lines = markdown.split('\n');
        let inList = false;
        let currentParagraph = '';

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];

            // Headers
            if (line.startsWith('### ')) {
                if (currentParagraph) {
                    html += `<p>${currentParagraph}</p>\n`;
                    currentParagraph = '';
                }
                if (inList) {
                    html += '</ul>\n';
                    inList = false;
                }
                html += `<h3>${line.substring(4)}</h3>\n`;
            } else if (line.startsWith('## ')) {
                if (currentParagraph) {
                    html += `<p>${currentParagraph}</p>\n`;
                    currentParagraph = '';
                }
                if (inList) {
                    html += '</ul>\n';
                    inList = false;
                }
                html += `<h2>${line.substring(3)}</h2>\n`;
            } else if (line.startsWith('# ')) {
                if (currentParagraph) {
                    html += `<p>${currentParagraph}</p>\n`;
                    currentParagraph = '';
                }
                if (inList) {
                    html += '</ul>\n';
                    inList = false;
                }
                html += `<h1>${line.substring(2)}</h1>\n`;
            }
            // Lists
            else if (line.match(/^\s*[-*]\s/)) {
                if (currentParagraph) {
                    html += `<p>${currentParagraph}</p>\n`;
                    currentParagraph = '';
                }
                if (!inList) {
                    html += '<ul>\n';
                    inList = true;
                }
                html += `<li>${line.replace(/^\s*[-*]\s/, '')}</li>\n`;
            }
            // Empty line - paragraph break
            else if (line.trim() === '') {
                if (currentParagraph) {
                    html += `<p>${currentParagraph}</p>\n`;
                    currentParagraph = '';
                }
                if (inList) {
                    html += '</ul>\n';
                    inList = false;
                }
            }
            // Regular text
            else {
                if (inList) {
                    html += '</ul>\n';
                    inList = false;
                }
                if (currentParagraph) currentParagraph += ' ';
                currentParagraph += line;
            }
        }

        // Close any remaining paragraph or list
        if (currentParagraph) {
            html += `<p>${currentParagraph}</p>\n`;
        }
        if (inList) {
            html += '</ul>\n';
        }

        // Basic inline formatting
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2">$1</a>');

        return html;
    }
}

/**
 * Collapsible section manager
 * Handles expand/collapse behavior for hierarchical content
 */
class CollapsibleManager {
    /**
     * Initialize collapsible sections
     * @param {string} containerSelector - CSS selector for container
     */
    constructor(containerSelector) {
        this.containerSelector = containerSelector;
        this.collapsedState = new Map();
    }

    /**
     * Make all headers with class 'collapsible-header' clickable
     */
    init() {
        const container = document.querySelector(this.containerSelector);
        if (!container) {
            console.warn('Container not found:', this.containerSelector);
            return;
        }

        container.addEventListener('click', (e) => {
            const header = e.target.closest('.collapsible-header');
            if (header) {
                this.toggle(header);
            }
        });
    }

    /**
     * Toggle a collapsible section
     * @param {HTMLElement} headerElement - Header element to toggle
     */
    toggle(headerElement) {
        const content = headerElement.nextElementSibling;
        if (!content || !content.classList.contains('collapsible-content')) {
            return;
        }

        const isCollapsed = headerElement.classList.contains('collapsed');

        if (isCollapsed) {
            this.expand(headerElement);
        } else {
            this.collapse(headerElement);
        }
    }

    /**
     * Expand a section
     * @param {HTMLElement} headerElement - Header element
     */
    expand(headerElement) {
        headerElement.classList.remove('collapsed');
        const content = headerElement.nextElementSibling;
        if (content) {
            content.classList.remove('collapsed');
            content.style.maxHeight = content.scrollHeight + 'px';
        }
    }

    /**
     * Collapse a section
     * @param {HTMLElement} headerElement - Header element
     */
    collapse(headerElement) {
        headerElement.classList.add('collapsed');
        const content = headerElement.nextElementSibling;
        if (content) {
            content.classList.add('collapsed');
            content.style.maxHeight = '0';
        }
    }

    /**
     * Expand all sections
     */
    expandAll() {
        document.querySelectorAll(`${this.containerSelector} .collapsible-header`).forEach(header => {
            this.expand(header);
        });
    }

    /**
     * Collapse all sections
     */
    collapseAll() {
        document.querySelectorAll(`${this.containerSelector} .collapsible-header`).forEach(header => {
            this.collapse(header);
        });
    }
}

// Common CSS styles for collapsible sections and highlighting
const MD_VIEWER_COMMON_STYLES = `
.highlight {
    background-color: #ffeb3b;
    padding: 2px 4px;
    border-radius: 2px;
    font-weight: 500;
}

.collapsible-header {
    cursor: pointer;
    user-select: none;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    transition: color 0.2s;
}

.collapsible-header:hover {
    color: #3498db;
}

.collapse-icon {
    transition: transform 0.3s ease;
    font-size: 12px;
    display: inline-block;
}

.collapsible-header.collapsed .collapse-icon {
    transform: rotate(-90deg);
}

.collapsible-content {
    overflow: hidden;
    transition: max-height 0.3s ease-out;
}

.collapsible-content.collapsed {
    max-height: 0 !important;
}

.loading {
    text-align: center;
    padding: 40px;
    color: #666;
}

.error {
    background: #fee;
    border: 1px solid #fcc;
    border-radius: 6px;
    padding: 15px;
    margin: 20px 0;
    color: #c33;
}
`;

// Export for use in both module and non-module contexts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { MarkdownViewerBase, CollapsibleManager, MD_VIEWER_COMMON_STYLES };
}
