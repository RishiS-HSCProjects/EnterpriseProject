const loaderContainer = document.getElementById('loader-container');

function startLoader() {
    if (loaderContainer) {
        loaderContainer.removeAttribute('hidden');
    }
}

function stopLoader() {
    if (loaderContainer) {
        loaderContainer.setAttribute('hidden', '');
    }
}
