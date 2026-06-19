import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.datastructures import FileStorage

import blueprints.exams as exams_module
from blueprints.exams import (
    build_image_upload_caption,
    exams_bp,
    infer_image_exam_scope,
    infer_image_visual_category,
    prepare_image_uploads,
)


def make_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test-secret', TESTING=True)
    app.register_blueprint(exams_bp)
    return app


def make_image(filename='imagem.jpg', content=b'image', mimetype='image/jpeg', content_length=None):
    return FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
        content_type=mimetype,
        content_length=content_length,
    )


@pytest.mark.parametrize(
    ('exam_type', 'scope', 'category'),
    [
        ('Periapical', 'Elemento', 'radiografia'),
        ('Bite-wing', 'Quadrante', 'radiografia'),
        ('Oclusal', 'Arcada', 'radiografia'),
        ('Panorâmica', 'Complexo Maxilomandibular', 'radiografia'),
        ('Tomografia', 'Complexo Maxilomandibular', 'cbct'),
        ('Fotografia Clínica', 'Outro', 'intraoral'),
        ('Outro', 'Outro', 'documento_complementar'),
    ],
)
def test_image_exam_v2_infers_hidden_clinical_metadata(exam_type, scope, category):
    assert infer_image_exam_scope(exam_type) == scope
    assert infer_image_visual_category(exam_type) == category


def test_image_exam_v2_generates_caption_only_when_user_leaves_it_empty():
    assert (
        build_image_upload_caption('Panorâmica', 'panoramica.jpg')
        == 'Panorâmica — panoramica.jpg'
    )
    assert (
        build_image_upload_caption('Panorâmica', 'panoramica.jpg', '  Inicial  ')
        == 'Inicial'
    )


def test_image_exam_v2_validates_batch_before_upload():
    prepared = prepare_image_uploads([
        make_image('foto clínica.JPG'),
        make_image('tomografia.webp', mimetype='image/webp'),
    ])

    assert [item[1] for item in prepared] == ['foto_clinica.JPG', 'tomografia.webp']

    with pytest.raises(ValueError, match='não é compatível'):
        prepare_image_uploads([make_image('laudo.pdf', mimetype='application/pdf')])

    with pytest.raises(ValueError, match='ultrapassa o limite'):
        prepare_image_uploads([
            make_image('grande.png', mimetype='image/png', content_length=25 * 1024 * 1024 + 1),
        ])


def test_image_exam_v2_create_requires_only_type_and_infers_scope(monkeypatch):
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
            return 77
        return None

    monkeypatch.setattr(exams_module, 'execute', fake_execute)

    with app.test_request_context(
        '/exams/imagem/2',
        method='POST',
        data={'tipo_imagem': 'Panorâmica', 'detalhe_escopo': '', 'observacoes': ''},
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
    ):
        response = exams_module.imagem.__wrapped__(2)

    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['exam_id'] == 77
    assert executed[1][1] == (77, 'Panorâmica', 'Complexo Maxilomandibular', '', '')


def test_image_exam_v2_upload_stages_locally_and_queues_drive_sync(monkeypatch):
    app = make_app()
    inserted = {}
    queued = []

    monkeypatch.setattr(
        exams_module,
        'query',
        lambda sql, params=(), one=False: {
            'id': 77,
            'patient_id': 9,
            'tipo_imagem': 'Tomografia',
        },
    )
    monkeypatch.setattr(
        exams_module,
        'stage_uploaded_file',
        lambda *args: 'uploads/staging/exams/exam_image/image-101.png',
    )
    monkeypatch.setattr(
        exams_module,
        'enqueue_exam_file_sync',
        lambda source, record_id: queued.append((source, record_id)),
    )

    def fake_execute(sql, params=()):
        if 'INSERT INTO exam_imagem_arquivos' in sql:
            inserted['params'] = params
            return 101
        return None

    monkeypatch.setattr(exams_module, 'execute', fake_execute)
    monkeypatch.setattr(exams_module, 'audit_log', lambda **kwargs: None)
    monkeypatch.setattr(exams_module, 'current_user', SimpleNamespace(id=5))

    with app.test_request_context(
        '/exams/imagem/77/upload',
        method='POST',
        data={'images': make_image('corte 01.png', mimetype='image/png')},
    ):
        response = exams_module.upload_imagem.__wrapped__(77)

    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['total'] == 1
    assert payload['files'][0]['caption'] == 'Tomografia — corte_01.png'
    assert payload['files'][0]['storage_status'] == 'pending'
    assert payload['files'][0]['status_url'].endswith('/imagem/arquivo/101/status')
    assert inserted['params'][3] == 'uploads/staging/exams/exam_image/image-101.png'
    assert inserted['params'][4] == 'cbct'
    assert inserted['params'][5] == 'Tomografia — corte_01.png'
    assert inserted['params'][11] == 'uploads/staging/exams/exam_image/image-101.png'
    assert queued == [('exam_image', 101)]


def test_image_exam_async_form_returns_to_exams_tab_without_global_spinner():
    project_root = Path(__file__).resolve().parents[1]
    template = (project_root / 'templates/exams/imagem.html').read_text()
    script = (project_root / 'static/js/exam-image-v2.js').read_text()
    validation = (project_root / 'static/js/validation.js').read_text()

    assert 'data-async-submit="true"' in template
    assert "_anchor='tab-exames'" in template
    assert 'window.location.assign(returnUrl || app.dataset.createUrl)' in script
    assert "form.dataset.asyncSubmit === 'true'" in validation
