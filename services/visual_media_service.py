import datetime as dt
import unicodedata

from database import execute, query


VISUAL_CATEGORIES = [
    ('radiografia', 'Radiografia'),
    ('lesao', 'Lesão'),
    ('antes_depois', 'Antes/Depois'),
    ('evolucao', 'Evolução'),
    ('intraoral', 'Intraoral'),
    ('extraoral', 'Extraoral'),
    ('documento_complementar', 'Documento complementar'),
]

COMPARISON_LABELS = [
    ('diagnostico', 'Diagnóstico'),
    ('antes', 'Antes'),
    ('depois', 'Depois'),
    ('evolucao', 'Evolução'),
    ('controle', 'Controle'),
    ('pos_operatorio', 'Pós-operatório'),
    ('retorno', 'Retorno'),
]

_CATEGORY_ALIASES = {
    'radiografias': 'radiografia',
    'raio_x': 'radiografia',
    'raiox': 'radiografia',
    'lesoes': 'lesao',
    'lesao_bucal': 'lesao',
    'antesdepois': 'antes_depois',
    'antes_depois': 'antes_depois',
    'antes depois': 'antes_depois',
    'documento': 'documento_complementar',
    'documentos': 'documento_complementar',
}

_COMPARISON_ALIASES = {
    'pre': 'antes',
    'pré': 'antes',
    'pre_operatorio': 'antes',
    'pos': 'depois',
    'pós': 'depois',
    'pos_operatorio': 'pos_operatorio',
    'pós_operatorio': 'pos_operatorio',
    'diagnóstico': 'diagnostico',
}

_CATEGORY_LABELS = dict(VISUAL_CATEGORIES)
_COMPARISON_LABELS = dict(COMPARISON_LABELS)
_COMPARISON_ORDER = {
    'diagnostico': 0,
    'antes': 1,
    'evolucao': 2,
    'controle': 3,
    'retorno': 4,
    'pos_operatorio': 5,
    'depois': 6,
}


def _slug(value):
    text = str(value or '').strip().lower()
    normalized = unicodedata.normalize('NFKD', text)
    ascii_text = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    cleaned = []
    previous_separator = False
    for ch in ascii_text:
        if ch.isalnum():
            cleaned.append(ch)
            previous_separator = False
        elif not previous_separator:
            cleaned.append('_')
            previous_separator = True
    return ''.join(cleaned).strip('_')


def _clean_text(value):
    text = str(value or '').strip()
    return text or None


def _as_datetime(value):
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    if not value:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y'):
            try:
                return dt.datetime.strptime(text, fmt)
            except ValueError:
                continue
        try:
            return dt.datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _format_datetime_input(value):
    parsed = _as_datetime(value)
    return parsed.strftime('%Y-%m-%dT%H:%M') if parsed else ''


def _format_datetime_display(value):
    parsed = _as_datetime(value)
    return parsed.strftime('%d/%m/%Y %H:%M') if parsed else 'Sem data'


def normalize_visual_category(value, default='radiografia'):
    slug = _slug(value)
    slug = _CATEGORY_ALIASES.get(slug, slug)
    valid = {key for key, _label in VISUAL_CATEGORIES}
    return slug if slug in valid else default


def normalize_comparison_label(value, default='diagnostico'):
    slug = _slug(value)
    slug = _COMPARISON_ALIASES.get(slug, slug)
    valid = {key for key, _label in COMPARISON_LABELS}
    return slug if slug in valid else default


def get_visual_category_options():
    return VISUAL_CATEGORIES


def get_comparison_label_options():
    return COMPARISON_LABELS


def _metadata_from_form(form_data, category_default, comparison_default):
    category = normalize_visual_category(form_data.get('visual_category'), category_default)
    comparison_label = normalize_comparison_label(
        form_data.get('comparison_label'),
        comparison_default,
    )
    caption = _clean_text(form_data.get('caption') or form_data.get('legenda'))
    return {
        'visual_category': category,
        'caption': caption,
        'clinical_context': _clean_text(form_data.get('clinical_context')),
        'comparison_label': comparison_label,
        'comparison_group': _clean_text(form_data.get('comparison_group')),
        'taken_at': _clean_text(form_data.get('taken_at')),
    }


