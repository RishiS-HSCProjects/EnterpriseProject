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

    const blockedIpForm = document.getElementById('blocked-ip-add-form');
    if (blockedIpForm) {
        blockedIpForm.addEventListener('submit', (event) => {
            const ipInput = blockedIpForm.querySelector('input[name="ip_address"]');
            const ip = (ipInput.value || '').trim();

            // Check only inside blocked IPs table
            const blockedIpTable = document.querySelector('#table-blocked-ips table tbody');
            if (blockedIpTable) {
                const rows = blockedIpTable.querySelectorAll('tr');
                for (const row of rows) {
                    const ipCell = row.querySelector('td:first-child');
                    if (ipCell && ipCell.textContent.trim() === ip) {
                        event.preventDefault();
                        alert('This IP is already blocked.');
                        ipInput.focus();
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
    applyBlockedFilters();
});

function updateBlockedAggregates() {
    const blockedTable = document.querySelector('#table-blocked-ips table tbody');
    if (!blockedTable) return;

    const rows = Array.from(blockedTable.querySelectorAll('tr'));
    const total = rows.length;

    const now = Date.now();
    const recentThreshold = now - (24 * 60 * 60 * 1000);

    let recent = 0;
    let withReason = 0;

    rows.forEach(r => {
        const cells = r.querySelectorAll('td');
        const blockedAtText = (cells[1]?.textContent || '').trim();
        const reasonText = (cells[2]?.textContent || '').trim();

        if (reasonText && reasonText !== '—') withReason += 1;

        if (blockedAtText && blockedAtText !== 'N/A') {
            try {
                const iso = blockedAtText.replace(' ', 'T') + ':00Z';
                const ts = Date.parse(iso);
                if (!isNaN(ts) && ts >= recentThreshold) recent += 1;
            } catch (e) {}
        }
    });

    const tTotal = document.getElementById('agg-block-total');
    if (tTotal) tTotal.textContent = `Total: ${total}`;
}

function applyBlockedFilters() {
    const query = (document.getElementById('blocked-search')?.value || '').trim().toLowerCase();
    const filter = (document.getElementById('blocked-filter')?.value || 'all');

    const blockedTable = document.querySelector('#table-blocked-ips table tbody');
    if (!blockedTable) return;

    const rows = blockedTable.querySelectorAll('tr');

    const now = Date.now();
    const recentThreshold = now - (24 * 60 * 60 * 1000);

    rows.forEach(r => {
        const cells = r.querySelectorAll('td');
        const ip = (cells[0]?.textContent || '').trim().toLowerCase();
        const blockedAtText = (cells[1]?.textContent || '').trim();
        const reason = (cells[2]?.textContent || '').trim().toLowerCase();

        let visible = true;

        if (query) {
            visible = ip.includes(query) || reason.includes(query);
        }

        if (visible && filter === 'recent') {
            if (!blockedAtText || blockedAtText === 'N/A') visible = false;
            else {
                const iso = blockedAtText.replace(' ', 'T') + ':00Z';
                const ts = Date.parse(iso);
                visible = !isNaN(ts) && ts >= recentThreshold;
            }
        }

        if (visible && filter === 'with-reason') visible = reason && reason !== '—';
        if (visible && filter === 'without-reason') visible = !reason || reason === '—';

        r.style.display = visible ? '' : 'none';
    });
    updateBlockedAggregates();
}

document.addEventListener('DOMContentLoaded', () => {
    const bsearch = document.getElementById('blocked-search');
    const bfilter = document.getElementById('blocked-filter');
    if (bsearch) bsearch.addEventListener('input', applyBlockedFilters);
    if (bfilter) bfilter.addEventListener('change', applyBlockedFilters);
    applyBlockedFilters();
});
