from database import execute, query
from services.sigtap_service import get_sigtap_procedure
from services.security_service import audit_log


def credit_exam_request_productivity(exam_request, exam_id):
    """Credita ao clínico solicitante o(s) procedimento(s) SIGTAP do exame atendido.

    Chamada depois que a solicitação já foi marcada como 'atendido'. Tipos/
    categorias sem código SIGTAP mapeado não geram nenhum lançamento — o
    clínico continua podendo lançar manualmente no Plano de Tratamento, como
    já era possível antes desta automação.
    """
    if not exam_request:
        return []

    if exam_request['tipo'] == 'imagem':
        from blueprints.exams import IMAGE_EXAM_SIGTAP_CODES

        code = IMAGE_EXAM_SIGTAP_CODES.get(exam_request.get('tipo_imagem'))
        codes = (code,) if code else ()
        especialidade = 'diagnostico_estomatologia_radiologia'
    else:
        from services.clinical_lab_exam_service import CLINICAL_LAB_SIGTAP_CODES

        codes = CLINICAL_LAB_SIGTAP_CODES.get(exam_request.get('categoria'), ())
        especialidade = 'apoio_diagnostico_laboratorial'

    if not codes:
        return []

    already = query(
        'SELECT id FROM tratamento_procedimentos WHERE exam_request_id = %s',
        (exam_request['id'],),
    )
    if already:
        return [row['id'] for row in already]

    created_ids = []
    for code in codes:
        sigtap = get_sigtap_procedure(code)
        if not sigtap:
            continue
        proc_id = execute(
            """
            INSERT INTO tratamento_procedimentos (
                patient_id, descricao, especialidade_sigtap,
                sigtap_code, sigtap_competence, sigtap_name,
                validator_id, status, data_sessao, exam_request_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Concluído', CURRENT_DATE, %s)
            RETURNING id
            """,
            (
                exam_request['patient_id'],
                f"{sigtap['name']} (gerado automaticamente — exame solicitado)",
                especialidade,
                sigtap['code'],
                sigtap['competence'],
                sigtap['name'],
                exam_request['requested_by'],
                exam_request['id'],
            ),
        )
        created_ids.append(proc_id)
        audit_log(
            action='exam_request_productivity_credited',
            module='treatment',
            entity_type='tratamento_procedimentos',
            entity_id=proc_id,
            patient_id=exam_request['patient_id'],
            details={
                'exam_request_id': exam_request['id'],
                'exam_id': exam_id,
                'sigtap_code': sigtap['code'],
                'credited_to': exam_request['requested_by'],
            },
        )
    return created_ids