def build_exam_image_metadata(form_data):
    return _metadata_from_form(form_data, 'radiografia', 'diagnostico')


def build_estomatologia_photo_metadata(form_data):
    metadata = _metadata_from_form(form_data, 'lesao', 'evolucao')
    metadata['legenda'] = metadata['caption']
    return metadata


def _decorate_item(raw_item):
    item = dict(raw_item)
    category = normalize_visual_category(
        item.get('visual_category'),
        'lesao' if item.get('source_type') == 'estomatologia_photo' else 'radiografia',
    )
    comparison = normalize_comparison_label(
        item.get('comparison_label'),
        'evolucao' if item.get('source_type') == 'estomatologia_photo' else 'diagnostico',
    )
    item['visual_category'] = category
    item['visual_category_label'] = _CATEGORY_LABELS[category]
    item['comparison_label'] = comparison
    item['comparison_label_text'] = _COMPARISON_LABELS[comparison]
    item['caption'] = _clean_text(item.get('caption')) or item.get('filename') or 'Imagem clínica'
    item['comparison_group'] = _clean_text(item.get('comparison_group'))
    item['clinical_context'] = _clean_text(item.get('clinical_context'))
    item['taken_at_input'] = _format_datetime_input(item.get('taken_at') or item.get('uploaded_at'))
    item['taken_at_display'] = _format_datetime_display(item.get('taken_at') or item.get('uploaded_at'))
    item['source_label'] = (
        'Estomatologia'
        if item.get('source_type') == 'estomatologia_photo'
        else 'Exame de imagem'
    )
    return item


def list_patient_visual_media(patient_id):
    exam_images = query(
        """
        SELECT
            'exam_image' AS source_type,
            a.id AS source_id,
            a.exam_id,
            e.patient_id,
            a.filename,
            a.file_path,
            a.visual_category,
            a.caption,
            a.clinical_context,
            a.comparison_label,
            a.comparison_group,
            COALESCE(a.taken_at, a.data_upload) AS taken_at,
            a.data_upload AS uploaded_at,
            a.uploaded_by,
            u.username AS uploaded_by_username,
            u.full_name AS uploaded_by_full_name,
            e.tipo AS exam_type,
            e.resumo_clinico,
            i.tipo_imagem,
            i.escopo,
            i.detalhe_escopo
        FROM exam_imagem_arquivos a
        JOIN exams e ON e.id = a.exam_id
        LEFT JOIN exam_imagem i ON i.exam_id = e.id
        LEFT JOIN users u ON u.id = a.uploaded_by
        WHERE e.patient_id = %s
          AND COALESCE(a.active, TRUE) = TRUE
        """,
        (patient_id,),
    )
    lesion_photos = query(
        """
        SELECT
            'estomatologia_photo' AS source_type,
            f.id AS source_id,
            e.patient_id,
            f.estomatologia_id,
            f.filename,
            f.file_path,
            f.visual_category,
            COALESCE(NULLIF(f.legenda, ''), f.filename) AS caption,
            f.clinical_context,
            f.comparison_label,
            f.comparison_group,
            COALESCE(f.taken_at, f.data_upload) AS taken_at,
            f.data_upload AS uploaded_at,
            f.uploaded_by,
            u.username AS uploaded_by_username,
            u.full_name AS uploaded_by_full_name,
            e.localizacao_lesao,
            e.tamanho_lesao,
            e.suspeita_neoplasia,
            e.cancer_confirmed
        FROM estomatologia_fotos f
        JOIN estomatologia e ON e.id = f.estomatologia_id
        LEFT JOIN users u ON u.id = f.uploaded_by
        WHERE e.patient_id = %s
          AND COALESCE(f.active, TRUE) = TRUE
        """,
        (patient_id,),
    )

    items = [_decorate_item(row) for row in [*exam_images, *lesion_photos]]
    return sorted(
        items,
        key=lambda item: _as_datetime(item.get('taken_at')) or dt.datetime.min,
        reverse=True,
    )


