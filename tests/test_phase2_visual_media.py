import datetime as dt

import services.visual_media_service as visual_media_service
from services.visual_media_service import (
    build_comparison_groups,
    get_patient_visual_media_summary,
    normalize_comparison_label,
    normalize_visual_category,
    update_exam_image_metadata,
)


def test_visual_media_normalizes_categories_and_comparison_labels():
    assert normalize_visual_category('Radiografias') == 'radiografia'
    assert normalize_visual_category('Antes Depois') == 'antes_depois'
    assert normalize_visual_category('valor desconhecido') == 'radiografia'

    assert normalize_comparison_label('Pré') == 'antes'
    assert normalize_comparison_label('Pós-operatório') == 'pos_operatorio'
    assert normalize_comparison_label('inexistente') == 'diagnostico'


def test_visual_media_summary_merges_exam_images_and_lesion_photos(monkeypatch):
    def fake_query(sql, params=(), one=False):
        assert params == (42,)
        if 'FROM exam_imagem_arquivos' in sql:
            return [{
                'source_type': 'exam_image',
                'source_id': 10,
                'exam_id': 7,
                'patient_id': 42,
                'filename': 'panoramica.jpg',
                'file_path': 'uploads/exames/panoramica.jpg',
                'visual_category': 'radiografia',
                'caption': 'Panorâmica inicial',
                'clinical_context': 'Diagnóstico inicial',
                'comparison_label': 'diagnostico',
                'comparison_group': 'Caso 42',
                'taken_at': dt.datetime(2026, 6, 1, 9, 0),
                'uploaded_at': dt.datetime(2026, 6, 1, 9, 5),
            }]
        if 'FROM estomatologia_fotos' in sql:
            return [{
                'source_type': 'estomatologia_photo',
                'source_id': 11,
                'patient_id': 42,
                'estomatologia_id': 5,
                'filename': 'lesao.jpg',
                'file_path': 'uploads/estomatologia/lesao.jpg',
                'visual_category': 'lesao',
                'caption': 'Lesão antes',
                'clinical_context': None,
                'comparison_label': 'antes',
                'comparison_group': 'Caso 42',
                'taken_at': dt.datetime(2026, 5, 30, 8, 0),
                'uploaded_at': dt.datetime(2026, 5, 30, 8, 5),
            }]
        return []

    monkeypatch.setattr(visual_media_service, 'query', fake_query)

    summary = get_patient_visual_media_summary(42)

    assert summary['visual_stats']['total'] == 2
    assert summary['visual_stats']['radiografias'] == 1
    assert summary['visual_stats']['lesoes'] == 1
    assert summary['visual_stats']['comparativos'] == 1
    assert [group['slug'] for group in summary['visual_groups']] == ['radiografia', 'lesao']
    assert summary['visual_comparisons'][0]['title'] == 'Caso 42'


def test_comparison_groups_require_same_group_and_order_by_visual_stage():
    items = [
        {'comparison_group': 'Lesão A', 'comparison_label': 'depois', 'taken_at': dt.datetime(2026, 6, 20)},
        {'comparison_group': 'Lesão A', 'comparison_label': 'antes', 'taken_at': dt.datetime(2026, 6, 1)},
        {'comparison_group': None, 'comparison_label': 'antes', 'taken_at': dt.datetime(2026, 6, 1)},
    ]

    groups = build_comparison_groups(items)

    assert len(groups) == 1
    assert [item['comparison_label'] for item in groups[0]['items']] == ['antes', 'depois']


def test_update_exam_image_metadata_validates_patient_and_persists(monkeypatch):
    executed = {}

    def fake_query(sql, params=(), one=False):
        assert params == (99, 42)
        assert one is True
        return {'id': 99, 'exam_id': 5, 'patient_id': 42}

    def fake_execute(sql, params=()):
        executed['sql'] = sql
        executed['params'] = params

    monkeypatch.setattr(visual_media_service, 'query', fake_query)
    monkeypatch.setattr(visual_media_service, 'execute', fake_execute)

    record = update_exam_image_metadata(99, 42, {
        'visual_category': 'intraoral',
        'caption': 'Foto intraoral inicial',
        'clinical_context': 'Primeira consulta',
        'comparison_label': 'antes',
        'comparison_group': 'Sorriso inicial',
        'taken_at': '2026-06-03T10:00',
    })

    assert record['patient_id'] == 42
    assert executed['params'] == (
        'intraoral',
        'Foto intraoral inicial',
        'Primeira consulta',
        'antes',
        'Sorriso inicial',
        '2026-06-03T10:00',
        99,
    )
