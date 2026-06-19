import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.datastructures import FileStorage

import blueprints.exams as exams_module
from blueprints.exams import exams_bp
from services.clinical_lab_exam_service import (
    CLINICAL_LAB_EXAM_TYPES,
    build_clinical_lab_caption,
    get_clinical_lab_exam_label,
    is_clinical_lab_image,
    prepare_clinical_lab_uploads,
)


def make_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test-secret', TESTING=True)
    app.register_blueprint(exams_bp)
    return app


def make_file(
    filename='laudo.pdf',
    content=b'%PDF-1.7 test',
    mimetype='application/pdf',
    content_length=None,
):
    return FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
        content_type=mimetype,
        content_length=content_length,
    )


def test_clinical_lab_catalog_contains_requested_odontology_groups():
    expected = {
        'hemograma_completo',
        'coagulacao_hemostasia',
        'glicemia_diabetes',
        'marcadores_inflamatorios',
        'funcao_renal',
        'funcao_hepatica',
        'doencas_transmissiveis',
        'tireoide',
        'ferro_vitaminas',
        'perfil_lipidico_cardiovascular',
    }

    assert expected.issubset(CLINICAL_LAB_EXAM_TYPES)
    assert 'TP/INR' in CLINICAL_LAB_EXAM_TYPES['coagulacao_hemostasia']['tests']
    assert 'HbA1c' in CLINICAL_LAB_EXAM_TYPES['glicemia_diabetes']['tests']


def test_clinical_lab_upload_accepts_pdf_and_images_only():
    prepared = prepare_clinical_lab_uploads([
        make_file('laudo sangue.pdf'),
        make_file('foto resultado.PNG', content=b'png', mimetype='image/png'),
    ])

    assert [item[1] for item in prepared] == ['laudo_sangue.pdf', 'foto_resultado.PNG']

    with pytest.raises(ValueError, match='não é compatível'):
        prepare_clinical_lab_uploads([
            make_file('resultado.docx', mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
        ])

    with pytest.raises(ValueError, match='ultrapassa o limite'):
        prepare_clinical_lab_uploads([
            make_file('grande.pdf', content_length=25 * 1024 * 1024 + 1),
        ])


def test_clinical_lab_caption_and_preview_type_are_automatic():
    assert get_clinical_lab_exam_label('funcao_renal') == 'Função renal'
    assert (
        build_clinical_lab_caption('funcao_renal', 'creatinina.pdf')
        == 'Função renal — creatinina.pdf'
    )
    assert is_clinical_lab_image('resultado.webp', 'image/webp') is True
    assert is_clinical_lab_image('resultado.pdf', 'application/pdf') is False


def test_clinical_lab_create_requires_only_category(monkeypatch):
    app = make_app()
    executed = []

    monkeypatch.setattr(
        exams_module,
        'query',
        lambda sql, params=(), one=False: {
            'id': 2,
            'patient_id': 9,
            'patient_name': 'Paciente Teste',
        },
    )

    def fake_execute(sql, params=()):
        executed.append((sql, params))
        if 'INSERT INTO exams' in sql:
            return 88
        return None

    monkeypatch.setattr(exams_module, 'execute', fake_execute)

    with app.test_request_context(
        '/exams/clinico-laboratorial/2',
        method='POST',
        data={'categoria': 'hemograma_completo'},
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
    ):
        response = exams_module.clinico_laboratorial.__wrapped__(2)

    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['exam_id'] == 88
    assert executed[0][1] == (
        2,
        9,
        'clinico_laboratorial',
        'Hemograma completo',
    )
    assert executed[1][1] == (88, 'hemograma_completo', '', '', '')


def test_clinical_lab_pdf_upload_stages_locally_and_queues_drive_sync(monkeypatch):
    app = make_app()
    inserted = {}
    queued = []

    monkeypatch.setattr(
        exams_module,
        'query',
        lambda sql, params=(), one=False: {
            'id': 88,
            'patient_id': 9,
            'categoria': 'hemograma_completo',
        },
    )
    monkeypatch.setattr(
        exams_module,
        'stage_uploaded_file',
        lambda *args: 'uploads/staging/exams/clinical_lab/laudo-301.pdf',
    )
    monkeypatch.setattr(
        exams_module,
        'enqueue_exam_file_sync',
        lambda source, record_id: queued.append((source, record_id)),
    )

    def fake_execute(sql, params=()):
        if 'INSERT INTO exam_clinico_laboratorial_arquivos' in sql:
            inserted['params'] = params
            return 301
        return None

    monkeypatch.setattr(exams_module, 'execute', fake_execute)
    monkeypatch.setattr(exams_module, 'audit_log', lambda **kwargs: None)
    monkeypatch.setattr(exams_module, 'current_user', SimpleNamespace(id=5))

    with app.test_request_context(
        '/exams/clinico-laboratorial/88/upload',
        method='POST',
        data={'files': make_file('hemograma junho.pdf')},
    ):
        response = exams_module.upload_clinico_laboratorial.__wrapped__(88)

    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['files'][0]['is_image'] is False
    assert payload['files'][0]['caption'] == 'Hemograma completo — hemograma_junho.pdf'
    assert payload['files'][0]['storage_status'] == 'pending'
    assert payload['files'][0]['status_url'].endswith(
        '/clinico-laboratorial/arquivo/301/status'
    )
    assert inserted['params'][3] == 'uploads/staging/exams/clinical_lab/laudo-301.pdf'
    assert inserted['params'][4] == 'application/pdf'
    assert inserted['params'][7] == 'uploads/staging/exams/clinical_lab/laudo-301.pdf'
    assert queued == [('clinical_lab', 301)]


def test_clinical_lab_async_form_returns_to_exams_tab():
    project_root = Path(__file__).resolve().parents[1]
    template = (
        project_root / 'templates/exams/clinico_laboratorial.html'
    ).read_text()
    script = (project_root / 'static/js/clinical-lab-exam.js').read_text()

    assert 'data-async-submit="true"' in template
    assert "_anchor='tab-exames'" in template
    assert 'window.location.assign(returnUrl || app.dataset.createUrl)' in script
