/**
 * Centralize form validations and masks
 */

document.addEventListener('DOMContentLoaded', () => {
    initMasks();
    initFormListeners();
});

/**
 * Initialize Input Masks using IMask.js
 */
function initMasks() {
    // CPF Mask: 000.000.000-00
    const cpfElements = document.querySelectorAll('input[name="cpf"], #cpf');
    cpfElements.forEach(el => {
        IMask(el, { mask: '000.000.000-00' });
    });

    // Celular Mask: (00) 00000-0000
    const phoneElements = document.querySelectorAll('input[name="celular"], #celular');
    phoneElements.forEach(el => {
        IMask(el, { mask: '(00) 00000-0000' });
    });

    // CNS Mask: 000.0000.0000.0000
    const cnsElements = document.querySelectorAll('input[name="cns"], #cns');
    cnsElements.forEach(el => {
        IMask(el, { mask: '000.0000.0000.0000' });
    });
}

/**
 * Initialize common form behaviors
 */
function initFormListeners() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            // Formulários assíncronos controlam o próprio estado e o próprio
            // redirecionamento. Não substituir o botão desses fluxos.
            if (form.dataset.asyncSubmit === 'true') {
                return;
            }

            // Validate CPF if present
            const cpfInput = form.querySelector('input[name="cpf"], #cpf');
            if (cpfInput && cpfInput.value) {
                const rawCpf = cpfInput.value.replace(/\D/g, '');
                if (rawCpf.length > 0 && !validateCPF(rawCpf)) {
                    alert('CPF inválido. Por favor, verifique os números digitados.');
                    e.preventDefault();
                    return;
                }
            }

            // Validate Date of Birth if present
            const dobInput = form.querySelector('input[type="date"][name="data_nascimento"]');
            if (dobInput && dobInput.value) {
                const selectedDate = new Date(dobInput.value);
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                if (selectedDate > today) {
                    alert('A data de nascimento não pode estar no futuro.');
                    e.preventDefault();
                    return;
                }
            }

            // Visual feedback on submit
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                // Prevent multiple clicks
                setTimeout(() => {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = `<span class="spinner-inline"></span> Salvando...`;
                }, 10);
            }
        });
    });
}

/**
 * CPF Validation Algorithm
 */
function validateCPF(cpf) {
    if (cpf.length !== 11 || /^(\d)\1+$/.test(cpf)) return false;
    let sum = 0, rev;
    for (let i = 0; i < 9; i++) sum += parseInt(cpf.charAt(i)) * (10 - i);
    rev = 11 - (sum % 11);
    if (rev === 10 || rev === 11) rev = 0;
    if (rev !== parseInt(cpf.charAt(9))) return false;
    sum = 0;
    for (let i = 0; i < 10; i++) sum += parseInt(cpf.charAt(i)) * (11 - i);
    rev = 11 - (sum % 11);
    if (rev === 10 || rev === 11) rev = 0;
    if (rev !== parseInt(cpf.charAt(10))) return false;
    return true;
}
