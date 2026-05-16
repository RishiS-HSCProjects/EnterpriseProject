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
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                    },
                    body: new URLSearchParams(formData),
                });

                let data = {};
                try {
                    data = await response.json();
                } catch (e) {
                    // ignore
                }

                if (typeof sendFlashMessage === 'function') sendFlashMessage(data.message || 'Caching completed.', data.success ? 'success' : 'error');

                if (data.success) {
                    setTimeout(() => window.location.reload(), 500);
                }
            } catch (error) {
                if (typeof sendFlashMessage === 'function') sendFlashMessage('Unexpected error caching tournament stats.', 'error');
            } finally {
                if (typeof endLoader === 'function') endLoader();
                if (button) {
                    button.disabled = false;
                    button.textContent = originalText;
                }
            }
        });
    }

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
