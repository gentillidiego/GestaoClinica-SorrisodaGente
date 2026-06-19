(() => {
    'use strict';

    const app = document.getElementById('labExamApp');
    if (!app) return;

    const form = document.getElementById('labExamForm');
    const categoryInput = document.getElementById('categoria');
    const fileInput = document.getElementById('labFiles');
    const dropzone = document.getElementById('labDropzone');
    const selectedPanel = document.getElementById('labSelectedFiles');
    const selectedGrid = document.getElementById('labSelectedFilesGrid');
    const selectedCount = document.getElementById('labSelectedCount');
    const clearSelectionButton = document.getElementById('clearLabSelection');
    const typeError = document.getElementById('labTypeError');
    const fileError = document.getElementById('labFileError');
    const guideTitle = document.getElementById('labExamGuideTitle');
    const guideTests = document.getElementById('labExamGuideTests');
    const saveButton = document.getElementById('saveLabExamButton');
    const idleButtonLabel = saveButton.querySelector('.image-exam-submit__idle');
    const busyButtonLabel = saveButton.querySelector('.image-exam-submit__busy');
    const actionHint = document.getElementById('labActionHint');
    const statusBox = document.getElementById('labUploadStatus');
    const statusIcon = document.getElementById('labUploadStatusIcon');
    const statusTitle = document.getElementById('labUploadStatusTitle');
    const statusMessage = document.getElementById('labUploadStatusMessage');
    const progress = document.getElementById('labUploadProgress');
    const progressBar = document.getElementById('labUploadProgressBar');
    const galleryGrid = document.getElementById('labGalleryGrid');
    const galleryEmpty = document.getElementById('labGalleryEmpty');
    const galleryCount = document.getElementById('labGalleryCount');
    const lightbox = document.getElementById('labLightbox');
    const lightboxImage = document.getElementById('labLightboxImage');
    const lightboxCaption = document.getElementById('labLightboxCaption');
    const lightboxPosition = document.getElementById('labLightboxPosition');

    let examId = app.dataset.examId || '';
    let uploadUrl = app.dataset.uploadUrl || '';
    let viewUrl = app.dataset.viewUrl || '';
    let selectedFiles = [];
    let isBusy = false;
    let currentLightboxIndex = 0;
    const objectUrls = new Set();

    function fileLabel(total) {
        return `${total} ${total === 1 ? 'arquivo' : 'arquivos'}`;
    }

    function showStatus(state, title, message, withProgress = false) {
        const icons = {
            uploading: '↑',
            success: '✓',
            warning: '!',
            error: '×',
            info: 'i',
        };
        statusBox.hidden = false;
        statusBox.dataset.state = state;
        statusIcon.textContent = icons[state] || icons.info;
        statusTitle.textContent = title;
        statusMessage.textContent = message;
        progress.hidden = !withProgress;
        if (!withProgress) {
            progress.classList.remove('is-processing');
            progressBar.style.width = '0%';
        }
    }

    function setProgress(percent) {
        progress.hidden = false;
        progress.classList.remove('is-processing');
        progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    }

    function setProcessingStatus() {
        showStatus(
            'uploading',
            'Arquivos recebidos',
            'Finalizando a gravação segura no prontuário.',
            true,
        );
        progress.classList.add('is-processing');
        progressBar.style.width = '';
    }

    function setBusy(busy) {
        isBusy = busy;
        saveButton.disabled = busy || (!examId && (!categoryInput.value || selectedFiles.length === 0));
        idleButtonLabel.hidden = busy;
        busyButtonLabel.hidden = !busy;
        dropzone.setAttribute('aria-disabled', busy ? 'true' : 'false');
        form.setAttribute('aria-busy', busy ? 'true' : 'false');
    }

    function updateGuide() {
        const option = categoryInput.options[categoryInput.selectedIndex];
        if (!categoryInput.value) {
            guideTitle.textContent = 'O que esta categoria pode incluir';
            guideTests.textContent = 'Selecione um tipo para visualizar os exames mais comuns.';
            return;
        }
        guideTitle.textContent = option.textContent.trim();
        guideTests.textContent = option.dataset.tests || '';
    }

    function updateAction() {
        const total = selectedFiles.length;
        if (examId) {
            idleButtonLabel.textContent = total
                ? `Adicionar ${fileLabel(total)}`
                : 'Salvar alterações';
            actionHint.textContent = total
                ? `${fileLabel(total)} ${total === 1 ? 'pronto' : 'prontos'} para envio.`
                : 'Escolha arquivos para adicionar ou salve alterações nos dados.';
        } else {
            idleButtonLabel.textContent = total
                ? `Salvar exame com ${fileLabel(total)}`
                : 'Salvar exame';
            actionHint.textContent = total
                ? 'Tudo pronto. O exame e os arquivos serão salvos juntos.'
                : 'Selecione o tipo e pelo menos um arquivo.';
        }
        setBusy(isBusy);
    }

    function fileKey(file) {
        return `${file.name}:${file.size}:${file.lastModified}`;
    }

    function isImage(file) {
        return file.type.startsWith('image/') || /\.(jpe?g|png|webp)$/i.test(file.name);
    }

    function validateFiles(files) {
        const accepted = [];
        const errors = [];
        const existingKeys = new Set(selectedFiles.map((entry) => fileKey(entry.file)));

        for (const file of files) {
            const extensionIsValid = /\.(pdf|jpe?g|png|webp)$/i.test(file.name);
            const mimeIsValid = (
                !file.type
                || file.type === 'application/pdf'
                || file.type === 'application/octet-stream'
                || file.type.startsWith('image/')
            );
            if (!extensionIsValid || !mimeIsValid) {
                errors.push(`${file.name}: use PDF, JPG, PNG ou WEBP`);
                continue;
            }
            if (file.size > 25 * 1024 * 1024) {
                errors.push(`${file.name}: ultrapassa 25 MB`);
                continue;
            }
            if (existingKeys.has(fileKey(file))) continue;
            if (selectedFiles.length + accepted.length >= 12) {
                errors.push('O limite é de 12 arquivos por envio');
                break;
            }
            accepted.push(file);
            existingKeys.add(fileKey(file));
        }
        return { accepted, errors };
    }

    function addFiles(files) {
        const { accepted, errors } = validateFiles(Array.from(files || []));
        accepted.forEach((file) => {
            const image = isImage(file);
            const previewUrl = image ? URL.createObjectURL(file) : '';
            if (previewUrl) objectUrls.add(previewUrl);
            selectedFiles.push({ file, isImage: image, previewUrl });
        });
        fileInput.value = '';
        fileError.textContent = errors.join(' · ');
        renderSelectedFiles();
        if (accepted.length && statusBox.dataset.state === 'error') statusBox.hidden = true;
    }

    function removeSelectedFile(index) {
        const [removed] = selectedFiles.splice(index, 1);
        if (removed?.previewUrl) {
            URL.revokeObjectURL(removed.previewUrl);
            objectUrls.delete(removed.previewUrl);
        }
        renderSelectedFiles();
    }

    function clearSelectedFiles() {
        selectedFiles.forEach((entry) => {
            if (entry.previewUrl) {
                URL.revokeObjectURL(entry.previewUrl);
                objectUrls.delete(entry.previewUrl);
            }
        });
        selectedFiles = [];
        fileInput.value = '';
        renderSelectedFiles();
    }

    function renderSelectedFiles() {
        selectedGrid.replaceChildren();
        selectedPanel.hidden = selectedFiles.length === 0;
        selectedCount.textContent = `${fileLabel(selectedFiles.length)} ${
            selectedFiles.length === 1 ? 'selecionado' : 'selecionados'
        }`;

        selectedFiles.forEach((entry, index) => {
            const item = document.createElement('div');
            item.className = 'image-selection-item';

            if (entry.isImage) {
                const image = document.createElement('img');
                image.src = entry.previewUrl;
                image.alt = '';
                item.appendChild(image);
            } else {
                const documentPreview = document.createElement('div');
                documentPreview.className = 'lab-selected-document';
                const badge = document.createElement('span');
                badge.textContent = 'PDF';
                documentPreview.appendChild(badge);
                item.appendChild(documentPreview);
            }

            const filename = document.createElement('span');
            filename.textContent = entry.file.name;
            filename.title = entry.file.name;

            const removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.setAttribute('aria-label', `Remover ${entry.file.name}`);
            removeButton.textContent = '×';
            removeButton.addEventListener('click', () => removeSelectedFile(index));

            item.append(filename, removeButton);
            selectedGrid.appendChild(item);
        });
        updateAction();
    }

    async function parseResponse(response) {
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            throw new Error(
                response.status === 400
                    ? 'Sua sessão de segurança expirou. Recarregue a página e tente novamente.'
                    : 'O servidor não conseguiu concluir a solicitação.',
            );
        }
        return response.json();
    }

    function metadataFormData() {
        const data = new FormData();
        data.append('csrf_token', document.getElementById('labCsrfToken').value);
        data.append('categoria', categoryInput.value);
        data.append('laboratorio', document.getElementById('laboratorio').value.trim());
        data.append('data_coleta', document.getElementById('data_coleta').value);
        data.append('observacoes', document.getElementById('observacoes').value.trim());
        return data;
    }

    async function saveMetadata() {
        const targetUrl = examId ? viewUrl : app.dataset.createUrl;
        const response = await fetch(targetUrl, {
            method: 'POST',
            body: metadataFormData(),
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            },
        });
        const data = await parseResponse(response);
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Não foi possível salvar os dados do exame.');
        }

        examId = String(data.exam_id);
        uploadUrl = data.upload_url;
        viewUrl = data.view_url;
        app.dataset.examId = examId;
        app.dataset.uploadUrl = uploadUrl;
        app.dataset.viewUrl = viewUrl;
        window.history.replaceState({}, '', viewUrl);
    }

    function uploadFormData() {
        const data = new FormData();
        selectedFiles.forEach((entry) => data.append('files', entry.file, entry.file.name));
        data.append('csrf_token', document.getElementById('labCsrfToken').value);
        data.append('caption', document.getElementById('labCaption').value.trim());
        return data;
    }

    function uploadFiles() {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', uploadUrl);
            xhr.setRequestHeader('Accept', 'application/json');
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
            xhr.timeout = 4 * 60 * 1000;

            xhr.upload.addEventListener('progress', (event) => {
                if (!event.lengthComputable) return;
                const percent = Math.round((event.loaded / event.total) * 100);
                showStatus(
                    'uploading',
                    `Enviando ${fileLabel(selectedFiles.length)}`,
                    `${percent}% transferido. Não feche esta página.`,
                    true,
                );
                setProgress(percent);
                if (percent >= 100) setProcessingStatus();
            });
            xhr.addEventListener('load', () => {
                let data;
                try {
                    data = JSON.parse(xhr.responseText);
                } catch (_error) {
                    reject(new Error('O servidor não retornou uma confirmação válida.'));
                    return;
                }
                if ((xhr.status >= 200 && xhr.status < 300) || data.partial) {
                    resolve(data);
                    return;
                }
                reject(new Error(data.error || 'Não foi possível enviar os arquivos.'));
            });
            xhr.addEventListener('error', () => {
                reject(new Error('A conexão foi interrompida durante o envio. Tente novamente.'));
            });
            xhr.addEventListener('timeout', () => {
                reject(new Error('O envio demorou mais que o esperado. Verifique os arquivos salvos antes de tentar novamente.'));
            });
            xhr.send(uploadFormData());
        });
    }

    function initializeGalleryImage(image) {
        const markLoaded = () => image.classList.add('is-loaded');
        if (image.complete && image.naturalWidth) markLoaded();
        else image.addEventListener('load', markLoaded, { once: true });
        image.addEventListener('error', () => {
            const loading = image.parentElement.querySelector('.image-gallery-item__loading');
            if (loading) loading.textContent = 'Não foi possível exibir';
        }, { once: true });
    }

    function updateSyncBadge(badge, status, label) {
        badge.dataset.syncStatus = status;
        badge.className = `file-sync-status file-sync-status--${status}`;
        const text = badge.querySelector('span');
        if (text) text.textContent = label;
    }

    function pollSyncBadge(badge, delay = 1200) {
        if (!badge?.dataset.statusUrl || badge.dataset.syncStatus === 'synced') return;
        window.setTimeout(async () => {
            try {
                const response = await fetch(badge.dataset.statusUrl, {
                    headers: {'Accept': 'application/json'},
                });
                const data = await response.json();
                if (response.ok && data.success) {
                    updateSyncBadge(badge, data.status, data.label);
                    if (data.status !== 'synced') {
                        pollSyncBadge(badge, data.status === 'failed' ? 15000 : 2500);
                    }
                    return;
                }
            } catch (_error) {
                // A cópia local continua disponível; uma nova consulta será feita.
            }
            pollSyncBadge(badge, 10000);
        }, delay);
    }

    function buildSyncBadge(fileData) {
        const badge = document.createElement('span');
        const status = fileData.storage_status || 'pending';
        badge.className = `file-sync-status file-sync-status--${status}`;
        badge.dataset.syncStatus = status;
        badge.dataset.statusUrl = fileData.status_url || '';
        const dot = document.createElement('i');
        dot.setAttribute('aria-hidden', 'true');
        const text = document.createElement('span');
        text.textContent = fileData.storage_label || 'Salvo no prontuário · aguardando sincronização';
        badge.append(dot, text);
        pollSyncBadge(badge);
        return badge;
    }

    function buildGalleryItem(fileData, previewUrl) {
        const isImageFile = Boolean(fileData.is_image);
        const item = document.createElement(isImageFile ? 'button' : 'a');
        item.className = 'image-gallery-item lab-gallery-item';
        item.dataset.fileId = fileData.id;
        item.dataset.fileUrl = previewUrl || fileData.preview_url || fileData.url;
        item.dataset.serverUrl = fileData.preview_url || fileData.url;
        item.dataset.originalUrl = fileData.url;
        item.dataset.fileCaption = fileData.caption || fileData.filename;
        item.dataset.isImage = isImageFile ? 'true' : 'false';
        item.dataset.statusUrl = fileData.status_url || '';

        if (isImageFile) {
            item.type = 'button';
            item.setAttribute('aria-label', `Abrir ${fileData.caption || fileData.filename}`);
        } else {
            item.href = fileData.url;
            item.target = '_blank';
            item.rel = 'noopener';
            item.setAttribute('aria-label', `Abrir laudo ${fileData.caption || fileData.filename}`);
        }

        const media = document.createElement('span');
        media.className = isImageFile
            ? 'image-gallery-item__media'
            : 'image-gallery-item__media lab-document-media';

        if (isImageFile) {
            const loading = document.createElement('span');
            loading.className = 'image-gallery-item__loading';
            loading.textContent = 'Carregando…';
            const image = document.createElement('img');
            image.src = previewUrl || fileData.thumbnail_url || fileData.preview_url || fileData.url;
            image.alt = fileData.caption || fileData.filename;
            initializeGalleryImage(image);
            media.append(loading, image);
        } else {
            const icon = document.createElement('span');
            icon.className = 'lab-document-icon';
            icon.textContent = 'PDF';
            const action = document.createElement('span');
            action.className = 'lab-document-action';
            action.textContent = 'Abrir laudo';
            media.append(icon, action);
        }

        const info = document.createElement('span');
        info.className = 'image-gallery-item__info';
        const caption = document.createElement('strong');
        caption.textContent = fileData.caption || fileData.filename;
        const filename = document.createElement('small');
        filename.textContent = fileData.filename;
        info.append(caption, filename, buildSyncBadge(fileData));
        item.append(media, info);
        return item;
    }

    function addSavedFilesToGallery(files) {
        const previews = new Map();
        selectedFiles.forEach((entry) => {
            if (!entry.previewUrl) return;
            const urls = previews.get(entry.file.name) || [];
            urls.push(entry.previewUrl);
            previews.set(entry.file.name, urls);
        });

        const savedNames = [];
        files.forEach((fileData) => {
            const clientName = fileData.client_filename || fileData.filename;
            const urls = previews.get(clientName) || [];
            const previewUrl = urls.shift();
            savedNames.push(clientName);
            galleryGrid.appendChild(buildGalleryItem(fileData, previewUrl));
        });

        const namesToRemove = new Map();
        savedNames.forEach((name) => namesToRemove.set(name, (namesToRemove.get(name) || 0) + 1));
        selectedFiles = selectedFiles.filter((entry) => {
            const count = namesToRemove.get(entry.file.name) || 0;
            if (!count) return true;
            namesToRemove.set(entry.file.name, count - 1);
            return false;
        });

        galleryGrid.hidden = false;
        galleryEmpty.hidden = true;
        galleryCount.textContent = String(galleryGrid.querySelectorAll('.lab-gallery-item').length);
        renderSelectedFiles();
    }

    function validateForm() {
        typeError.textContent = '';
        fileError.textContent = '';
        categoryInput.removeAttribute('aria-invalid');
        if (!categoryInput.value) {
            typeError.textContent = 'Selecione o tipo do exame.';
            categoryInput.setAttribute('aria-invalid', 'true');
            categoryInput.focus();
            return false;
        }
        if (!examId && selectedFiles.length === 0) {
            fileError.textContent = 'Selecione pelo menos um laudo ou imagem.';
            dropzone.focus();
            return false;
        }
        return true;
    }

    async function handleSubmit(event) {
        event.preventDefault();
        if (isBusy || !validateForm()) return;

        setBusy(true);
        showStatus(
            'uploading',
            'Preparando o exame',
            'Salvando os dados clínicos antes do envio.',
            true,
        );
        progress.classList.add('is-processing');

        try {
            await saveMetadata();
            if (selectedFiles.length === 0) {
                showStatus('success', 'Alterações salvas', 'Os dados do exame foram atualizados com sucesso.');
                return;
            }

            const result = await uploadFiles();
            if (result.files?.length) addSavedFilesToGallery(result.files);
            if (result.partial) {
                showStatus(
                    'warning',
                    'Envio parcialmente concluído',
                    `${result.error} Os arquivos salvos já aparecem abaixo; tente novamente apenas com os restantes.`,
                );
            } else {
                showStatus(
                    'success',
                    'Envio concluído',
                    result.message || `${fileLabel(result.total || 0)} ${
                        result.total === 1 ? 'salvo' : 'salvos'
                    } com segurança.`,
                );
            }
        } catch (error) {
            showStatus(
                'error',
                examId ? 'Não foi possível concluir o envio' : 'Não foi possível salvar o exame',
                error.message,
            );
        } finally {
            setBusy(false);
            updateAction();
        }
    }

    function galleryImageItems() {
        return Array.from(galleryGrid.querySelectorAll('.lab-gallery-item[data-is-image="true"]'));
    }

    function openLightbox(index) {
        const items = galleryImageItems();
        if (!items.length) return;
        currentLightboxIndex = (index + items.length) % items.length;
        const item = items[currentLightboxIndex];
        lightboxImage.src = item.dataset.fileUrl;
        lightboxImage.alt = item.dataset.fileCaption;
        lightboxCaption.textContent = item.dataset.fileCaption;
        lightboxPosition.textContent = `${currentLightboxIndex + 1} de ${items.length}`;
        lightbox.hidden = false;
        document.body.classList.add('image-lightbox-open');
        document.getElementById('closeLabLightbox').focus();
    }

    function closeLightbox() {
        lightbox.hidden = true;
        lightboxImage.src = '';
        document.body.classList.remove('image-lightbox-open');
    }

    dropzone.addEventListener('click', () => {
        if (!isBusy) fileInput.click();
    });
    dropzone.addEventListener('dragover', (event) => {
        event.preventDefault();
        if (!isBusy) dropzone.classList.add('is-dragging');
    });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('is-dragging'));
    dropzone.addEventListener('drop', (event) => {
        event.preventDefault();
        dropzone.classList.remove('is-dragging');
        if (!isBusy) addFiles(event.dataTransfer.files);
    });
    fileInput.addEventListener('change', () => addFiles(fileInput.files));
    clearSelectionButton.addEventListener('click', clearSelectedFiles);
    categoryInput.addEventListener('change', () => {
        typeError.textContent = '';
        categoryInput.removeAttribute('aria-invalid');
        updateGuide();
        updateAction();
    });
    form.addEventListener('submit', handleSubmit);
    document.getElementById('closeLabStatus').addEventListener('click', () => {
        if (!isBusy) statusBox.hidden = true;
    });
    galleryGrid.addEventListener('click', (event) => {
        const item = event.target.closest('.lab-gallery-item[data-is-image="true"]');
        if (!item) return;
        openLightbox(galleryImageItems().indexOf(item));
    });
    document.getElementById('closeLabLightbox').addEventListener('click', closeLightbox);
    document.getElementById('previousLabImage').addEventListener('click', () => openLightbox(currentLightboxIndex - 1));
    document.getElementById('nextLabImage').addEventListener('click', () => openLightbox(currentLightboxIndex + 1));
    lightbox.addEventListener('click', (event) => {
        if (event.target === lightbox) closeLightbox();
    });
    document.addEventListener('keydown', (event) => {
        if (lightbox.hidden) return;
        if (event.key === 'Escape') closeLightbox();
        if (event.key === 'ArrowLeft') openLightbox(currentLightboxIndex - 1);
        if (event.key === 'ArrowRight') openLightbox(currentLightboxIndex + 1);
    });
    window.addEventListener('beforeunload', (event) => {
        if (!isBusy) return;
        event.preventDefault();
        event.returnValue = '';
    });
    window.addEventListener('pagehide', () => {
        objectUrls.forEach((url) => URL.revokeObjectURL(url));
    });

    document.querySelectorAll('.lab-gallery-item img').forEach(initializeGalleryImage);
    document.querySelectorAll('.file-sync-status').forEach((badge) => pollSyncBadge(badge));
    updateGuide();
    updateAction();
})();
