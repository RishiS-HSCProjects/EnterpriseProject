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

    // Add click listeners to common close attributes (backwards compatible)
    modal.querySelectorAll('[data-close-modal], [data-close-pin-modal]').forEach(function(element) {
        element.addEventListener('click', handleCloseModal);
    });

    // If modal overlay exists, clicking it should close the modal
    modal.querySelectorAll('.modal-overlay').forEach(function(el) {
        el.addEventListener('click', handleCloseModal);
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

/**
 * Convenience helper to wire up a form inside a modal and an open button.
 * Options:
 * - modalId (string): id of the modal element
 * - openButtonSelector (string): selector for the button that opens the modal (optional)
 * - formId (string): id of the form inside the modal (optional)
 * - focusSelector (string): selector for element to focus when opened (optional)
 * - autoOpen (boolean): if true, open immediately
 */
function setupFormModal({modalId, openButtonSelector, formId, focusSelector, autoOpen}) {
    const modal = document.getElementById(modalId);
    if (!modal) return null;

    let focusElement = null;
    if (focusSelector) {
        focusElement = modal.querySelector(focusSelector) || document.querySelector(focusSelector);
    }
    if (!focusElement && formId) {
        const form = modal.querySelector(`#${formId}`) || document.getElementById(formId);
        if (form) focusElement = form.querySelector('input, select, textarea');
    }

    initializeModal(modal, !!autoOpen, focusElement);

    if (openButtonSelector) {
        document.querySelectorAll(openButtonSelector).forEach(btn => {
            btn.addEventListener('click', () => openModal(modal, focusElement));
        });
    }

    return { modal, focusElement };
}

// expose helpers
window.openModal = openModal;
window.closeModal = closeModal;
window.initializeModal = initializeModal;
window.setupFormModal = setupFormModal;
