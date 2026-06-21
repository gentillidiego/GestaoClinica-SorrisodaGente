import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from PIL import Image
from werkzeug.datastructures import FileStorage

import blueprints.exams as exams_module
import services.upload_security_service as upload_security
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


def make_image(filename='imagem.jpg', content=None, mimetype='image/jpeg', content_length=None):
    if content is None:
        extension = Path(filename).suffix.lower()
        image_format = {
            '.png': 'PNG',
            '.webp': 'WEBP',
        }.get(extension, 'JPEG')
        stream = io.BytesIO()
        Image.new('RGB', (16, 12), color=(20, 80, 140)).save(
            stream,
            format=image_format,
        )
        content = stream.getvalue()
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


def test_image_exam_v2_validates_batch_before_upload(monkeypatch):
    prepared = prepare_image_uploads([
        make_image('foto clínica.JPG'),
        make_image('tomografia.webp', mimetype='image/webp'),
    ])

    assert [item[1] for item in prepared] == ['foto_clinica.jpg', 'tomografia.webp']

    with pytest.raises(ValueError, match='formato permitido'):
        prepare_image_uploads([
            make_image(
                'laudo.pdf',
                content=b'%PDF-1.7 falso',
                mimetype='application/pdf',
            )
        ])

    monkeypatch.setattr(upload_security, 'CLINICAL_UPLOAD_MAX_FILE_BYTES', 32)
    with pytest.raises(ValueError, match='limite operacional'):
        prepare_image_uploads([
            make_image(
                'grande.png',
                content=b'\x89PNG\r\n\x1a\n' + (b'x' * 40),
                mimetype='image/png',
            ),
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
    assert 'if (!isBusy || allowNavigation) return;' in script
    assert "form.dataset.asyncSubmit === 'true'" in validation


def test_exam_card_uses_read_only_viewer_without_manual_validation():
    project_root = Path(__file__).resolve().parents[1]
    tab = (
        project_root / 'templates/patients/includes/_tab_exames.html'
    ).read_text()
    viewer = (project_root / 'templates/exams/viewer.html').read_text()
    viewer_script = (project_root / 'static/js/exam-viewer.js').read_text()

    assert "url_for('exams.visualizar', exam_id=exam.id)" in tab
    assert 'validate_exam' not in tab
    assert 'Aguardando validação clínica' not in tab
    assert 'data-action="zoom-in"' in viewer
    assert 'data-action="move-left"' in viewer
    assert 'data-action="fullscreen"' in viewer
    assert 'requestFullscreen' in viewer_script
    assert "imageLayer.addEventListener('pointermove'" in viewer_script


def test_image_exam_viewer_builds_media_only_context(monkeypatch):
    app = make_app()

    def fake_query(sql, params=(), one=False):
        if 'FROM exams e' in sql:
            return {
                'id': 10,
                'anamnesis_id': 2,
                'patient_id': 9,
                'patient_name': 'Paciente Teste',
                'tipo': 'imagem',
                'resumo_clinico': 'Panorâmica',
            }
        if 'FROM exam_imagem WHERE' in sql:
            return {'tipo_imagem': 'Panorâmica'}
        if 'FROM exam_imagem_arquivos' in sql:
            return [{
                'id': 101,
                'filename': 'panoramica.jpg',
                'caption': 'Panorâmica inicial',
            }]
        raise AssertionError(sql)

    monkeypatch.setattr(exams_module, 'query', fake_query)
    monkeypatch.setattr(exams_module, 'audit_log', lambda **kwargs: None)
    monkeypatch.setattr(
        exams_module,
        'current_user',
        SimpleNamespace(can=lambda permission: permission == 'exams:view'),
    )
    monkeypatch.setattr(
        exams_module,
        'url_for',
        lambda endpoint, **values: (
            f"/{endpoint}/"
            + str(values.get('arquivo_id') or values.get('exam_id') or values.get('id') or '')
        ),
    )
    monkeypatch.setattr(
        exams_module,
        'render_template',
        lambda template, **context: {'template': template, **context},
    )

    with app.test_request_context('/exams/10/visualizar'):
        response = exams_module.visualizar.__wrapped__.__wrapped__(10)

    assert response['template'] == 'exams/viewer.html'
    assert response['exam_title'] == 'Panorâmica'
    assert response['files'][0]['kind'] == 'image'
    assert response['files'][0]['url'] == '/exams.serve_imagem/101'
