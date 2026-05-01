import { initializeModal } from './modal_utils.js';

document.addEventListener('DOMContentLoaded', function() {
    const firstInput = document.querySelector('input[type="text"]');
    if (firstInput) {
        firstInput.focus();
    }

    const state = document.getElementById('registration-state');
    const modal = document.getElementById('pin-modal');

    if (!state || !modal) {
        return;
    }

    const pinInput = modal.querySelector('input[name="pin"]');
    const shouldOpenModal = state.dataset.openPinModal === 'true';

    initializeModal(modal, shouldOpenModal, pinInput);
});
