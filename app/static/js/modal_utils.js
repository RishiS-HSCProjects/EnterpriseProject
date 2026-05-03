/**
 * Modal utility functions for managing modal dialogs
 */

/**
 * Opens a modal by setting it to visible and optionally focusing on a specified input
 * @param {HTMLElement} modal - The modal element to open
 * @param {HTMLElement} [focusElement] - Optional element to focus after opening
 */
function openModal(modal, focusElement) {
    modal.hidden = false;
    if (focusElement) {
        focusElement.focus();
    }
}

/**
 * Closes a modal by hiding it
 * @param {HTMLElement} modal - The modal element to close
 */
function closeModal(modal) {
    modal.hidden = true;
}

/**
 * Sets up event listeners for a modal
 * @param {HTMLElement} modal - The modal element
 * @param {HTMLElement} [focusElement] - Optional element to focus when opening
 */
function setupModalListeners(modal, focusElement) {
    const handleCloseModal = () => closeModal(modal);

    // Add click listeners to all close buttons
    modal.querySelectorAll('[data-close-pin-modal]').forEach(function(element) {
        element.addEventListener('click', handleCloseModal);
    });

    // Add escape key listener
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && !modal.hidden) {
            closeModal(modal);
        }
    });
}

/**
 * Initializes a modal with optional auto-open functionality
 * @param {HTMLElement} modal - The modal element
 * @param {boolean} shouldOpen - Whether to automatically open the modal
 * @param {HTMLElement} [focusElement] - Optional element to focus
 */
function initializeModal(modal, shouldOpen, focusElement) {
    setupModalListeners(modal, focusElement);

    if (shouldOpen) {
        openModal(modal, focusElement);
    }
}
