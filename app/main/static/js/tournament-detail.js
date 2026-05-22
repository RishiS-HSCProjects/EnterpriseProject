document.addEventListener('DOMContentLoaded', () => {
    // Show/hide round leaderboard sections based on selector
    function showRoundLeaderboard() {
        const select = document.getElementById('round-selector');
        const selectedRound = select ? select.value : '';
        document.querySelectorAll('[data-round-leaderboard]').forEach((panel) => {
            panel.hidden = panel.dataset.roundLeaderboard !== selectedRound;
        });
    }

    showRoundLeaderboard();
    const roundSelector = document.getElementById('round-selector');
    if (roundSelector) {
        roundSelector.addEventListener('change', showRoundLeaderboard);
    }

    // Open a player portal in a new tab
    window.openPortal = function (playerName) {
        const url = 'https://ngmc.co/p/' + encodeURIComponent(playerName);
        window.open(url, '_blank');
    };

    function renderRewardPackages(packages) {
        const list = document.getElementById('reward-packages-list');
        if (!list) return;

        const status = document.getElementById('reward-packages-status');

        if (!Array.isArray(packages) || !packages.length) {
            if (status) status.textContent = 'No packages available yet.';
            return;
        }

        packages.forEach((packageItem) => {
            const item = document.createElement('li');
            item.className = 'reward-package-card';

            const title = document.createElement('div');
            title.className = 'reward-package-title';
            title.textContent = packageItem.reward_label || packageItem.reward_type || 'Package';
            item.appendChild(title);

            const row = document.createElement('div');
            row.className = 'reward-package-row';
            item.appendChild(row);

            const meta = document.createElement('div');
            meta.className = 'reward-package-meta';
            meta.textContent = packageItem.display_text || 'No recipients';
            row.appendChild(meta);

            const copyButton = document.createElement('button');
            copyButton.type = 'button';
            copyButton.className = 'reward-package-copy';
            copyButton.textContent = 'Copy';
            copyButton.dataset.copyText = packageItem.copy_text || '';

            if (Array.isArray(packageItem.unresolved_players) && packageItem.unresolved_players.length) {
                const note = document.createElement('div');
                note.className = 'reward-package-note';
                note.textContent = 'Skipped: ' + packageItem.unresolved_players.join(', ');
                item.appendChild(note);
            } else {
                row.appendChild(copyButton);
            }

            list.appendChild(item);
        });

        list.querySelectorAll('.reward-package-copy').forEach((button) => {
            button.addEventListener('click', async () => {
                const copyText = button.dataset.copyText || '';
                if (!copyText) return;

                try {
                    await navigator.clipboard.writeText(copyText);
                    const originalText = button.textContent;
                    button.textContent = 'Copied!';
                    sendFlashMessage('Copied to clipboard.', 'success');
                } catch (error) {
                    sendFlashMessage('Failed to copy. Please try manually.', 'error');
                    console.error('Clipboard copy failed: ', error);
                }
            });
        });
    }

    async function loadRewardPackages(type = null) { // type='round'; type='global';
        const panel = document.getElementById('reward-packages-panel');
        if (!panel) return;

        const status = document.getElementById('reward-packages-status');
        const packageUrl = panel.dataset.packageUrl;
        if (!packageUrl) {
            if (status) status.textContent = 'Package endpoint unavailable.';
            return;
        }

        try {
            const response = await fetch(`${packageUrl}?type=${encodeURIComponent(type)}`);

            const data = await response.json();
            if (data.success) {
                renderRewardPackages(data.packages);
            } else if (status) {
                status.textContent = 'Unable to load packages';
                sendFlashMessage(data.message || 'Unable to load packages', 'error')
            }
        } catch (error) {
            console.error(`Error ${status || ''}`) 
        }
    }

    // Cache tournament stats form handler (AJAX)
    const cacheForm = document.getElementById('cache-stats-form');
    if (cacheForm) {
        cacheForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const button = form.querySelector('button[type="submit"]');
            const originalText = button ? button.textContent : 'Cache Stats';

            try {
                if (button) {
                    button.disabled = true;
                    button.textContent = 'Caching...';
                }
                if (typeof startLoader === 'function') startLoader();

                const formData = new FormData(form);
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                });

                let data = {};
                try {
                    data = await response.json();
                } catch (e) { 
                    console.error('Failed to parse JSON response:', e);
                    sendFlashMessage('Server error during caching.', 'error');
                    return;
                }

                if (data.success) {
                    window.location.reload()
                }
            } catch (error) {
                console.error('Unexpected error caching tournament stats:', error);
                sendFlashMessage('Unexpected error caching tournament stats.', 'error');
            } finally {
                stopLoader();
                if (button) {
                    button.disabled = false;
                    button.textContent = originalText;
                }
            }
        });
    }

    loadRewardPackages('round');
    loadRewardPackages('global');

    // Delete modal wiring: use centralized setupFormModal if available
    const deleteModal = document.getElementById('delete-modal');
    if (deleteModal) {
        try {
            if (typeof setupFormModal === 'function') {
                setupFormModal({
                    modalId: 'delete-modal',
                    openButtonSelector: '.delete-tourney-btn',
                    formId: 'delete-form',
                    focusSelector: '#delete-password',
                    autoOpen: false,
                });
            }
        } catch (e) {
            // ignore
        }

        const deleteForm = document.getElementById('delete-form');
        if (deleteForm) {
            deleteForm.addEventListener('submit', (ev) => {
                const pw = document.getElementById('delete-password');
                if (!pw || !pw.value.trim()) {
                    ev.preventDefault();
                    alert('Please enter your password to confirm deletion.');
                    pw && pw.focus();
                    return false;
                }
                if (!confirm('This will permanently delete the tournament and its data. Are you sure?')) {
                    ev.preventDefault();
                    return false;
                }
                if (typeof startLoader === 'function') startLoader();
                // allow submit to proceed
                return true;
            });
        }
    }

    // If server marked user as unauthenticated, disable form inputs
    try {
        const isAuth = window.__isAuthenticated === true || window.__isAuthenticated === 'true';
        if (!isAuth) {
            const formElements = document.querySelectorAll('#tournament-edit-form input, #tournament-edit-form textarea');
            formElements.forEach((e) => e.disabled = true);
        }
    } catch (e) {
        // ignore
    }
});
