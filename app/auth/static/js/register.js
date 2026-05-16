document.addEventListener("DOMContentLoaded", () => {
    const registerForm = document.getElementById("register-form");
    registerForm.addEventListener("submit", (event) => {
        event.preventDefault();
        handleVerificationSubmit();
    });

    const pinForm = document.getElementById("pin-form");
    pinForm.addEventListener("submit", (event) => {
        event.preventDefault();
        handlePinSubmit();
    });

    const regState = document.getElementById('registration-state');
    const autoOpen = regState && regState.dataset.openPinModal === 'true';
    if (typeof setupFormModal === 'function') {
        setupFormModal({
            modalId: 'pin-modal',
            formId: 'pin-form',
            focusSelector: 'input[name="pin"]',
            autoOpen: autoOpen
        });
    }
});

function handleVerificationSubmit() {
    startLoader();

    const form = document.getElementById("register-form");
    const formData = new FormData(form);

    fetch("/register/handle/pin", {
        method: "POST",
        body: formData,
        credentials: "include"
    })
    .then(async response => {
        const text = await response.text();

        let data;
        try {
            data = JSON.parse(text);
        } catch {
            console.error("Server did not return JSON:", text);
            endLoader();
            return;
        }

        if (data.status === "error") {
            endLoader();
            window.location.href = "/register";
            return;
        }

        endLoader();

        if (data.message) console.log("Server message:", data.message);

        // Show modal (use central helper openModal if available)
        const modal = document.getElementById("pin-modal");
        const pinInput = modal ? modal.querySelector('input[name="pin"]') : null;
        if (typeof openModal === 'function' && modal) openModal(modal, pinInput);
        else if (modal) modal.removeAttribute("hidden");
        return;
    })
        .catch(error => {
        console.error("Error:", error);
        endLoader();
    });
}

function handlePinSubmit() {
    const form = document.getElementById("pin-form");
    const formData = new FormData(form);

    fetch("/register/verify/pin", {
        method: "POST",
        body: formData,
        credentials: "include"
    })
    .then(async response => {
        const text = await response.text();
        let data;
        try {
            data = JSON.parse(text);
        } catch {
            console.error("Server did not return JSON:", text);
            window.location.href = "/register";
            return;
        }

        if (data.status === "error") {
            if (data.message) console.error("Verification error:", data.message);

            if (response.status === 409) window.location.href = "/login";
            else window.location.href = "/register";

            return;
        }

        if (data.message) console.log("Verification success:", data.message);
        window.location.href = "/login";
    })
    .catch(error => {
        console.error("Error:", error);
        window.location.href = "/register";
    });
}
