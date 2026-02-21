/**
 * Request Actions Manager
 * Handles interactions for the detailed request view (Notes, Email, Status, Assignments)
 * Designed to work with dynamically loaded content in tabs.
 */

const RequestActions = {
    // Store recipient lists for each request key
    recipientsMap: new Map(),

    /**
     * Open a modal scoped to a specific request
     * @param {string} modalId - The ID of the modal to open
     * @param {string} requestKey - The key of the request (e.g. ACCT-1234)
     */
    openModal(modalId) {
        // Construct the specific ID for this request's modal
        const el = document.getElementById(modalId);
        if (el) {
            el.classList.add('active');
        } else {
            console.error(`Modal with ID ${modalId} not found`);
        }
    },

    /**
     * Close a modal
     * @param {string} modalId - The ID of the modal to close
     */
    closeModal(modalId) {
        const el = document.getElementById(modalId);
        if (el) {
            el.classList.remove('active');
        }
    },

    /**
     * Submit an internal note
     * @param {string} requestKey 
     */
    async submitNote(requestKey) {
        const inputId = `note-body-${requestKey}`;
        const input = document.getElementById(inputId);
        const body = input ? input.value : '';

        if (!body) {
            alert('Note cannot be empty');
            return;
        }

        await this.apiCall(`/other/api/request/${requestKey}/comment`, { body }, requestKey);
        this.closeModal(`note-modal-${requestKey}`);
    },

    /**
     * Update request status
     * @param {string} requestKey 
     * @param {string} status 
     */
    async updateStatus(requestKey, status) {
        const success = await this.apiCall(`/other/api/request/${requestKey}/status`, { status }, requestKey);
        if (success) showToast(`Status updated to "${status}"`);
    },

    /**
     * Assign request to a user
     * @param {string} requestKey 
     * @param {string} email 
     */
    async assignRequest(requestKey, email) {
        await this.apiCall(`/other/api/request/${requestKey}/assign`, { assignee_email: email }, requestKey);
    },

    /**
     * Initialize recipients list for a request if not exists
     * @param {string} requestKey 
     */
    initRecipients(requestKey) {
        if (!this.recipientsMap.has(requestKey)) {
            this.recipientsMap.set(requestKey, []);
        }
    },

    /**
     * Add a recipient to the email list
     * @param {string} requestKey 
     * @param {string} email 
     */
    addRecipient(requestKey, email) {
        this.initRecipients(requestKey);
        const list = this.recipientsMap.get(requestKey);

        if (email && !list.includes(email)) {
            list.push(email);
            this.renderRecipients(requestKey);

            // Clear input if it exists
            const input = document.getElementById(`new-recipient-${requestKey}`);
            if (input) input.value = '';
        }
    },

    /**
     * Add recipient from manual input
     * @param {string} requestKey 
     */
    addRecipientManual(requestKey) {
        const input = document.getElementById(`new-recipient-${requestKey}`);
        if (input) {
            this.addRecipient(requestKey, input.value);
        }
    },

    /**
     * Remove a recipient
     * @param {string} requestKey 
     * @param {string} email 
     */
    removeRecipient(requestKey, email) {
        if (!this.recipientsMap.has(requestKey)) return;

        const list = this.recipientsMap.get(requestKey);
        const index = list.indexOf(email);
        if (index > -1) {
            list.splice(index, 1);
            this.renderRecipients(requestKey);
        }
    },

    /**
     * Render the list of recipients
     * @param {string} requestKey 
     */
    renderRecipients(requestKey) {
        const list = this.recipientsMap.get(requestKey) || [];
        const container = document.getElementById(`recipient-list-${requestKey}`);

        if (container) {
            container.innerHTML = list.map(email => `
                <div class="recipient-pill">
                    ${email} 
                    <i class="ph ph-x" style="cursor:pointer" 
                       onclick="RequestActions.removeRecipient('${requestKey}', '${email}')"></i>
                </div>
            `).join('');
        }
    },

    /**
     * Handle Enter key in recipient input
     */
    handleRecipientEnter(event, requestKey) {
        if (event.key === 'Enter') {
            event.preventDefault();
            this.addRecipientManual(requestKey);
        }
    },

    /**
     * Send the composed email
     * @param {string} requestKey 
     */
    async sendEmail(requestKey) {
        const subject = document.getElementById(`email-subject-${requestKey}`).value;
        const body = document.getElementById(`email-body-${requestKey}`).value;
        const recipients = this.recipientsMap.get(requestKey) || [];

        if (recipients.length === 0) {
            alert('Add at least one recipient');
            return;
        }
        if (!body) {
            alert('Message body empty');
            return;
        }

        const btn = document.getElementById(`send-email-btn-${requestKey}`);
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="ph-bold ph-arrows-clockwise animate-spin" style="display:inline-block"></i> Sending...';
        }

        const success = await this.apiCall(`/other/api/request/${requestKey}/send-email`, {
            subject,
            body,
            to_list: recipients
        }, requestKey);

        if (!success && btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="ph-bold ph-paper-plane-right"></i> Send Email';
        }
    },

    /**
     * Generic API call helper
     */
    async apiCall(url, data, requestKey) {
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (res.ok) {
                if (window.TabManager) {
                    window.TabManager.reloadTab(requestKey);
                } else {
                    location.reload();
                }
                return true;
            } else {
                const err = await res.json();
                alert('Action failed: ' + (err.error || 'Unknown error'));
                return false;
            }
        } catch (e) {
            alert('Error: ' + e.message);
            return false;
        }
    }
};

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.style.cssText = [
        'position:fixed', 'bottom:1.5rem', 'right:1.5rem', 'z-index:9999',
        'display:flex', 'align-items:center', 'gap:0.6rem',
        'padding:0.7rem 1.1rem', 'border-radius:0.75rem',
        'box-shadow:0 8px 24px rgba(0,0,0,0.18)',
        'font-size:0.875rem', 'font-weight:600', 'color:#fff',
        'transition:opacity 0.3s,transform 0.3s',
        'opacity:0', 'transform:translateY(0.5rem)'
    ].join(';');
    toast.style.backgroundColor = type === 'success' ? '#16a34a' : '#dc2626';
    const icon = type === 'success' ? 'ph-check-circle' : 'ph-x-circle';
    toast.innerHTML = `<i class="ph-bold ${icon}" style="font-size:1.1rem"></i>${message}`;
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    });

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(0.5rem)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/**
 * Toggle the collapsible activity filter row
 */
