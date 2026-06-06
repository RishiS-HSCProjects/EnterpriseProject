document.addEventListener('DOMContentLoaded', () => {
    const cards = document.querySelectorAll('[data-kpi-kind="countdown"][data-kpi-target-unix]');
    if (!cards.length) return;

    const formatCountdown = (secondsRemaining) => {
        const totalSeconds = Math.max(0, Math.floor(secondsRemaining));
        if (totalSeconds < 60) {
            // Under a minute? Just show seconds
            return `${totalSeconds}s`;
        }
        if (totalSeconds < 3600) {
            // Under an hour? Show minutes and seconds
            const minutes = Math.floor(totalSeconds / 60);
            const seconds = totalSeconds % 60;
            return `${minutes}m ${seconds}s`;
        }
        if (totalSeconds < 86400) {
            // Under a day? Show hours and minutes
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            if (!minutes) {
                return `${hours}h`;
            }
            return `${hours}h ${minutes}m`;
        }

        // Calculate full days in the remaining seconds
        const days = Math.floor(totalSeconds / 86400);
        // Calculate remaining full hours after removing the days portion
        const hours = Math.floor((totalSeconds % 86400) / 3600);
        if (!hours) {
            // If there are no full hours remaining, just show the days
            return `${days}d`;
        }
        // Otherwise, show both days and hours
        return `${days}d ${hours}h`;
    };

    const updateCard = (card) => {
        // Get the target Unix timestamp from the card's data attribute (provided from the Flask route)
        const targetUnix = Number(card.dataset.kpiTargetUnix);
        if (!Number.isFinite(targetUnix)) return; // Invalid or missing target timestamp

        const field = card.dataset.kpiCountdownField === 'detail' ? 'detail' : 'value';
        const targetEl = card.querySelector(field === 'detail' ? '.kpi-bottom' : '.kpi-value');
        if (!targetEl) return;

        const titleEl = card.querySelector('.kpi-top');
        const valueEl = card.querySelector('.kpi-value');
        const detailEl = card.querySelector('.kpi-bottom');

        const secondsRemaining = Math.max(0, targetUnix - Math.floor(Date.now() / 1000));
        const countdownText = `${formatCountdown(secondsRemaining)}`;
        targetEl.textContent = countdownText;

        if (titleEl && valueEl && detailEl) {
            card.setAttribute('aria-label', `${titleEl.textContent}. ${valueEl.textContent}. ${detailEl.textContent}`);
        }
    };

    const tick = () => {
        // Update each countdown card every tick (every second)
        cards.forEach(updateCard);
    };

    tick(); // Initial tick to set values immediately on page load
    window.setInterval(tick, 1000); // Tick ever second after that
});