def group_visual_media_by_category(items):
    groups = {
        key: {'slug': key, 'label': label, 'count': 0, 'items': []}
        for key, label in VISUAL_CATEGORIES
    }
    for item in items:
        group = groups[item['visual_category']]
        group['items'].append(item)
        group['count'] += 1
    return [group for group in groups.values() if group['count']]


def build_comparison_groups(items):
    grouped = {}
    for item in items:
        group_key = item.get('comparison_group')
        if not group_key:
            continue
        grouped.setdefault(group_key.strip().lower(), {
            'title': group_key.strip(),
            'items': [],
        })['items'].append(item)

    comparisons = []
    for group in grouped.values():
        group['items'].sort(
            key=lambda item: (
                _COMPARISON_ORDER.get(item.get('comparison_label'), 99),
                _as_datetime(item.get('taken_at')) or dt.datetime.min,
            )
        )
        if len(group['items']) >= 2:
            comparisons.append(group)
    return comparisons


def get_patient_visual_media_summary(patient_id):
    items = list_patient_visual_media(patient_id)
    stats = {
        'total': len(items),
        'radiografias': sum(1 for item in items if item['visual_category'] == 'radiografia'),
        'lesoes': sum(1 for item in items if item['visual_category'] == 'lesao'),
        'comparativos': len(build_comparison_groups(items)),
    }
    return {
        'visual_items': items,
        'visual_groups': group_visual_media_by_category(items),
        'visual_comparisons': build_comparison_groups(items),
        'visual_stats': stats,
        'visual_category_options': get_visual_category_options(),
        'visual_comparison_options': get_comparison_label_options(),
    }


def update_exam_image_metadata(arquivo_id, patient_id, form_data):
    record = query(
        """
        SELECT a.id, a.exam_id, e.patient_id
        FROM exam_imagem_arquivos a
        JOIN exams e ON e.id = a.exam_id
        WHERE a.id = %s AND e.patient_id = %s
        """,
        (arquivo_id, patient_id),
        one=True,
    )
    if not record:
        return None

    metadata = build_exam_image_metadata(form_data)
    if not metadata['caption']:
        raise ValueError('A legenda da imagem é obrigatória.')

    execute(
        """
        UPDATE exam_imagem_arquivos
        SET visual_category = %s,
            caption = %s,
            clinical_context = %s,
            comparison_label = %s,
            comparison_group = %s,
            taken_at = NULLIF(%s, '')::timestamp
        WHERE id = %s
        """,
        (
            metadata['visual_category'],
            metadata['caption'],
            metadata['clinical_context'],
            metadata['comparison_label'],
            metadata['comparison_group'],
            metadata['taken_at'] or '',
            arquivo_id,
        ),
    )
    return dict(record)


def update_estomatologia_photo_metadata(photo_id, patient_id, form_data):
    record = query(
        """
        SELECT f.id, f.estomatologia_id, e.patient_id
        FROM estomatologia_fotos f
        JOIN estomatologia e ON e.id = f.estomatologia_id
        WHERE f.id = %s AND e.patient_id = %s
        """,
        (photo_id, patient_id),
        one=True,
    )
    if not record:
        return None

    metadata = build_estomatologia_photo_metadata(form_data)
    if not metadata['legenda']:
        raise ValueError('A legenda da foto é obrigatória.')

    execute(
        """
        UPDATE estomatologia_fotos
        SET visual_category = %s,
            legenda = %s,
            clinical_context = %s,
            comparison_label = %s,
            comparison_group = %s,
            taken_at = NULLIF(%s, '')::timestamp
        WHERE id = %s
        """,
        (
            metadata['visual_category'],
            metadata['legenda'],
            metadata['clinical_context'],
            metadata['comparison_label'],
            metadata['comparison_group'],
            metadata['taken_at'] or '',
            photo_id,
        ),
    )
    return dict(record)