function toggleActivityFilters() {
    const filters = document.getElementById('activity-filters');
    const btn = document.getElementById('filter-toggle-btn');
    if (!filters) return;

    const isOpen = filters.style.maxHeight !== '0px';

    if (isOpen) {
        filters.style.maxHeight = '0px';
        filters.style.opacity = '0';
        btn.classList.remove('bg-agilent-light', 'text-agilent-blue', 'border-agilent-blue/30');
        btn.classList.add('bg-white', 'text-surface-500');
    } else {
        filters.style.maxHeight = '50px';
        filters.style.opacity = '1';
        btn.classList.add('bg-agilent-light', 'text-agilent-blue', 'border-agilent-blue/30');
        btn.classList.remove('bg-white', 'text-surface-500');
    }
}

/**
 * Toggle between card view and compact audit log view
 */
function toggleHistoryView() {
    const cardView = document.getElementById('card-view');
    const historyView = document.getElementById('history-view');
    const btn = document.getElementById('history-toggle-btn');
    if (!cardView || !historyView) return;

    const showingHistory = historyView.style.display !== 'none';

    if (showingHistory) {
        // Switch back to card view
        cardView.style.display = '';
        historyView.style.display = 'none';
        btn.classList.remove('bg-agilent-light', 'text-agilent-blue', 'border-agilent-blue/30');
        btn.classList.add('bg-white', 'text-surface-500');
    } else {
        // Switch to audit log view
        cardView.style.display = 'none';
        historyView.style.display = '';
        btn.classList.add('bg-agilent-light', 'text-agilent-blue', 'border-agilent-blue/30');
        btn.classList.remove('bg-white', 'text-surface-500');
    }
}

/**
 * Switch between activity tabs and filter messages
 * @param {string} tabType - 'all', 'system', 'agent', or 'customer'
 */
function switchActivityTab(tabType) {
    // Update tab button styles
    const tabs = document.querySelectorAll('.activity-tab');
    tabs.forEach(tab => {
        const isActive = tab.id === `tab-${tabType}`;

        if (isActive) {
            tab.classList.remove('text-surface-600', 'bg-surface-100', 'hover:bg-surface-200');
            tab.classList.add('bg-agilent-blue', 'text-white');
            tab.setAttribute('aria-selected', 'true');
        } else {
            tab.classList.remove('bg-agilent-blue', 'text-white');
            tab.classList.add('text-surface-600', 'bg-surface-100', 'hover:bg-surface-200');
            tab.setAttribute('aria-selected', 'false');
        }
    });

    // Update filter icon style
    const filterBtn = document.getElementById('filter-toggle-btn');
    if (filterBtn) {
        if (tabType === 'all') {
            filterBtn.classList.remove('bg-agilent-light', 'text-agilent-blue', 'border-agilent-blue/30');
            filterBtn.classList.add('bg-white', 'text-surface-500');
        } else {
            filterBtn.classList.add('bg-agilent-light', 'text-agilent-blue', 'border-agilent-blue/30');
            filterBtn.classList.remove('bg-white', 'text-surface-500');
        }
    }

    // Filter activity messages
    const messages = document.querySelectorAll('.activity-message');
    messages.forEach(message => {
        const messageType = message.getAttribute('data-activity-type');

        if (tabType === 'all') {
            message.style.display = '';
        } else {
            message.style.display = messageType === tabType ? '' : 'none';
        }
    });
}
