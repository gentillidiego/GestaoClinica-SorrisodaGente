(function () {
    const root = document.querySelector('[data-address-widget]');
    if (!root) return;

    const fields = {
        cep: document.getElementById('cep_residencial'),
        state: document.getElementById('endereco_estado'),
        city: document.getElementById('endereco_cidade'),
        neighborhood: document.getElementById('endereco_bairro'),
        street: document.getElementById('endereco_logradouro'),
        number: document.getElementById('endereco_numero'),
        ibge: document.getElementById('endereco_ibge_codigo'),
        consolidated: document.getElementById('endereco_residencial'),
        status: document.getElementById('cep_status'),
        preview: document.getElementById('endereco_preview'),
        neighborhoodList: document.getElementById('endereco_bairro_options'),
    };

    let cepTimer = null;

    function digitsOnly(value) {
        return (value || '').replace(/\D/g, '');
    }

    function formatCep(value) {
        const digits = digitsOnly(value).slice(0, 8);
        if (digits.length > 5) {
            return `${digits.slice(0, 5)}-${digits.slice(5)}`;
        }
        return digits;
    }

    function setStatus(message, tone) {
        if (!fields.status) return;
        fields.status.textContent = message || '';
        const colors = {
            ok: '#166534',
            warn: '#9a3412',
            error: '#991b1b',
            muted: 'hsl(var(--text-muted))',
        };
        fields.status.style.color = colors[tone] || colors.muted;
    }

    function option(value, label, dataset) {
        const item = document.createElement('option');
        item.value = value || '';
        item.textContent = label || value || '';
        if (dataset) {
            Object.entries(dataset).forEach(([key, dataValue]) => {
                item.dataset[key] = dataValue || '';
            });
        }
        return item;
    }

    function selectedCityOption() {
        return fields.city.options[fields.city.selectedIndex];
    }

    function updateIbgeFromCity() {
        const selected = selectedCityOption();
        if (selected && selected.dataset.ibge) {
            fields.ibge.value = selected.dataset.ibge;
        }
    }

    function buildAddress() {
        const parts = [];
        const street = fields.street.value.trim();
        const number = fields.number.value.trim();
        const neighborhood = fields.neighborhood.value.trim();
        const city = fields.city.value.trim();
        const state = fields.state.value.trim();
        const cep = formatCep(fields.cep.value);

        if (street && number) {
            parts.push(`${street}, ${number}`);
        } else if (street) {
            parts.push(street);
        } else if (number) {
            parts.push(`Nº ${number}`);
        }
        if (neighborhood) parts.push(neighborhood);
        if (city && state) {
            parts.push(`${city} - ${state}`);
        } else if (city) {
            parts.push(city);
        } else if (state) {
            parts.push(state);
        }
        if (cep) parts.push(`CEP ${cep}`);

        const consolidated = parts.join(', ');
        fields.consolidated.value = consolidated;
        fields.preview.textContent = consolidated ? `Endereço: ${consolidated}` : '';
    }

    async function fetchJson(url) {
        const response = await fetch(url, { headers: { Accept: 'application/json' } });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.error || 'Falha ao carregar dados.');
        }
        return payload;
    }

    async function loadCities(uf, selectedCity) {
        const current = selectedCity || fields.city.dataset.currentCity || fields.city.value;
        fields.city.innerHTML = '';
        fields.city.appendChild(option('', 'Selecione a cidade'));
        fields.city.disabled = true;

        if (!uf) {
            fields.city.disabled = false;
            return;
        }

        try {
            const url = `${root.dataset.citiesUrl}?uf=${encodeURIComponent(uf)}`;
            const cities = await fetchJson(url);
            cities.forEach((city) => {
                fields.city.appendChild(option(city.nome, city.nome, { ibge: city.ibge_codigo }));
            });
            if (current && !cities.some((city) => city.nome === current)) {
                fields.city.appendChild(option(current, current));
            }
            fields.city.value = current || '';
            updateIbgeFromCity();
        } catch (error) {
            if (current) {
                fields.city.appendChild(option(current, current));
                fields.city.value = current;
            }
            setStatus('Não foi possível carregar cidades. Preencha manualmente.', 'warn');
        } finally {
            fields.city.disabled = false;
            fields.city.dataset.currentCity = '';
            loadNeighborhoods();
            buildAddress();
        }
    }

    async function loadNeighborhoods() {
        fields.neighborhoodList.innerHTML = '';
        const uf = fields.state.value;
        const city = fields.city.value;
        if (!city) return;

        try {
            const url = `${root.dataset.neighborhoodsUrl}?uf=${encodeURIComponent(uf)}&city=${encodeURIComponent(city)}`;
            const neighborhoods = await fetchJson(url);
            neighborhoods.forEach((name) => fields.neighborhoodList.appendChild(option(name, name)));
        } catch (error) {
            fields.neighborhoodList.innerHTML = '';
        }
    }

    function applyCep(payload) {
        fields.cep.value = formatCep(payload.cep || fields.cep.value);
        fields.state.value = payload.estado || fields.state.value || 'AL';
        fields.street.value = payload.logradouro || fields.street.value;
        fields.neighborhood.value = payload.bairro || fields.neighborhood.value;
        fields.ibge.value = payload.ibge_codigo || fields.ibge.value;

        loadCities(fields.state.value, payload.cidade).then(() => {
            if (payload.cidade) fields.city.value = payload.cidade;
            if (payload.ibge_codigo) fields.ibge.value = payload.ibge_codigo;
            loadNeighborhoods();
            buildAddress();
            fields.number.focus();
        });
        setStatus('CEP encontrado.', 'ok');
    }

    async function lookupCep() {
        const digits = digitsOnly(fields.cep.value);
        if (digits.length < 8) {
            setStatus('', 'muted');
            buildAddress();
            return;
        }

        setStatus('Buscando CEP...', 'muted');
        const url = root.dataset.cepUrlTemplate.replace('__CEP__', digits);
        try {
            const payload = await fetchJson(url);
            applyCep(payload);
        } catch (error) {
            setStatus('CEP não encontrado. Preencha o endereço manualmente.', 'warn');
            buildAddress();
        }
    }

    fields.cep.addEventListener('input', () => {
        fields.cep.value = formatCep(fields.cep.value);
        clearTimeout(cepTimer);
        cepTimer = setTimeout(lookupCep, 450);
        buildAddress();
    });
    fields.state.addEventListener('change', () => {
        fields.city.dataset.currentCity = '';
        fields.city.value = '';
        fields.neighborhood.value = '';
        loadCities(fields.state.value, '');
    });
    fields.city.addEventListener('change', () => {
        updateIbgeFromCity();
        loadNeighborhoods();
        buildAddress();
    });
    [fields.neighborhood, fields.street, fields.number].forEach((field) => {
        field.addEventListener('input', buildAddress);
    });

    fields.cep.value = formatCep(fields.cep.value);
    if (fields.state.value) {
        loadCities(fields.state.value, fields.city.dataset.currentCity || fields.city.value);
    }
    loadNeighborhoods();
    buildAddress();
})();
