document.addEventListener('DOMContentLoaded', () => {
    // Show/hide round leaderboard sections based on selector
    function showRoundLeaderboard() {
        const select = document.getElementById('round-selector');
        const selectedRound = select ? select.value : '';
        document.querySelectorAll('[data-round-leaderboard]').forEach((panel) => {
            panel.hidden = panel.dataset.roundLeaderboard !== selectedRound;
        });
    }

    // Expose archived disqualified players (if present) for client-side features
    try {
        const disqEl = document.getElementById('disqualified-players');
        if (disqEl && disqEl.dataset && disqEl.dataset.disqualified) {
            try {
                window.__allDisqualifiedPlayers = JSON.parse(disqEl.dataset.disqualified);
            } catch (e) {
                console.error('Failed to parse disqualified players JSON:', e);
                window.__allDisqualifiedPlayers = {};
            }
        } else {
            window.__allDisqualifiedPlayers = {};
        }
    } catch (e) {
        window.__allDisqualifiedPlayers = {};
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

    function bindLeaderboardPlayers() {
        document.querySelectorAll('li[data-player]').forEach((item) => {
            const playerName = item.dataset.player || '';
            if (!playerName) return;

            item.setAttribute('role', 'button');
            item.setAttribute('tabindex', '0');
            item.setAttribute('aria-label', `Open ${playerName} on the Portal`);

            item.addEventListener('click', () => {
                window.openPortal(playerName);
            });

            item.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    window.openPortal(playerName);
                }
            });
        });
    }

    const epochStartTime = document.getElementById("start-info");
    if (epochStartTime) {
        epochStartTime.addEventListener('click', async () => {
            if (copyClipboard(epochStartTime.dataset.value)) {
                sendFlashMessage('Tournament start time copied to clipboard!', 'success');
            } else {
                sendFlashMessage('Something went wrong when trying to copy start time to clipboard.', 'error');
            }
        });
    }

    const epochEndTime = document.getElementById("end-info");
    if (epochEndTime) {
        epochEndTime.addEventListener('click', async () => {
            if (copyClipboard(epochEndTime.dataset.value)) {
                sendFlashMessage('Tournament end time copied to clipboard!', 'success');
            } else {
                sendFlashMessage('Something went wrong when trying to copy end time to clipboard.', 'error');
            }
        });
    }

    const epochDurSec = document.getElementById('epoch-duration');
    if (epochDurSec) {
        epochDurSec.addEventListener('click', async () => {
            if (copyClipboard(epochDurSec.dataset.value)) {
                sendFlashMessage('Tournament duration copied to clipboard!', 'success');
            } else {
                sendFlashMessage('Something went wrong when trying to copy duration to clipboard.', 'error');
            }
        });
    }

    const rewardPackageState = {
        packages: [],
        scope: 'round',
    };

    function bindRewardPackageControls() {
        const scopeSelect = document.getElementById('reward-package-scope');

        if (scopeSelect) {
            rewardPackageState.scope = scopeSelect.value || rewardPackageState.scope;
            scopeSelect.addEventListener('change', () => {
                rewardPackageState.scope = scopeSelect.value;
                renderRewardPackages(rewardPackageState.packages);
            });
        }
    }

    function renderSelectedRewardPackage(packageItem) {
        const list = document.getElementById('reward-packages-list');
        if (!list) return;

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
        row.appendChild(copyButton);

        const entries = Array.isArray(packageItem.entries) ? packageItem.entries : [];
        if (entries.length) {
            const entryList = document.createElement('ul');
            entryList.className = 'reward-package-entries';

            entries.forEach((entry) => {
                const entryItem = document.createElement('li');
                const roundLabel = entry && entry.round !== null && entry.round !== undefined
                    ? `Round ${entry.round}`
                    : (packageItem.reward_scope === 'global' ? 'Overall' : 'Winner');
                entryItem.textContent = `${roundLabel}: ${entry.player || 'Unknown player'}`;
                entryList.appendChild(entryItem);
            });

            item.appendChild(entryList);
        }

        if (Array.isArray(packageItem.unresolved_players) && packageItem.unresolved_players.length) {
            const note = document.createElement('div');
            note.className = 'reward-package-note';
            note.textContent = 'Skipped: ' + packageItem.unresolved_players.join(', ');
            item.appendChild(note);
        }

        copyButton.addEventListener('click', async () => {
            const copyText = copyButton.dataset.copyText || '';
            if (!copyText) return;

            if (copyClipboard(copyText)) {
                const originalText = copyButton.textContent;
                copyButton.textContent = 'Copied!';
                sendFlashMessage('Copied to clipboard.', 'success');
                window.setTimeout(() => {
                    copyButton.textContent = originalText;
                }, 1200);
            } else {
                sendFlashMessage('Failed to copy. Please try manually.', 'error');
            }
        });

        list.appendChild(item);
    }

    function renderRewardPackages(packages) {
        rewardPackageState.packages = Array.isArray(packages) ? packages : [];
        bindRewardPackageControls();

        const list = document.getElementById('reward-packages-list');
        const status = document.getElementById('reward-packages-status');
        if (list) list.innerHTML = '';

        if (!rewardPackageState.packages.length) {
            if (status) status.textContent = 'No packages available yet.';
            return;
        }

        const visiblePackages = rewardPackageState.packages.filter((packageItem) => {
            return (packageItem.reward_scope || '') === rewardPackageState.scope;
        });

        if (status) {
            status.textContent = visiblePackages.length
                ? `${visiblePackages.length} package${visiblePackages.length === 1 ? '' : 's'} available.`
                : 'No packages available for this selection.';
        }

        visiblePackages.forEach((packageItem) => {
            renderSelectedRewardPackage(packageItem);
        });
    }

    async function loadRewardPackages() {
        const panel = document.getElementById('reward-packages-panel');
        if (!panel) return;

        const status = document.getElementById('reward-packages-status');
        const packageUrl = panel.dataset.packageUrl;
        if (!packageUrl) {
            if (status) status.textContent = 'Package endpoint unavailable.';
            return;
        }

        try {
            const response = await fetch(packageUrl);
            const data = await response.json();
            if (data.success) {
                renderRewardPackages(data.packages);
            } else if (status) {
                status.textContent = 'Unable to load packages';
                sendFlashMessage(data.message || 'Unable to load packages', 'error');
            }
        } catch (error) {
            console.error(`Error loading reward packages: ${error.message}`, error);
        }
    }

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
                    window.location.reload();
                } else {
                    console.log(data);
                }
            } catch (error) {
                console.error('Unexpected error caching tournament stats:', error);
                sendFlashMessage('Unexpected error caching tournament stats.', 'error');
            } finally {
                if (typeof stopLoader === 'function') stopLoader();
                if (button) {
                    button.disabled = false;
                    button.textContent = originalText;
                }
            }
        });
    }

    loadRewardPackages();
    bindLeaderboardPlayers();

    const validateRecipientsForm = document.getElementById('validate-recipients-form');
    if (validateRecipientsForm) {
        validateRecipientsForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const button = form.querySelector('button[type="submit"]');
            const originalText = button ? button.textContent : 'Validate Recipients';

            try {
                if (button) {
                    button.disabled = true;
                    button.textContent = 'Validating...';
                }
                if (typeof startLoader === 'function') startLoader();

                const formData = new FormData(form);
                const response = await fetch(form.dataset.action, {
                    method: 'POST',
                    body: formData,
                });

                let data = {};
                try {
                    data = await response.json();
                } catch (e) {
                    console.error('Failed to parse JSON response:', e);
                    sendFlashMessage('Server error during recipient validation.', 'error');
                    return;
                }

                if (data.success) {
                    window.location.reload();
                } else {
                    console.log(data);
                    sendFlashMessage(data.message || 'Failed to validate recipients.', 'error');
                }
            } catch (error) {
                console.error('Unexpected error validating recipients:', error);
                sendFlashMessage('Unexpected error validating recipients.', 'error');
            } finally {
                if (typeof stopLoader === 'function') stopLoader();
                if (button) {
                    button.disabled = false;
                    button.textContent = originalText;
                }
            }
        });
    }

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
                    if (pw) pw.focus();
                    return false;
                }
                if (!confirm('This will permanently delete the tournament and its data. Are you sure?')) {
                    ev.preventDefault();
                    return false;
                }
                if (typeof startLoader === 'function') startLoader();
                return true;
            });
        }
    }

    try {
        const isAuth = window.__isAuthenticated === true || window.__isAuthenticated === 'true';
        if (!isAuth) {
            const formElements = document.querySelectorAll('#tournament-edit-form input, #tournament-edit-form textarea');
            formElements.forEach((element) => {
                element.disabled = true;
            });
        }
    } catch (e) {
        // ignore
    }

    try {
        if (!window.TimeUtils) throw new Error('TimeUtils not loaded');

        const startUnixInput = document.getElementById('start-unix-input');
        const endUnixInput = document.getElementById('end-unix-input');
        const startInfo = document.getElementById('start-info');
        const endInfo = document.getElementById('end-info');
        const startPicker = document.getElementById('start-date-picker');
        const endPicker = document.getElementById('end-date-picker');

        const updatePreviewFromUnix = (inputEl, infoEl) => {
            if (!inputEl || !infoEl) return;
            const value = parseInt(inputEl.value, 10);
            if (Number.isNaN(value)) {
                infoEl.textContent = '';
                infoEl.title = '';
                infoEl.style.display = 'none';
            } else {
                const { display, utc, relative } = window.TimeUtils.formatDateLocal(value);
                const isoUtc = new Date(value * 1000).toISOString(); // Convert epoch to ms and then to ISO string
                infoEl.innerHTML = `<strong>${display}</strong> | Epoch: <code>${value}</code> | ISO8601: <code>${isoUtc}</code>`;
                infoEl.title = `GMT: ${utc} | ${relative}`;
                infoEl.style.display = 'block';
                infoEl.dataset.value = isoUtc;
            }
        };

        if (startUnixInput && startInfo) {
            if (startPicker && startUnixInput.value) {
                startPicker.value = window.TimeUtils.epochToDateInput(parseInt(startUnixInput.value, 10));
            }
            updatePreviewFromUnix(startUnixInput, startInfo);
            startUnixInput.addEventListener('input', () => updatePreviewFromUnix(startUnixInput, startInfo));
        }

        if (endUnixInput && endInfo) {
            if (endPicker && endUnixInput.value) {
                endPicker.value = window.TimeUtils.epochToDateInput(parseInt(endUnixInput.value, 10));
            }
            updatePreviewFromUnix(endUnixInput, endInfo);
            endUnixInput.addEventListener('input', () => updatePreviewFromUnix(endUnixInput, endInfo));
        }

        if (startPicker && startUnixInput) {
            startPicker.addEventListener('change', () => {
                const epoch = window.TimeUtils.dateToEpoch(startPicker.value);
                if (epoch !== null) {
                    startUnixInput.value = epoch;
                    startUnixInput.dispatchEvent(new Event('input'));
                }
            });
        }

        if (endPicker && endUnixInput) {
            endPicker.addEventListener('change', () => {
                const epoch = window.TimeUtils.dateToEpoch(endPicker.value);
                if (epoch !== null) {
                    endUnixInput.value = epoch;
                    endUnixInput.dispatchEvent(new Event('input'));
                }
            });
        }

        const roundCountInput = document.getElementById('round-count-input');
        const epochDurationEl = document.getElementById('epoch-duration');

        const updateRoundDuration = () => {
            if (!epochDurationEl) return;
            const startValue = startUnixInput ? parseInt(startUnixInput.value, 10) : NaN;
            const endValue = endUnixInput ? parseInt(endUnixInput.value, 10) : NaN;
            const roundCountValue = roundCountInput ? parseInt(roundCountInput.value, 10) : NaN;

            if (Number.isNaN(startValue) || Number.isNaN(endValue) || Number.isNaN(roundCountValue) || roundCountValue <= 0 || endValue <= startValue) {
                const serverValue = parseInt(epochDurationEl.dataset.value, 10);
                if (!Number.isNaN(serverValue)) {
                    epochDurationEl.textContent = `Round Duration: ${serverValue} seconds`;
                    epochDurationEl.dataset.value = serverValue;
                }
                return;
            }

            const totalDuration = endValue - startValue;
            const roundDuration = totalDuration / roundCountValue;
            const formatted = window.TimeUtils.formatDuration(roundDuration);

            if (formatted) {
                epochDurationEl.textContent = `Round Duration: ${formatted.display} (${formatted.seconds} seconds)`;
                epochDurationEl.dataset.value = formatted.seconds;
            } else {
                epochDurationEl.textContent = '';
            }
        };

        if (startUnixInput) startUnixInput.addEventListener('input', updateRoundDuration);
        if (endUnixInput) endUnixInput.addEventListener('input', updateRoundDuration);
        if (roundCountInput) roundCountInput.addEventListener('input', updateRoundDuration);

        updateRoundDuration();
    } catch (e) {
        // TimeUtils not available or error - fail silently
    }
});
