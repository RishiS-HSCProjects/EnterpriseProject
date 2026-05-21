/**
 * Flash Message System
 * Handles client-side display, timing, and interaction for flash messages.
 */

const FLASH_DURATION = 10000; // Duration to show message (ms)
const FLASH_STAGGER = 500;    // Delay between showing multiple messages (ms)

document.addEventListener('DOMContentLoaded', () => {
    const messages = Array.from(
        document.querySelectorAll('#flash-container .flash-message')
    );

    messages.forEach((msg, index) => initFlashMessage(msg, index));
});

/**
 * Initialize a flash message with display and timing logic.
 * Handles auto-dismiss, hover interactions, and click-to-dismiss.
 * 
 * @param {HTMLElement} msg - The flash message element to initialize.
 * @param {number} index - The index for staggered display timing.
 */
function initFlashMessage(msg, index = 0) {
    // Stagger display
    setTimeout(() => {
        msg.classList.add('show');

        // Force reflow so transitions don't skip
        void msg.offsetWidth;

        // Initialize internal state
        msg.remaining = FLASH_DURATION;
        msg.lastTick = Date.now();
        msg.fadeOutStarted = false;
        msg.timer = requestAnimationFrame(() => tick(msg));

        // Hover to pause timer
        msg.addEventListener('mouseenter', () => {
            if (msg.fadeOutStarted) return;
            pauseTimer(msg);
        });

        // Hover to resume timer (with bonus time)
        msg.addEventListener('mouseleave', () => {
            if (msg.fadeOutStarted) return;
            msg.remaining = Math.min(msg.remaining + 2000, FLASH_DURATION);
            resumeTimer(msg);
        });

        // Click to dismiss immediately
        msg.addEventListener('click', () => {
            pauseTimer(msg);
            fadeOut(msg);
        });

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
 */
function pauseTimer(msg) {
    if (msg.timer) {
        cancelAnimationFrame(msg.timer);
        msg.timer = null;
    }
}

/**
 * Resume the auto-dismiss timer for a flash message.
 * 
 * @param {HTMLElement} msg - The flash message element.
 */
function resumeTimer(msg) {
    if (!msg.timer) {
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

    msg.fadeOutStarted = true;
    msg.classList.add('fade-out');
    msg.style.transition = 'opacity 0.45s ease, transform 0.45s ease';
    msg.style.opacity = '0';
    msg.style.transform = 'scale(0.95)';

    setTimeout(() => {
        msg.remove();
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

    // Initialize with staggered timing
    const messageCount = container.querySelectorAll('.flash-message:not(.fade-out)').length;
    initFlashMessage(msg, messageCount - 1);
}
