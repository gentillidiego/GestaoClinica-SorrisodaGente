import os

from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database import query
import datetime
from extensions import limiter
from services.bi_report_service import (
    get_bi_report,
    list_bi_government_reports,
    register_bi_government_report,
)
from services.command_center_service import get_command_center_data
from services.epidemiology_service import get_epidemiology_dashboard
from services.executive_bi_service import get_executive_bi_dashboard
from services.institutional_report_service import update_generated_report_task
from services.security_service import audit_log, permission_required
from tasks.pdf_tasks import generate_pdf_task

main_bp = Blueprint('main', __name__)

import time

@main_bp.route('/health')
@limiter.exempt
def health_check():
    """Endpoint de health check para monitoramento externo."""
    start = time.time()
    try:
        query("SELECT 1", one=True)
        db_ok = True
        db_latency = round((time.time() - start) * 1000, 2)
    except Exception as e:
        db_ok = False
        db_latency = -1

    status_code = 200 if db_ok else 503
    return jsonify({
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "db_latency_ms": db_latency,
        "timestamp": time.time()
    }), status_code

@main_bp.route('/')
def index():
    return render_template('landing.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Estatísticas básicas de pacientes
    total_patients = query("SELECT COUNT(*) as count FROM patients", one=True)['count']

    first_day_month = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')
    patients_month = query("SELECT COUNT(*) as count FROM patients WHERE criado_em >= %s", (first_day_month,), one=True)['count']

    today = datetime.date.today().strftime('%Y-%m-%d')

    # Atendimentos (tabela legada)
    appointments_today = query("SELECT COUNT(*) as count FROM atendimentos WHERE date(data) = %s", (today,), one=True)['count']

    # Tratamentos pendentes
    pending_treatments = query("SELECT COUNT(*) as count FROM tratamento_procedimentos WHERE status = 'Pendente'", one=True)['count']

    # Pacientes em Alerta Vermelho (suspeita de neoplasia bucal)
    red_alert_patients_count = query("SELECT COUNT(*) as count FROM estomatologia WHERE suspeita_neoplasia = TRUE", one=True)['count']

    # Últimos 5 pacientes cadastrados
    recent_patients = query(
        "SELECT id, nome, criado_em FROM patients ORDER BY id DESC LIMIT 5"
    )

    # Procedimentos individuais realizados (da Evolução Clínica / Tratamento)
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    first_day_str = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')

    procedimentos_hoje = query(
        "SELECT COUNT(*) as count FROM tratamento_procedimentos WHERE status = 'Concluído' AND data_sessao = %s",
        (today_str,), one=True
    )['count']

    procedimentos_mes = query(
        "SELECT COUNT(*) as count FROM tratamento_procedimentos WHERE status = 'Concluído' AND data_sessao >= %s",
        (first_day_str,), one=True
    )['count']

    # ── Estatísticas da Agenda ──────────────────────────────────────────
    # Total geral de consultas por status
    agenda_stats_rows = query(
        "SELECT status, COUNT(*) as count FROM consultas GROUP BY status"
    )
    agenda_by_status = {r['status']: r['count'] for r in (agenda_stats_rows or [])}

    agenda_planejadas  = agenda_by_status.get('Pendente', 0) + agenda_by_status.get('Confirmado', 0)
    agenda_confirmadas = agenda_by_status.get('Confirmado', 0)
    agenda_concluidas  = agenda_by_status.get('Realizado', 0)
    agenda_canceladas  = agenda_by_status.get('Cancelado', 0)
    agenda_faltas      = agenda_by_status.get('Faltou', 0)
    agenda_total       = sum(agenda_by_status.values())

    # Consultas de hoje (para a lista rápida)
    consultas_hoje = query(
        """
        SELECT c.id, c.data_consulta, c.status, c.duracao_minutos,
               p.id as patient_id, p.nome as patient_nome,
               u.full_name as dentista_nome
        FROM consultas c
        JOIN patients p ON c.patient_id = p.id
        JOIN users u ON c.dentista_id = u.id
        WHERE DATE(c.data_consulta) = %s
          AND c.status != 'Cancelado'
        ORDER BY c.data_consulta ASC
        LIMIT 6
        """,
        (today,)
    )

    # Taxa de conclusão (evitar divisão por zero)
    taxa_conclusao = round((agenda_concluidas / agenda_total * 100)) if agenda_total > 0 else 0

    stats = {
        'total_patients':     total_patients,
        'patients_month':     patients_month,
        'appointments_today': appointments_today,
        'pending_treatments':  pending_treatments,
        'procedimentos_hoje':  procedimentos_hoje,
        'procedimentos_mes':   procedimentos_mes,
        'red_alert_patients_count': red_alert_patients_count,
        # agenda
        'agenda_planejadas':  agenda_planejadas,
        'agenda_confirmadas': agenda_confirmadas,
        'agenda_concluidas':  agenda_concluidas,
        'agenda_canceladas':  agenda_canceladas,
        'agenda_faltas':      agenda_faltas,
        'agenda_total':       agenda_total,
        'taxa_conclusao':     taxa_conclusao,
        'pending_signatures':  0,
    }

    return render_template(
        'index.html',
        user=current_user,
        stats=stats,
        recent_patients=recent_patients,
        consultas_hoje=consultas_hoje,
    )


@main_bp.route('/command-center')
@login_required
@permission_required('command_center:view')
def command_center():
    data = get_command_center_data()
    return render_template('command_center.html', data=data)


@main_bp.route('/epidemiologia')
@login_required
@permission_required('epidemiologia:view')
def epidemiologia_dashboard():
    data = get_epidemiology_dashboard(
        start_date=request.args.get('inicio'),
        end_date=request.args.get('fim'),
        neighborhood=request.args.get('bairro'),
        municipality=request.args.get('municipio'),
        specialty=request.args.get('especialidade'),
        professional_id=request.args.get('profissional'),
        gender=request.args.get('sexo'),
        age_group=request.args.get('faixa_etaria'),
        treatment_status=request.args.get('status_tratamento'),
    )
    return render_template('epidemiologia.html', data=data)


@main_bp.route('/bi')
@login_required
@permission_required('bi:view')
def bi_dashboard():
    data = get_executive_bi_dashboard(
        start_date=request.args.get('inicio'),
        end_date=request.args.get('fim'),
        view=request.args.get('visao'),
    )
    return render_template(
        'bi_dashboard.html',
        data=data,
        generated_bi_reports=list_bi_government_reports(limit=8),
    )


@main_bp.route('/bi/export', methods=['POST'])
@login_required
@permission_required('bi:view')
def export_bi_government_pdf():
    report = get_bi_report(
        start_date=request.form.get('inicio'),
        end_date=request.form.get('fim'),
        view=request.form.get('visao'),
    )
    generated_by = current_user.full_name or current_user.username
    html = render_template(
        'pdfs/bi_government_report_pdf.html',
        report=report,
        generated_by=generated_by,
    )

    pdf_dir = os.path.join(os.getcwd(), 'pdf_temp')
    os.makedirs(pdf_dir, exist_ok=True)
    start = report['period']['start'].strftime('%Y%m%d')
    end = report['period']['end'].strftime('%Y%m%d')
    filename = f"relatorio_bi_governamental_{report['view']}_{start}_{end}_{current_user.id}.pdf"
    output_path = os.path.join(pdf_dir, filename)

    report_id = register_bi_government_report(
        report,
        filename=filename,
        file_path=output_path,
        generated_by=current_user.id,
    )
    task = generate_pdf_task.delay(html, output_path, report_id)
    update_generated_report_task(report_id, task.id)
    audit_log(
        action='bi_government_report_exported',
        module='bi',
        entity_type='generated_report',
        entity_id=report_id,
        details={
            'view': report['view'],
            'period_start': report['period']['start'],
            'period_end': report['period']['end'],
            'filename': filename,
            'economy_methodology_status': report['dashboard']['economy']['methodology_status'],
        },
    )
    flash('Relatório governamental do BI enviado para geração em PDF.', 'success')
    return redirect(url_for('documents.pdf_status', task_id=task.id, filename=filename))
