document.addEventListener('DOMContentLoaded', () => {
    const whitelistForm = document.getElementById('whitelist-add-form');
    if (whitelistForm) {
        whitelistForm.addEventListener('submit', (event) => {
            // Add submit listener for when the add button is clicked
            // Client-side verification done here for efficiency
            const usernameInput = whitelistForm.querySelector('input[name="username"]');
            const username = (usernameInput.value || '').trim().toLowerCase();

            // Check only inside whitelist table
            const whitelistTable = document.querySelector('#table-whitelist table tbody');
            if (whitelistTable) {
                const rows = whitelistTable.querySelectorAll('tr');
                for (const row of rows) {
                    const usernameCell = row.querySelector('td:first-child');
                    if (usernameCell && usernameCell.textContent.trim().toLowerCase() === username) {
                        event.preventDefault();
                        sendFlashMessage('This player is already whitelisted.', 'error');
                        usernameInput.focus();
                        return;
                    }
                }
            }

            startLoader(); // Start loading animation
            // Form automatically redirects to the whitelist add route
        });
    }
});

/**
 * Update aggregate stats (total, unregistered) based on table values.
 */
function updateAggregates() {
    const whitelistTable = document.querySelector('#table-whitelist table tbody');
    if (!whitelistTable) return;

    const rows = whitelistTable.querySelectorAll('tr');
    let total = 0, unregistered = 0;

    // Go through each row and compute registeration information client-side
    // Ignores filters for name/xuid and registration status
    rows.forEach(r => {
        const cells = r.querySelectorAll('td');
        if (cells.length < 3) return;

        total += 1;

        const registeredCell = cells[2];
        if (registeredCell && registeredCell.textContent.trim().toLowerCase() === 'no') {
            unregistered += 1;
        }
    });

    // Set vals
    const aggTotal = document.getElementById('agg-total');
    const aggUnregistered = document.getElementById('agg-unregistered');
    if (aggTotal) aggTotal.textContent = `Total: ${total}`;
    if (aggUnregistered) aggUnregistered.textContent = `Unregistered: ${unregistered}`;
}

function applyWhitelistFilters() {
    const query = (document.getElementById('whitelist-search')?.value || '').trim().toLowerCase();
    const filter = (document.getElementById('whitelist-filter')?.value || 'all');

    const whitelistTable = document.querySelector('#table-whitelist table tbody');
    if (!whitelistTable) return;

    const rows = whitelistTable.querySelectorAll('tr');

    rows.forEach(r => {
        const cells = r.querySelectorAll('td');
        const username = (cells[0]?.textContent || '').trim().toLowerCase();
        const xuid = (cells[1]?.textContent || '').trim().toLowerCase();
        const registered = (cells[2]?.textContent || '').trim().toLowerCase();

        let visible = true;

        if (query) {
            visible = username.includes(query) || xuid.includes(query);
        }

        if (visible && filter === 'registered') visible = registered === 'yes';
        if (visible && filter === 'unregistered') visible = registered !== 'yes';

        r.style.display = visible ? '' : 'none';
    });

    updateAggregates(); // Update aggregates on filter application
}

document.addEventListener('DOMContentLoaded', () => {
    const search = document.getElementById('whitelist-search');
    const filter = document.getElementById('whitelist-filter');

    if (search) search.addEventListener('input', applyWhitelistFilters);
    if (filter) filter.addEventListener('change', applyWhitelistFilters);

    applyWhitelistFilters();
});

/**
 * Client-side table updating on role update event
 */
function updateRole(entryId, selectElement) {
    const previousRole = selectElement.dataset.previous;
    const newRole = selectElement.value;

    // Disable to avoid accidental repeat requests
    selectElement.disabled = true;
    startLoader();

    // Ask the server to change the role
    fetch(`/admin/update_role/${entryId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector(
                'input[name="csrf_token"]'
            ).value
        },
        body: JSON.stringify({
            role: newRole
        })
    })
    .then(async response => {
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.message ||
                'Failed to update role.'
            );
        }

        return data;
    })
    .then(data => {
        selectElement.dataset.previous = newRole;

        sendFlashMessage(
            data.message ||
            'User role updated successfully.',
            'success'
        );
    })
    .catch(error => {
        selectElement.value = previousRole;

        sendFlashMessage(
            error.message ||
            'An error occurred while updating user role.',
            'error'
        );
    })
    .finally(() => {
        selectElement.disabled = false;
        stopLoader();
    });
}
