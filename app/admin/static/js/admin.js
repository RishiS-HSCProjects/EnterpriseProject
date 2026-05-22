document.addEventListener('DOMContentLoaded', () => {
    const whitelistForm = document.getElementById('whitelist-add-form');
    if (whitelistForm) {
        whitelistForm.addEventListener('submit', (event) => {
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

            startLoader();
        });
    }
});

function updateAggregates() {
    const whitelistTable = document.querySelector('#table-whitelist table tbody');
    if (!whitelistTable) return;

    const rows = whitelistTable.querySelectorAll('tr');
    let total = 0, unregistered = 0;

    rows.forEach(r => {
        const cells = r.querySelectorAll('td');
        if (cells.length < 3) return;

        total += 1;

        const registeredCell = cells[2];
        if (registeredCell && registeredCell.textContent.trim().toLowerCase() === 'no') {
            unregistered += 1;
        }
    });

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

    updateAggregates();
}

document.addEventListener('DOMContentLoaded', () => {
    const search = document.getElementById('whitelist-search');
    const filter = document.getElementById('whitelist-filter');

    if (search) search.addEventListener('input', applyWhitelistFilters);
    if (filter) filter.addEventListener('change', applyWhitelistFilters);

    applyWhitelistFilters();
});

function updateRole(entryId, selectElement) {
    const previousRole = selectElement.dataset.previous;
    const newRole = selectElement.value;

    selectElement.disabled = true;
    startLoader();

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
