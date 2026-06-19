(() => {
    'use strict';

    const app = document.getElementById('imageExamApp');
    if (!app) return;

    const form = document.getElementById('imageExamForm');
    const typeInput = document.getElementById('tipo_imagem');
    const regionInput = document.getElementById('detalhe_escopo');
    const regionHint = document.getElementById('regionHint');
    const fileInput = document.getElementById('imageFiles');
    const dropzone = document.getElementById('imageDropzone');
    const selectedPanel = document.getElementById('selectedImages');
    const selectedGrid = document.getElementById('selectedImagesGrid');
    const selectedCount = document.getElementById('selectedCount');
    const clearSelectionButton = document.getElementById('clearSelection');
    const typeError = document.getElementById('typeError');
    const fileError = document.getElementById('fileError');
    const saveButton = document.getElementById('saveExamButton');
    const idleButtonLabel = saveButton.querySelector('.image-exam-submit__idle');
    const busyButtonLabel = saveButton.querySelector('.image-exam-submit__busy');
    const actionHint = document.getElementById('actionHint');
    const statusBox = document.getElementById('uploadStatus');
    const statusIcon = document.getElementById('uploadStatusIcon');
    const statusTitle = document.getElementById('uploadStatusTitle');
    const statusMessage = document.getElementById('uploadStatusMessage');
    const progress = document.getElementById('uploadProgress');
    const progressBar = document.getElementById('uploadProgressBar');
    const closeStatus = document.getElementById('closeStatus');
    const galleryGrid = document.getElementById('galleryGrid');
    const galleryEmpty = document.getElementById('galleryEmpty');
    const galleryCount = document.getElementById('galleryCount');
    const lightbox = document.getElementById('imageLightbox');
    const lightboxImage = document.getElementById('lightboxImage');
    const lightboxCaption = document.getElementById('lightboxCaption');
    const lightboxPosition = document.getElementById('lightboxPosition');

    let examId = app.dataset.examId || '';
    let uploadUrl = app.dataset.uploadUrl || '';
    let viewUrl = app.dataset.viewUrl || '';
    const returnUrl = app.dataset.returnUrl || '';
    let selectedFiles = [];
    let isBusy = false;
    let allowNavigation = false;
    let currentLightboxIndex = 0;
    const objectUrls = new Set();

    const regionRules = {
        'Periapical': ['Ex.: dentes 11 e 21', 'Informe os dentes apenas se isso ajudar a identificar o exame.'],
        'Bite-wing': ['Ex.: lado direito ou 1º quadrante', 'O lado ou quadrante é opcional.'],
        'Oclusal': ['Ex.: arcada superior', 'A arcada é opcional.'],
        'Panorâmica': ['Normalmente não é necessário', 'A panorâmica já abrange as duas arcadas.'],
        'Telerradiografia': ['Normalmente não é necessário', 'Preencha somente se houver uma observação de localização.'],
        'Tomografia': ['Ex.: região dos dentes 36 e 37', 'Informe a região examinada quando for relevante.'],
        'Ultrassonografia': ['Ex.: glândula parótida direita', 'Informe a região examinada quando for relevante.'],
        'Ressonância': ['Ex.: ATM bilateral', 'Informe a região examinada quando for relevante.'],
        'Fotografia Clínica': ['Ex.: intraoral frontal', 'Você pode indicar o enquadramento ou a região fotografada.'],
        'Outro': ['Descreva a região, se necessário', 'Use este campo apenas quando a localização for importante.'],
    };

    function pluralizeImages(total) {
        return `${total} ${total === 1 ? 'imagem' : 'imagens'}`;
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
        saveButton.disabled = busy || (!examId && (!typeInput.value || selectedFiles.length === 0));
        idleButtonLabel.hidden = busy;
        busyButtonLabel.hidden = !busy;
        dropzone.setAttribute('aria-disabled', busy ? 'true' : 'false');
        form.setAttribute('aria-busy', busy ? 'true' : 'false');
    }

    function returnToExamsTab() {
        allowNavigation = true;
        setBusy(false);
        window.location.assign(returnUrl || app.dataset.createUrl);
    }

    function updateRegionHelp() {
        const [placeholder, hint] = regionRules[typeInput.value] || regionRules.Outro;
        regionInput.placeholder = placeholder;
        regionHint.textContent = hint;
    }

    function updateAction() {
        const total = selectedFiles.length;
        if (examId) {
            idleButtonLabel.textContent = total
                ? `Adicionar ${pluralizeImages(total)}`
                : 'Salvar alterações';
            actionHint.textContent = total
                ? `${pluralizeImages(total)} ${total === 1 ? 'pronta' : 'prontas'} para envio.`
                : 'Escolha imagens para adicionar ou salve alterações nos dados.';
        } else {
            idleButtonLabel.textContent = total
                ? `Salvar exame com ${pluralizeImages(total)}`
                : 'Salvar exame';
            actionHint.textContent = total
                ? 'Tudo pronto. O exame e as imagens serão salvos juntos.'
                : 'Selecione o tipo e pelo menos uma imagem.';
        }
        setBusy(isBusy);
    }

    function fileKey(file) {
        return `${file.name}:${file.size}:${file.lastModified}`;
    }

    function validateFiles(files) {
        const accepted = [];
        const errors = [];
        const existingKeys = new Set(selectedFiles.map((entry) => fileKey(entry.file)));

        for (const file of files) {
            const extensionIsValid = /\.(jpe?g|png|webp)$/i.test(file.name);
            const mimeIsValid = !file.type || file.type.startsWith('image/');

            if (!extensionIsValid || !mimeIsValid) {
                errors.push(`${file.name}: formato não compatível`);
                continue;
            }
            if (file.size > 25 * 1024 * 1024) {
                errors.push(`${file.name}: ultrapassa 25 MB`);
                continue;
            }
            if (existingKeys.has(fileKey(file))) continue;
            if (selectedFiles.length + accepted.length >= 12) {
                errors.push('O limite é de 12 imagens por envio');
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
            const previewUrl = URL.createObjectURL(file);
            objectUrls.add(previewUrl);
            selectedFiles.push({ file, previewUrl });
        });
        fileInput.value = '';
        fileError.textContent = errors.join(' · ');
        renderSelectedFiles();
        if (accepted.length && statusBox.dataset.state === 'error') statusBox.hidden = true;
    }

    function removeSelectedFile(index) {
        const [removed] = selectedFiles.splice(index, 1);
        if (removed) {
            URL.revokeObjectURL(removed.previewUrl);
            objectUrls.delete(removed.previewUrl);
        }
        renderSelectedFiles();
    }

    function clearSelectedFiles({ preserveUrls = new Set() } = {}) {
        selectedFiles.forEach((entry) => {
            if (!preserveUrls.has(entry.previewUrl)) {
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
        selectedCount.textContent = `${pluralizeImages(selectedFiles.length)} ${
            selectedFiles.length === 1 ? 'selecionada' : 'selecionadas'
        }`;

        selectedFiles.forEach((entry, index) => {
            const item = document.createElement('div');
            item.className = 'image-selection-item';

            const image = document.createElement('img');
            image.src = entry.previewUrl;
            image.alt = '';

            const filename = document.createElement('span');
            filename.textContent = entry.file.name;
            filename.title = entry.file.name;

            const removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.setAttribute('aria-label', `Remover ${entry.file.name}`);
            removeButton.textContent = '×';
            removeButton.addEventListener('click', () => removeSelectedFile(index));

            item.append(image, filename, removeButton);
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
        data.append('csrf_token', document.getElementById('csrfToken').value);
        data.append('tipo_imagem', typeInput.value);
        data.append('escopo', form.elements.escopo.value);
        data.append('detalhe_escopo', regionInput.value.trim());
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
        return data;
    }

    function uploadFormData() {
        const data = new FormData();
        selectedFiles.forEach((entry) => data.append('images', entry.file, entry.file.name));
        data.append('csrf_token', document.getElementById('csrfToken').value);

        const optionalFields = [
            'caption',
            'taken_at',
            'visual_category',
            'comparison_label',
            'comparison_group',
            'clinical_context',
        ];
        optionalFields.forEach((name) => {
            const input = form.elements[name];
            if (input) data.append(name, input.value);
        });
        return data;
    }

    function uploadImages() {
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
                    `Enviando ${pluralizeImages(selectedFiles.length)}`,
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
                reject(new Error(data.error || 'Não foi possível enviar as imagens.'));
            });
            xhr.addEventListener('error', () => {
                reject(new Error('A conexão foi interrompida durante o envio. Tente novamente.'));
            });
            xhr.addEventListener('timeout', () => {
                reject(new Error('O envio demorou mais que o esperado. Verifique a galeria antes de tentar novamente.'));
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
        text.textContent = fileData.storage_label || 'Salva no prontuário · aguardando sincronização';
        badge.append(dot, text);
        pollSyncBadge(badge);
        return badge;
    }

    function buildGalleryItem(fileData, previewUrl) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'image-gallery-item';
        button.dataset.imageId = fileData.id;
        button.dataset.imageUrl = previewUrl || fileData.preview_url || fileData.url;
        button.dataset.serverUrl = fileData.preview_url || fileData.url;
        button.dataset.originalUrl = fileData.url;
        button.dataset.imageFilename = fileData.filename;
        button.dataset.imageCaption = fileData.caption || fileData.filename;
        button.dataset.statusUrl = fileData.status_url || '';
        button.setAttribute('aria-label', `Abrir ${fileData.caption || fileData.filename}`);

        const media = document.createElement('span');
        media.className = 'image-gallery-item__media';
        const loading = document.createElement('span');
        loading.className = 'image-gallery-item__loading';
        loading.textContent = 'Carregando…';
        const image = document.createElement('img');
        image.src = previewUrl || fileData.thumbnail_url || fileData.preview_url || fileData.url;
        image.alt = fileData.caption || fileData.filename;
        initializeGalleryImage(image);
        media.append(loading, image);

        const info = document.createElement('span');
        info.className = 'image-gallery-item__info';
        const caption = document.createElement('strong');
        caption.textContent = fileData.caption || fileData.filename;
        const filename = document.createElement('small');
        filename.textContent = fileData.filename;
        info.append(caption, filename, buildSyncBadge(fileData));

        button.append(media, info);
        return button;
    }

    function addSavedFilesToGallery(files) {
        const availablePreviews = new Map();
        selectedFiles.forEach((entry) => {
            const entries = availablePreviews.get(entry.file.name) || [];
            entries.push(entry.previewUrl);
            availablePreviews.set(entry.file.name, entries);
        });

        const savedClientNames = [];
        files.forEach((fileData) => {
            const clientName = fileData.client_filename || fileData.filename;
            const previews = availablePreviews.get(clientName) || [];
            const previewUrl = previews.shift();
            savedClientNames.push(clientName);
            galleryGrid.appendChild(buildGalleryItem(fileData, previewUrl));
        });

        const namesToRemove = new Map();
        savedClientNames.forEach((name) => namesToRemove.set(name, (namesToRemove.get(name) || 0) + 1));
        selectedFiles = selectedFiles.filter((entry) => {
            const count = namesToRemove.get(entry.file.name) || 0;
            if (!count) return true;
            namesToRemove.set(entry.file.name, count - 1);
            return false;
        });

        galleryGrid.hidden = false;
        galleryEmpty.hidden = true;
        galleryCount.textContent = String(galleryGrid.querySelectorAll('.image-gallery-item').length);
        renderSelectedFiles();
    }

    function validateForm() {
        let valid = true;
        typeError.textContent = '';
        fileError.textContent = '';
        typeInput.removeAttribute('aria-invalid');

        if (!typeInput.value) {
            typeError.textContent = 'Selecione o tipo do exame.';
            typeInput.setAttribute('aria-invalid', 'true');
            typeInput.focus();
            valid = false;
        } else if (!examId && selectedFiles.length === 0) {
            fileError.textContent = 'Selecione pelo menos uma imagem.';
            dropzone.focus();
            valid = false;
        }
        return valid;
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
                returnToExamsTab();
                return;
            }

            const result = await uploadImages();
            if (result.partial) {
                if (result.files && result.files.length) addSavedFilesToGallery(result.files);
                showStatus(
                    'warning',
                    'Envio parcialmente concluído',
                    `${result.error} As imagens salvas já aparecem na galeria; tente novamente apenas com as restantes.`,
                );
            } else {
                returnToExamsTab();
                return;
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

    function galleryItems() {
        return Array.from(galleryGrid.querySelectorAll('.image-gallery-item'));
    }

    function openLightbox(index) {
        const items = galleryItems();
        if (!items.length) return;
        currentLightboxIndex = (index + items.length) % items.length;
        const item = items[currentLightboxIndex];
        lightboxImage.src = item.dataset.imageUrl;
        lightboxImage.alt = item.dataset.imageCaption;
        lightboxCaption.textContent = item.dataset.imageCaption;
        lightboxPosition.textContent = `${currentLightboxIndex + 1} de ${items.length}`;
        lightbox.hidden = false;
        document.body.classList.add('image-lightbox-open');
        document.getElementById('closeLightbox').focus();
    }

    function closeLightboxView() {
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
    clearSelectionButton.addEventListener('click', () => clearSelectedFiles());
    typeInput.addEventListener('change', () => {
        typeError.textContent = '';
        typeInput.removeAttribute('aria-invalid');
        updateRegionHelp();
        updateAction();
    });
    form.addEventListener('submit', handleSubmit);
    closeStatus.addEventListener('click', () => {
        if (!isBusy) statusBox.hidden = true;
    });

    galleryGrid.addEventListener('click', (event) => {
        const item = event.target.closest('.image-gallery-item');
        if (!item) return;
        openLightbox(galleryItems().indexOf(item));
    });
    document.getElementById('closeLightbox').addEventListener('click', closeLightboxView);
    document.getElementById('previousImage').addEventListener('click', () => openLightbox(currentLightboxIndex - 1));
    document.getElementById('nextImage').addEventListener('click', () => openLightbox(currentLightboxIndex + 1));
    lightbox.addEventListener('click', (event) => {
        if (event.target === lightbox) closeLightboxView();
    });
    document.addEventListener('keydown', (event) => {
        if (lightbox.hidden) return;
        if (event.key === 'Escape') closeLightboxView();
        if (event.key === 'ArrowLeft') openLightbox(currentLightboxIndex - 1);
        if (event.key === 'ArrowRight') openLightbox(currentLightboxIndex + 1);
    });
    window.addEventListener('beforeunload', (event) => {
        if (!isBusy || allowNavigation) return;
        event.preventDefault();
        event.returnValue = '';
    });
    window.addEventListener('pagehide', () => {
        objectUrls.forEach((url) => URL.revokeObjectURL(url));
    });

    document.querySelectorAll('.image-gallery-item img').forEach(initializeGalleryImage);
    document.querySelectorAll('.file-sync-status').forEach((badge) => pollSyncBadge(badge));
    updateRegionHelp();
    updateAction();
})();
