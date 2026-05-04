document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('add-modal');
    if (!modal) return;

    setupFormModal({
        modalId: 'add-modal',
        openButtonSelector: '.create-tournament-btn',
        formId: 'add-tournament-form',
        focusSelector: 'input[type="text"]',
        autoOpen: modal.dataset.showAddModal === 'true'
    });

    const relativeTime = (dt) => {
        const diffSec = Math.floor((Date.now() - dt.getTime()) / 1000);
        const future = diffSec < 0;
        const abs = Math.abs(diffSec);
        const units = [
            { limit: 5, unit: 'second' }, // Just now
            { limit: 60, unit: 'second' }, // 60
            { limit: 3600, unit: 'minute', divisor: 60 }, // 60 * 60
            { limit: 86400, unit: 'hour', divisor: 3600 }, // 24 * 3600
            { limit: 2592000, unit: 'day', divisor: 86400 }, // Approximate month as 30 days
            { limit: Infinity, unit: 'month', divisor: 2592000 } // Approximate month as 30 days
        ];
        
        for (const { limit, unit, divisor = 1 } of units) {
            if (abs < limit) {
                const value = divisor === 1 ? abs : Math.floor(abs / divisor);
                const s = value !== 1 ? 's' : '';
                return future ? `in ${value} ${unit}${s}` : `${value} ${unit}${s} ago`;
            }
        }
        
        const years = Math.floor(abs / 31536000);
        const s = years !== 1 ? 's' : '';
        return future ? `in ${years} year${s}` : `${years} year${s} ago`;
    };

    // Display unix timestamp as formatted date with preview
    const formatDate = (unix) => {
        const dt = new Date(unix * 1000);
        const day = String(dt.getDate()).padStart(2, '0');
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const month = months[dt.getMonth()];
        const hour = String(dt.getHours()).padStart(2, '0');
        const min = String(dt.getMinutes()).padStart(2, '0');
        return { display: `${day} ${month} ${hour}:${min}`, utc: dt.toUTCString(), relative: relativeTime(dt) };
    };

    // Convert displayed datetimes with class 'dt' and data-unix attribute
    document.querySelectorAll('.dt[data-unix]').forEach(el => {
        const unix = parseInt(el.dataset.unix, 10);
        if (!isNaN(unix)) {
            const { display, utc, relative } = formatDate(unix);
            el.textContent = `Local Time: ${display}`;
            el.title = `GMT: ${utc} ・ ${relative}`;
        }
    });

    // Format duration in seconds to readable format
    const formatDuration = (seconds) => {
        if (seconds <= 0) return null;
        const units = [
            { limit: 60, unit: 'second' },
            { limit: 3600, unit: 'minute', divisor: 60 },
            { limit: 86400, unit: 'hour', divisor: 3600 },
            { limit: 604800, unit: 'day', divisor: 86400 },
            { limit: Infinity, unit: 'week', divisor: 604800 }
        ];
        
        for (const { limit, unit, divisor = 1 } of units) {
            if (seconds < limit) {
                const value = divisor === 1 ? Math.round(seconds) : (seconds / divisor).toFixed(1);
                const s = value !== 1 && value !== '1.0' ? 's' : '';
                return { display: `${value} ${unit}${s}`, seconds: Math.round(seconds) };
            }
        }
    };

    // Update round duration preview when start, end, or round count changes
    const updateRoundDuration = () => {
        const startVal = parseInt(document.getElementById('start-unix-input').value, 10);
        const endVal = parseInt(document.getElementById('end-unix-input').value, 10);
        const roundCountVal = parseInt(document.getElementById('round-count-input').value, 10);
        const previewEl = document.getElementById('round-duration-preview');

        if (isNaN(startVal) || isNaN(endVal) || isNaN(roundCountVal) || roundCountVal <= 0 || endVal <= startVal) {
            previewEl.textContent = '';
            previewEl.title = '';
            previewEl.style.display = 'none';
            return;
        }

        const totalDuration = endVal - startVal;
        const roundDuration = totalDuration / roundCountVal;
        const formatted = formatDuration(roundDuration);

        if (formatted) {
            previewEl.textContent = `Round duration: ${formatted.display} (${formatted.seconds} seconds)`;
            previewEl.title = `Total tournament duration: ${totalDuration} seconds / ${roundCountVal} rounds`;
            previewEl.style.display = 'block';
        } else {
            previewEl.textContent = '';
            previewEl.title = '';
            previewEl.style.display = 'none';
        }
    };

    // Wire up unix input preview updates
    [
        { input: 'start-unix-input', preview: 'start-preview' },
        { input: 'end-unix-input', preview: 'end-preview' }
    ].forEach(({ input, preview }) => {
        const inputEl = document.getElementById(input);
        const previewEl = document.getElementById(preview);
        if (!inputEl || !previewEl) return;
        
        const update = () => {
            const v = parseInt(inputEl.value, 10);
            if (isNaN(v)) {
                previewEl.textContent = '';
                previewEl.title = '';
                previewEl.style.display = 'none';
            } else {
                const { display, utc, relative } = formatDate(v);
                previewEl.textContent = display;
                previewEl.title = `GMT: ${utc} ・ ${relative}`;
                previewEl.style.display = 'block';
            }
        };
        inputEl.addEventListener('input', () => {
            update();
            updateRoundDuration();
        });
        update();
    });

    // Date picker to UTC midnight epoch conversion
    const dateToEpoch = (dateValue) => {
        if (!dateValue) return null;
        const [year, month, day] = dateValue.split('-').map(Number);
        const utcDate = new Date(Date.UTC(year, month - 1, day, 0, 0, 0));
        return Math.floor(utcDate.getTime() / 1000);
    };

    const handleDatePicker = (pickerId, unixInputId) => {
        const picker = document.getElementById(pickerId);
        const input = document.getElementById(unixInputId);
        if (!picker || !input) return;
        
        picker.addEventListener('change', () => {
            const epoch = dateToEpoch(picker.value);
            if (epoch !== null) {
                input.value = epoch;
                input.dispatchEvent(new Event('input'));
            }
        });
    };

    handleDatePicker('start-date-picker', 'start-unix-input');
    handleDatePicker('end-date-picker', 'end-unix-input');

    // Wire up round count input
    ['start-unix-input', 'end-unix-input', 'round-count-input'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', updateRoundDuration);
        }
    });
    updateRoundDuration();
});
