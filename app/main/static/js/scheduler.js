document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('add-modal');
    if (!modal) return;

    const shouldOpenModal = modal.dataset.showAddModal === 'true';

    // Wire modal using centralized helper
    setupFormModal({
        modalId: 'add-modal',
        openButtonSelector: '.create-tournament-btn',
        formId: 'add-tournament-form',
        focusSelector: 'input[type="text"]',
        autoOpen: shouldOpenModal
    });

    // Convert any displayed datetimes (with class 'dt' and data-unix) into local timezone strings
    function relativeTime(dt) {
        const diffSec = Math.floor((Date.now() - dt.getTime()) / 1000);
        const future = diffSec < 0;
        const abs = Math.abs(diffSec);
        if (abs < 5) return future ? `in ${abs} seconds` : 'just now';
        if (abs < 60) return future ? `in ${abs} seconds` : `${abs} seconds ago`;
        if (abs < 3600) {
            const m = Math.floor(abs / 60);
            return future ? `in ${m} minute${m !== 1 ? 's' : ''}` : `${m} minute${m !== 1 ? 's' : ''} ago`;
        }
        if (abs < 86400) {
            const h = Math.floor(abs / 3600);
            return future ? `in ${h} hour${h !== 1 ? 's' : ''}` : `${h} hour${h !== 1 ? 's' : ''} ago`;
        }
        if (abs < 2592000) {
            const d = Math.floor(abs / 86400);
            return future ? `in ${d} day${d !== 1 ? 's' : ''}` : `${d} day${d !== 1 ? 's' : ''} ago`;
        }
        const months = Math.floor(abs / 2592000);
        if (months < 12) return future ? `in ${months} month${months !== 1 ? 's' : ''}` : `${months} month${months !== 1 ? 's' : ''} ago`;
        const years = Math.floor(months / 12);
        return future ? `in ${years} year${years !== 1 ? 's' : ''}` : `${years} year${years !== 1 ? 's' : ''} ago`;
    }

    function convertDisplayedDatetimes() {
        document.querySelectorAll('.dt[data-unix]').forEach(el => {
            const unix = parseInt(el.dataset.unix, 10);
            if (isNaN(unix)) return;
            const dt = new Date(unix * 1000);
            try {
                el.textContent = dt.toLocaleString(undefined, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
            } catch (e) {
                el.textContent = dt.toLocaleString();
            }
            // Hover shows GMT and relative time
            el.title = 'GMT: ' + dt.toUTCString() + ' - ' + relativeTime(dt);
                    // Local display: e.g. "26 April 14:30"
                    const day = String(dt.getDate()).padStart(2, '0');
                    const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
                    const month = monthNames[dt.getMonth()];
                    const hour = String(dt.getHours()).padStart(2, '0');
                    const minute = String(dt.getMinutes()).padStart(2, '0');
                    el.textContent = `${day} ${month} ${hour}:${minute}`;
            });
    }

    function unixPreview(inputEl, previewEl) {
        if (!inputEl || !previewEl) return;
        function update() {
            const v = parseInt(inputEl.value, 10);
            if (isNaN(v)) {
                previewEl.textContent = '';
                previewEl.title = '';
                return;
            }
            const dt = new Date(v * 1000);
            const day = String(dt.getDate()).padStart(2, '0');
            const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
            const month = monthNames[dt.getMonth()];
            const hour = String(dt.getHours()).padStart(2, '0');
            const minute = String(dt.getMinutes()).padStart(2, '0');
            previewEl.textContent = `${day} ${month} ${hour}:${minute}`;
            previewEl.title = 'GMT: ' + dt.toUTCString() + ' — ' + relativeTime(dt);
        }
        inputEl.addEventListener('input', update);
        update();
    }

    unixPreview(document.getElementById('start-unix-input'), document.getElementById('start-preview'));
    unixPreview(document.getElementById('end-unix-input'), document.getElementById('end-preview'));
    // initialize displayed datetimes
    convertDisplayedDatetimes();
});
