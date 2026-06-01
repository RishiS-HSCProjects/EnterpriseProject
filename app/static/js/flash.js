/**
 * Flash Message System
 * Handles client-side display, timing, and interaction for flash messages.
 */

const FLASH_DURATION = 10000; // Duration to show message (ms)
const FLASH_STAGGER = 500;    // Delay between showing multiple messages (ms)

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('flash-container');
    if (!container) {
        return;
    }

    const messages = Array.from(
        container.querySelectorAll('.flash-message')
    );

    updateFlashContainerVisibility(container);

    messages.forEach((msg, index) => initFlashMessage(msg, index, container));

    const syncFlashTimers = () => {
        const shouldPause = document.hidden || !document.hasFocus();
        const activeMessages = Array.from(
            container.querySelectorAll('.flash-message')
        );

        activeMessages.forEach((msg) => {
            if (msg.fadeOutStarted) {
                return;
            }

            if (shouldPause) {
                pauseTimer(msg, 'focus');
            } else {
                resumeTimer(msg, 'focus');
            }
        });
    };

    window.addEventListener('blur', syncFlashTimers);
    window.addEventListener('focus', syncFlashTimers);
    document.addEventListener('visibilitychange', syncFlashTimers);
});

/**
 * Initialize a flash message with display and timing logic.
 * Handles auto-dismiss, hover interactions, and click-to-dismiss.
 * 
 * @param {HTMLElement} msg - The flash message element to initialize.
 * @param {number} index - The index for staggered display timing.
 */
function initFlashMessage(msg, index = 0, container = document.getElementById('flash-container')) {
    // Stagger display
    setTimeout(() => {
        if (container) {
            updateFlashContainerVisibility(container, true);
        }

        msg.style.display = 'flex'; // Ensure the message is visible for animation
        setTimeout(() => {
            msg.classList.add('show');

            // Force reflow so transitions don't skip
            void msg.offsetWidth;

            // Initialize internal state
            msg.remaining = FLASH_DURATION;
            msg.lastTick = Date.now();
            msg.fadeOutStarted = false;
            msg.pauseReasons = msg.pauseReasons || new Set();

            if (document.hidden || !document.hasFocus()) {
                pauseTimer(msg, 'focus');
            } else {
                msg.timer = requestAnimationFrame(() => tick(msg));
            }

            // Hover to pause timer
            msg.addEventListener('mouseenter', () => {
                if (msg.fadeOutStarted) return;
                pauseTimer(msg, 'hover');
            });

            // Hover to resume timer (with bonus time)
            msg.addEventListener('mouseleave', () => {
                if (msg.fadeOutStarted) return;
                msg.remaining = Math.min(msg.remaining + 2000, FLASH_DURATION);
                resumeTimer(msg, 'hover');
            });

            // Click to dismiss immediately
            msg.addEventListener('click', () => {
                pauseTimer(msg, 'hover');
                pauseTimer(msg, 'focus');
                fadeOut(msg);
            });
        }, 100);

    }, index * FLASH_STAGGER);
}

/**
 * Handle the timer tick for a flash message.
 * Updates the remaining time and triggers fade-out when done.
 * 
 * @param {HTMLElement} msg - The flash message element.
 */
function tick(msg) {
    const now = Date.now();
    const elapsed = now - msg.lastTick;
    msg.lastTick = now;

    msg.remaining -= elapsed;

    if (msg.remaining <= 0) {
        fadeOut(msg);
        return;
    }

    msg.timer = requestAnimationFrame(() => tick(msg));
}

/**
 * Pause the auto-dismiss timer for a flash message.
 * 
 * @param {HTMLElement} msg - The flash message element.
 * @param {string} [reason='manual'] - Why the timer is being paused.
 */
function pauseTimer(msg, reason = 'manual') {
    if (!msg.pauseReasons) {
        msg.pauseReasons = new Set();
    }

    msg.pauseReasons.add(reason);

    if (msg.timer) {
        cancelAnimationFrame(msg.timer);
        msg.timer = null;
    }
}

/**
 * Resume the auto-dismiss timer for a flash message.
 * 
 * @param {HTMLElement} msg - The flash message element.
 * @param {string} [reason='manual'] - Why the timer is being resumed.
 */
function resumeTimer(msg, reason = 'manual') {
    if (msg.pauseReasons) {
        msg.pauseReasons.delete(reason);
    }

    if (!msg.timer && (!msg.pauseReasons || msg.pauseReasons.size === 0)) {
        msg.lastTick = Date.now();
        msg.timer = requestAnimationFrame(() => tick(msg));
    }
}

/**
 * Fade out and remove a flash message.
 * 
 * @param {HTMLElement} msg - The flash message element to fade out.
 */
function fadeOut(msg) {
    if (msg.fadeOutStarted) return;

    const container = msg.parentElement;

    msg.fadeOutStarted = true;
    msg.classList.add('fade-out');
    msg.style.transition = 'opacity 0.45s ease, transform 0.45s ease';
    msg.style.opacity = '0';
    msg.style.transform = 'scale(0.95)';

    setTimeout(() => {
        msg.remove();
        if (container) {
            updateFlashContainerVisibility(container);
        }
    }, 450);
}

/**
 * Send a flash message dynamically from JavaScript (e.g., during AJAX requests).
 * Creates and displays a flash message without requiring a page reload.
 * 
 * @param {string} message - The message text to display.
 * @param {string} category - The message category: 'success', 'error', 'warning', or 'info'.
 */
function sendFlashMessage(message, category = 'info') {
    const container = document.getElementById('flash-container');
    if (!container) {
        console.error('Flash container not found in DOM.');
        return;
    }

    // Validate category
    const validCategories = ['success', 'error', 'warning', 'info'];
    if (!validCategories.includes(category)) {
        category = 'info';
    }

    // Create message element
    const msg = document.createElement('div');
    msg.className = `flash-message ${category}`;
    msg.textContent = message;

    // Add to container
    container.appendChild(msg);
    updateFlashContainerVisibility(container, true);

    // Initialize with staggered timing
    const messageCount = container.querySelectorAll('.flash-message:not(.fade-out)').length;
    initFlashMessage(msg, messageCount - 1, container);
}

/**
 * Show or hide the flash container depending on active messages.
 *
 * @param {HTMLElement} container - The flash container element.
 * @param {boolean} forceVisible - Force the container to display while messages are being added.
 */
function updateFlashContainerVisibility(container, forceVisible = false) {
    const activeMessages = container.querySelectorAll('.flash-message:not(.fade-out)').length;

    if (forceVisible || activeMessages > 0) {
        container.style.display = 'flex';
        return;
    }

    container.style.display = 'none';
}
