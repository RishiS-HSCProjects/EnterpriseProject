document.addEventListener('DOMContentLoaded', function() {
    // Automatically put focus on the first visible/interactable element in the registration forms
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

    if (shouldOpenModal) stopLoader();
});
