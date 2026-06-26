import os

from services.upload_security_service import (
    CLINICAL_LAB_FORMATS,
    UploadValidationError,
    inspect_uploaded_file,
)


CLINICAL_LAB_EXAM_TYPES = {
    'hemograma_completo': {
        'label': 'Hemograma completo',
        'tests': (
            'Hemácias, hemoglobina, hematócrito, leucócitos com diferencial, '
            'plaquetas, VCM, HCM e RDW.'
        ),
    },
    'glicemia_diabetes': {
        'label': 'Glicemia e diabetes',
        'tests': 'Glicemia de jejum, HbA1c e glicemia pós-prandial.',
    },
    'funcao_renal': {
        'label': 'Função renal',
        'tests': 'Creatinina, ureia e TFG estimada.',
    },
    'perfil_lipidico_cardiovascular': {
        'label': 'Perfil lipídico / cardiovascular',
        'tests': (
            'Colesterol total, LDL, HDL, triglicerídeos, troponina e BNP.'
        ),
    },
}

# Código(s) SIGTAP por categoria — usado para creditar automaticamente a
# produtividade do clínico solicitante ao atender a solicitação de exame
# (services/exam_productivity_service.py). O SIGTAP fatura por teste
# individual, não por "painel"; por isso algumas categorias mapeiam para
# mais de um código (ex.: Função renal = creatinina + ureia).
CLINICAL_LAB_SIGTAP_CODES = {
    'hemograma_completo': ('0202010503',),
    'glicemia_diabetes': ('0202010473',),
    'funcao_renal': ('0202010317', '0202010694'),
    'perfil_lipidico_cardiovascular': ('0202010295', '0202010643'),
}

CLINICAL_LAB_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
CLINICAL_LAB_MAX_FILES = 12


def get_clinical_lab_exam_label(category):
    item = CLINICAL_LAB_EXAM_TYPES.get(category)
    return item['label'] if item else 'Exame clínico / laboratorial'


def build_clinical_lab_caption(category, filename, supplied_caption=None):
    caption = str(supplied_caption or '').strip()
    return caption or f'{get_clinical_lab_exam_label(category)} — {filename}'


def is_clinical_lab_image(filename, mime_type=None):
    extension = os.path.splitext(str(filename or ''))[1].lower()
    return extension in CLINICAL_LAB_IMAGE_EXTENSIONS or str(mime_type or '').startswith('image/')


def prepare_clinical_lab_uploads(files):
    """Inspeciona o lote inteiro antes de gravar qualquer laudo."""
    valid_files = [file for file in files if file and file.filename]
    if not valid_files:
        raise ValueError('Selecione pelo menos um laudo ou imagem.')
    if len(valid_files) > CLINICAL_LAB_MAX_FILES:
        raise ValueError(f'Envie no máximo {CLINICAL_LAB_MAX_FILES} arquivos por vez.')

    prepared = []
    for file in valid_files:
        try:
            inspection = inspect_uploaded_file(
                file,
                allowed_formats=CLINICAL_LAB_FORMATS,
            )
        except UploadValidationError as exc:
            raise ValueError(str(exc)) from exc
        prepared.append(
            (
                file,
                inspection.safe_filename,
                inspection.extension,
                file.filename,
                inspection,
            )
        )
    return prepared
