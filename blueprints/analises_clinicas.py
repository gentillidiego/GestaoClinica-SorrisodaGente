from flask import Blueprint, render_template
from flask_login import login_required

from database import query
from services.clinical_lab_exam_service import get_clinical_lab_exam_label

analises_clinicas_bp = Blueprint(
    'analises_clinicas', __name__, url_prefix='/analises-clinicas'
)


@analises_clinicas_bp.route('/solicitacoes')
@login_required
def solicitacoes():
    pending_requests = query(
        """
        SELECT er.*, p.nome AS patient_name, u.full_name AS requested_by_name,
               u.username AS requested_by_username
        FROM exam_requests er
        JOIN patients p ON p.id = er.patient_id
        JOIN users u ON u.id = er.requested_by
        WHERE er.status = 'pendente' AND er.tipo = 'clinico_laboratorial'
        ORDER BY er.requested_at ASC
        """
    )

    items = []
    for row in pending_requests:
        item = dict(row)
        item['resumo'] = (
            get_clinical_lab_exam_label(item['categoria'])
            if item['categoria']
            else 'Exame clínico/laboratorial'
        )
        if item['laboratorio']:
            item['resumo'] += f' — {item["laboratorio"]}'
        item['attend_endpoint'] = 'exams.clinico_laboratorial'
        items.append(item)

    return render_template('analises_clinicas/solicitacoes.html', items=items)
