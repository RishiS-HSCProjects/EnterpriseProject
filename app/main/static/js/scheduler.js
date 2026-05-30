document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('add-modal');
    if (!modal) return;

    setupFormModal({
        modalId: 'add-modal',
        openButtonSelector: '.create-tournament-btn',
        formId: 'add-tournament-form',
        focusSelector: 'input[type="text"]',
        autoOpen: modal.dataset.showAddModal === 'true'
    });

    // Use shared TimeUtils for date formatting and relative times

    // Convert displayed datetimes with class 'dt' and data-unix attribute
    document.querySelectorAll('.dt[data-unix]').forEach(el => {
        const unix = parseInt(el.dataset.unix, 10);
        if (!isNaN(unix) && window.TimeUtils && typeof window.TimeUtils.formatDateLocal === 'function') {
            const { display, utc, relative } = window.TimeUtils.formatDateLocal(unix);
            el.textContent = `Local Time: ${display}`;
            el.title = `GMT: ${utc} ・ ${relative}`;
        }
    });

    // Use shared TimeUtils.formatDuration

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
        const formatted = (window.TimeUtils && typeof window.TimeUtils.formatDuration === 'function') ? window.TimeUtils.formatDuration(roundDuration) : null;

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

    // Wire up unix input preview updates (write into `time-info` elements)
    [
        { input: 'start-unix-input', preview: 'start-info' },
        { input: 'end-unix-input', preview: 'end-info' }
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
            } else if (window.TimeUtils && typeof window.TimeUtils.formatDateLocal === 'function') {
                const { display: local, utc, relative } = window.TimeUtils.formatDateLocal(v);
                // show both local display and epoch value
                previewEl.innerHTML = `${local} | Epoch: <code>${v}</code>`;
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
        if (window.TimeUtils && typeof window.TimeUtils.dateToEpoch === 'function') {
            return window.TimeUtils.dateToEpoch(dateValue);
        }
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
