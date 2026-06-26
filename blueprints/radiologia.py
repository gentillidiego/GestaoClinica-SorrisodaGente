from flask import Blueprint, render_template
from flask_login import login_required

from database import query

radiologia_bp = Blueprint('radiologia', __name__, url_prefix='/radiologia')


@radiologia_bp.route('/solicitacoes')
@login_required
def solicitacoes():
    pending_requests = query(
        """
        SELECT er.*, p.nome AS patient_name, u.full_name AS requested_by_name,
               u.username AS requested_by_username
        FROM exam_requests er
        JOIN patients p ON p.id = er.patient_id
        JOIN users u ON u.id = er.requested_by
        WHERE er.status = 'pendente' AND er.tipo = 'imagem'
        ORDER BY er.requested_at ASC
        """
    )

    items = []
    for row in pending_requests:
        item = dict(row)
        item['resumo'] = item['tipo_imagem'] or 'Exame de imagem'
        if item['detalhe_escopo']:
            item['resumo'] += f" ({item['detalhe_escopo']})"
        item['attend_endpoint'] = 'exams.imagem'
        items.append(item)

    return render_template('radiologia/solicitacoes.html', items=items)
