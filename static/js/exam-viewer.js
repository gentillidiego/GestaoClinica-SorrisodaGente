(() => {
    'use strict';

    const app = document.getElementById('examViewer');
    const shell = document.getElementById('viewerShell');
    if (!app || !shell) return;

    const stage = document.getElementById('viewerStage');
    const imageLayer = document.getElementById('viewerImageLayer');
    const image = document.getElementById('viewerImage');
    const pdf = document.getElementById('viewerPdf');
    const loading = document.getElementById('viewerLoading');
    const caption = document.getElementById('viewerCaption');
    const position = document.getElementById('viewerPosition');
    const zoomLabel = document.getElementById('viewerZoom');
    const originalLink = document.getElementById('viewerOriginalLink');
    const fileButtons = Array.from(document.querySelectorAll('.exam-viewer__file'));

    let activeIndex = 0;
    let zoom = 1;
    let offsetX = 0;
    let offsetY = 0;
    let dragging = false;
    let pointerX = 0;
    let pointerY = 0;

    function currentFile() {
        const button = fileButtons[activeIndex];
        return {
            kind: button.dataset.kind,
            url: button.dataset.url,
            caption: button.dataset.caption,
            filename: button.dataset.filename,
        };
    }

    function clampZoom(value) {
        return Math.min(5, Math.max(0.25, value));
    }

    function renderTransform() {
        const file = currentFile();
        zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
        if (file.kind === 'image') {
            image.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${zoom})`;
            return;
        }
        const percent = Math.round(zoom * 100);
        const left = Math.max(0, Math.round(-offsetX));
        const top = Math.max(0, Math.round(-offsetY));
        pdf.src = `${file.url}#toolbar=1&navpanes=0&zoom=${percent},${left},${top}`;
    }

    function resetView() {
        zoom = 1;
        offsetX = 0;
        offsetY = 0;
        renderTransform();
    }

    function selectFile(index) {
        activeIndex = (index + fileButtons.length) % fileButtons.length;
        const file = currentFile();
        loading.hidden = false;
        imageLayer.hidden = true;
        pdf.hidden = true;
        image.src = '';
        pdf.src = 'about:blank';
        fileButtons.forEach((button, buttonIndex) => {
            button.classList.toggle('is-active', buttonIndex === activeIndex);
        });
        caption.textContent = file.caption || file.filename;
        position.textContent = `${activeIndex + 1} de ${fileButtons.length} · ${file.filename}`;
        originalLink.href = file.url;
        zoom = 1;
        offsetX = 0;
        offsetY = 0;

        if (file.kind === 'image') {
            image.alt = file.caption || file.filename;
            image.addEventListener('load', () => {
                loading.hidden = true;
                imageLayer.hidden = false;
                renderTransform();
            }, {once: true});
            image.addEventListener('error', () => {
                loading.textContent = 'Não foi possível abrir a imagem.';
            }, {once: true});
            image.src = file.url;
        } else {
            pdf.hidden = false;
            loading.hidden = true;
            renderTransform();
        }
    }

    function zoomBy(delta) {
        zoom = clampZoom(zoom + delta);
        renderTransform();
    }

    function moveBy(x, y) {
        offsetX += x;
        offsetY += y;
        renderTransform();
    }

    async function toggleFullscreen() {
        if (document.fullscreenElement) {
            await document.exitFullscreen();
        } else {
            await shell.requestFullscreen();
        }
    }

    shell.addEventListener('click', (event) => {
        const action = event.target.closest('[data-action]')?.dataset.action;
        if (!action) return;
        const actions = {
            'zoom-out': () => zoomBy(-0.25),
            'zoom-in': () => zoomBy(0.25),
            'move-left': () => moveBy(-80, 0),
            'move-up': () => moveBy(0, -80),
            'move-down': () => moveBy(0, 80),
            'move-right': () => moveBy(80, 0),
            reset: resetView,
            fullscreen: toggleFullscreen,
            previous: () => selectFile(activeIndex - 1),
            next: () => selectFile(activeIndex + 1),
        };
        actions[action]?.();
    });

    fileButtons.forEach((button, index) => {
        button.addEventListener('click', () => selectFile(index));
    });

    stage.addEventListener('wheel', (event) => {
        if (currentFile().kind !== 'image') return;
        event.preventDefault();
        zoomBy(event.deltaY < 0 ? 0.15 : -0.15);
    }, {passive: false});

    imageLayer.addEventListener('pointerdown', (event) => {
        dragging = true;
        pointerX = event.clientX;
        pointerY = event.clientY;
        imageLayer.classList.add('is-dragging');
        imageLayer.setPointerCapture(event.pointerId);
    });
    imageLayer.addEventListener('pointermove', (event) => {
        if (!dragging) return;
        offsetX += event.clientX - pointerX;
        offsetY += event.clientY - pointerY;
        pointerX = event.clientX;
        pointerY = event.clientY;
        renderTransform();
    });
    imageLayer.addEventListener('pointerup', (event) => {
        dragging = false;
        imageLayer.classList.remove('is-dragging');
        imageLayer.releasePointerCapture(event.pointerId);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === '+') zoomBy(0.25);
        if (event.key === '-') zoomBy(-0.25);
        if (event.key === '0') resetView();
        if (event.key === 'ArrowLeft') moveBy(-80, 0);
        if (event.key === 'ArrowRight') moveBy(80, 0);
        if (event.key === 'ArrowUp') moveBy(0, -80);
        if (event.key === 'ArrowDown') moveBy(0, 80);
        if (event.key.toLowerCase() === 'f') toggleFullscreen();
    });

    selectFile(0);
})();
