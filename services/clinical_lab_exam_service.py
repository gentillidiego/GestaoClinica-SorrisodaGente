import os

from werkzeug.utils import secure_filename


CLINICAL_LAB_EXAM_TYPES = {
    'painel_laboratorial': {
        'label': 'Painel laboratorial / múltiplos exames',
        'tests': 'Use quando o mesmo laudo reunir exames de mais de uma categoria.',
    },
    'hemograma_completo': {
        'label': 'Hemograma completo',
        'tests': (
            'Hemácias, hemoglobina, hematócrito, leucócitos com diferencial, '
            'plaquetas, VCM, HCM e RDW.'
        ),
    },
    'coagulacao_hemostasia': {
        'label': 'Coagulação e hemostasia',
        'tests': 'TP/INR, TTPa, fibrinogênio e tempo de sangramento (TS).',
    },
    'glicemia_diabetes': {
        'label': 'Glicemia e diabetes',
        'tests': 'Glicemia de jejum, HbA1c e glicemia pós-prandial.',
    },
    'marcadores_inflamatorios': {
        'label': 'Marcadores inflamatórios',
        'tests': 'PCR ultrassensível, VHS e ferritina.',
    },
    'funcao_renal': {
        'label': 'Função renal',
        'tests': 'Creatinina, ureia e TFG estimada.',
    },
    'funcao_hepatica': {
        'label': 'Função hepática',
        'tests': 'TGO, TGP, GGT, bilirrubinas e fosfatase alcalina.',
    },
    'doencas_transmissiveis': {
        'label': 'Doenças transmissíveis',
        'tests': 'Anti-HIV, HBsAg, Anti-HBs, Anti-HCV e VDRL/FTA-ABS.',
    },
    'tireoide': {
        'label': 'Tireoide',
        'tests': 'TSH, T3, T4 livre e Anti-TPO.',
    },
    'ferro_vitaminas': {
        'label': 'Ferro e vitaminas',
        'tests': (
            'Ferro sérico, ferritina, CTLF, vitamina B12, ácido fólico, '
            'vitamina D.'
        ),
    },
    'perfil_lipidico_cardiovascular': {
        'label': 'Perfil lipídico / cardiovascular',
        'tests': (
            'Colesterol total, LDL, HDL, triglicerídeos, troponina e BNP.'
        ),
    },
}

CLINICAL_LAB_ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}
CLINICAL_LAB_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
CLINICAL_LAB_MAX_FILES = 12
CLINICAL_LAB_MAX_FILE_SIZE = 25 * 1024 * 1024


def get_clinical_lab_exam_label(category):
    item = CLINICAL_LAB_EXAM_TYPES.get(category)
    return item['label'] if item else 'Exame clínico / laboratorial'


def build_clinical_lab_caption(category, filename, supplied_caption=None):
    caption = str(supplied_caption or '').strip()
    return caption or f'{get_clinical_lab_exam_label(category)} — {filename}'


def is_clinical_lab_image(filename, mime_type=None):
    extension = os.path.splitext(str(filename or ''))[1].lower()
    return extension in CLINICAL_LAB_IMAGE_EXTENSIONS or str(mime_type or '').startswith('image/')


def _uploaded_file_size(file):
    declared_size = getattr(file, 'content_length', None)
    if declared_size:
        return declared_size
    try:
        position = file.stream.tell()
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(position)
        return size
    except (AttributeError, OSError):
        return None


def prepare_clinical_lab_uploads(files):
    """Valida o lote inteiro antes de enviar qualquer laudo ao Drive."""
    valid_files = [file for file in files if file and file.filename]
    if not valid_files:
        raise ValueError('Selecione pelo menos um laudo ou imagem.')
    if len(valid_files) > CLINICAL_LAB_MAX_FILES:
        raise ValueError(f'Envie no máximo {CLINICAL_LAB_MAX_FILES} arquivos por vez.')

    prepared = []
    for file in valid_files:
        safe_name = secure_filename(file.filename)
        extension = os.path.splitext(safe_name)[1].lower()
        if extension not in CLINICAL_LAB_ALLOWED_EXTENSIONS:
            raise ValueError(
                f'O arquivo “{file.filename}” não é compatível. '
                'Use PDF, JPG, PNG ou WEBP.'
            )

        mime_type = (file.mimetype or '').lower()
        mime_is_valid = (
            not mime_type
            or mime_type == 'application/octet-stream'
            or mime_type == 'application/pdf'
            or mime_type.startswith('image/')
        )
        if not mime_is_valid:
            raise ValueError(
                f'O arquivo “{file.filename}” não foi reconhecido como PDF ou imagem.'
            )

        size = _uploaded_file_size(file)
        if size is not None and size > CLINICAL_LAB_MAX_FILE_SIZE:
            raise ValueError(f'O arquivo “{file.filename}” ultrapassa o limite de 25 MB.')

        prepared.append((file, safe_name, extension, file.filename))
    return prepared
