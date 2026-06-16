import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database import query
from constants import CLINICAL_EXECUTOR_ROLES, Role
from services.institutional_report_service import (
    get_institutional_report,
    get_report_profile,
    get_report_types_for_role,
    get_report_type_choices,
    list_generated_reports,
    register_generated_report,
    role_can_access_report_type,
    update_generated_report_task,
)
from tasks.pdf_tasks import generate_pdf_task

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.before_request
@login_required
def require_reports_access():
    if not current_user.can('reports:view'):
        flash('Acesso negado para relatórios.', 'danger')
        return redirect(url_for('main.dashboard'))

@reports_bp.route('/', methods=['GET', 'POST'])
def index():
    report_user_roles = tuple(sorted(CLINICAL_EXECUTOR_ROLES | {Role.ADMIN}))
    placeholders = ', '.join(['%s'] * len(report_user_roles))
    dentistas = query(
        f"SELECT id, full_name, role FROM users WHERE role IN ({placeholders})",
        report_user_roles,
    )
    
    # Valores padrão
    data_inicio = request.form.get('data_inicio') or ''
    data_fim = request.form.get('data_fim') or ''
    dentista_id = request.form.get('dentista_id') or ''
    tipo_procedimento = request.form.get('tipo_procedimento') or ''
    status_procedimento = request.form.get('status_procedimento') or ''
    
    kpis = {
        'produtividade': 0,
        'conversao': 0.0,
        'absenteismo': 0.0,
        'total_agendamentos': 0,
        'valor_aprovado': 0.0,
        'valor_total': 0.0
    }
    
    procedimentos = []
    
    if request.method == 'POST' and not request.form.get('export_pdf'):
        # Filtros base para procedimentos
        proc_query = """
            SELECT tp.id, tp.data_sessao, tp.dente, tp.descricao, tp.status, 
                   p.nome as patient_name, u.full_name as dentista_name
            FROM tratamento_procedimentos tp
            JOIN patients p ON tp.patient_id = p.id
            LEFT JOIN users u ON tp.professor_id = u.id
            WHERE 1=1
        """
        proc_params = []
        
        if data_inicio:
            proc_query += " AND tp.criado_em >= %s"
            proc_params.append(f"{data_inicio} 00:00:00")
        if data_fim:
            proc_query += " AND tp.criado_em <= %s"
            proc_params.append(f"{data_fim} 23:59:59")
        if dentista_id:
            proc_query += " AND tp.professor_id = %s"
            proc_params.append(dentista_id)
        if tipo_procedimento:
            proc_query += " AND tp.descricao ILIKE %s"
            proc_params.append(f"%{tipo_procedimento}%")
        if status_procedimento:
            proc_query += " AND tp.status = %s"
            proc_params.append(status_procedimento)
            
        proc_query += " ORDER BY tp.criado_em DESC"
        procedimentos = query(proc_query, tuple(proc_params))
        
        # KPI: Produtividade (Qtd de procedimentos)
        kpis['produtividade'] = len(procedimentos)
        
        # KPI: Conversão (Planos Aprovados vs Total)
        plan_query = "SELECT SUM(custo_estimado) as total, status FROM planos_tratamento WHERE 1=1"
        plan_params = []
        if data_inicio:
            plan_query += " AND criado_em >= %s"
            plan_params.append(f"{data_inicio} 00:00:00")
        if data_fim:
            plan_query += " AND criado_em <= %s"
            plan_params.append(f"{data_fim} 23:59:59")
        
        plan_query += " GROUP BY status"
        planos = query(plan_query, tuple(plan_params))
        
        valor_total = sum(p['total'] or 0 for p in planos)
        valor_aprovado = sum(p['total'] or 0 for p in planos if p['status'] == 'Aprovado')
        
        kpis['valor_total'] = valor_total
        kpis['valor_aprovado'] = valor_aprovado
        if valor_total > 0:
            kpis['conversao'] = (valor_aprovado / valor_total) * 100
            
        # KPI: Absenteísmo (Consultas Canceladas vs Total)
        cons_query = "SELECT status, count(id) as qtd FROM consultas WHERE 1=1"
        cons_params = []
        if data_inicio:
            cons_query += " AND data_consulta >= %s"
            cons_params.append(f"{data_inicio} 00:00:00")
        if data_fim:
            cons_query += " AND data_consulta <= %s"
            cons_params.append(f"{data_fim} 23:59:59")
        if dentista_id:
            cons_query += " AND dentista_id = %s"
            cons_params.append(dentista_id)
            
        cons_query += " GROUP BY status"
        consultas = query(cons_query, tuple(cons_params))
        
        total_consultas = sum(c['qtd'] for c in consultas)
        canceladas = sum(c['qtd'] for c in consultas if c['status'] in ['Cancelado', 'Faltou'])
        
        kpis['total_agendamentos'] = total_consultas
        if total_consultas > 0:
            kpis['absenteismo'] = (canceladas / total_consultas) * 100

    return render_template('reports/index.html', 
                           dentistas=dentistas,
                           kpis=kpis,
                           procedimentos=procedimentos,
                           data_inicio=data_inicio,
                           data_fim=data_fim,
                           dentista_id=dentista_id,
                           tipo_procedimento=tipo_procedimento,
                           status_procedimento=status_procedimento)

@reports_bp.route('/export', methods=['POST'])
def export_pdf():
    # Coletar mesmos filtros e refazer a busca (ou passar via JSON escondido, mas refazer é mais seguro)
    data_inicio = request.form.get('data_inicio') or ''
    data_fim = request.form.get('data_fim') or ''
    dentista_id = request.form.get('dentista_id') or ''
    tipo_procedimento = request.form.get('tipo_procedimento') or ''
    status_procedimento = request.form.get('status_procedimento') or ''
    
    # Recalcular as queries (mesma lógica do index)
    proc_query = """
        SELECT tp.data_sessao, tp.dente, tp.descricao, tp.status, 
               p.nome as patient_name, u.full_name as dentista_name
        FROM tratamento_procedimentos tp
        JOIN patients p ON tp.patient_id = p.id
        LEFT JOIN users u ON tp.professor_id = u.id
        WHERE 1=1
    """
    proc_params = []
    
    if data_inicio:
        proc_query += " AND tp.criado_em >= %s"
        proc_params.append(f"{data_inicio} 00:00:00")
    if data_fim:
        proc_query += " AND tp.criado_em <= %s"
        proc_params.append(f"{data_fim} 23:59:59")
    if dentista_id:
        proc_query += " AND tp.professor_id = %s"
        proc_params.append(dentista_id)
    if tipo_procedimento:
        proc_query += " AND tp.descricao ILIKE %s"
        proc_params.append(f"%{tipo_procedimento}%")
    if status_procedimento:
        proc_query += " AND tp.status = %s"
        proc_params.append(status_procedimento)
        
    proc_query += " ORDER BY tp.criado_em DESC"
    procedimentos = query(proc_query, tuple(proc_params))
    
    kpis = {'produtividade': len(procedimentos), 'conversao': 0.0, 'absenteismo': 0.0, 'valor_aprovado': 0.0, 'valor_total': 0.0}
    
    plan_query = "SELECT SUM(custo_estimado) as total, status FROM planos_tratamento WHERE 1=1"
    plan_params = []
    if data_inicio:
        plan_query += " AND criado_em >= %s"
        plan_params.append(f"{data_inicio} 00:00:00")
    if data_fim:
        plan_query += " AND criado_em <= %s"
        plan_params.append(f"{data_fim} 23:59:59")
    plan_query += " GROUP BY status"
    planos = query(plan_query, tuple(plan_params))
    
    valor_total = sum(p['total'] or 0 for p in planos)
    valor_aprovado = sum(p['total'] or 0 for p in planos if p['status'] == 'Aprovado')
    kpis['valor_total'] = valor_total
    kpis['valor_aprovado'] = valor_aprovado
    if valor_total > 0:
        kpis['conversao'] = (valor_aprovado / valor_total) * 100
        
    cons_query = "SELECT status, count(id) as qtd FROM consultas WHERE 1=1"
    cons_params = []
    if data_inicio:
        cons_query += " AND data_consulta >= %s"
        cons_params.append(f"{data_inicio} 00:00:00")
    if data_fim:
        cons_query += " AND data_consulta <= %s"
        cons_params.append(f"{data_fim} 23:59:59")
    if dentista_id:
        cons_query += " AND dentista_id = %s"
        cons_params.append(dentista_id)
    cons_query += " GROUP BY status"
    consultas = query(cons_query, tuple(cons_params))
    
    total_consultas = sum(c['qtd'] for c in consultas)
    canceladas = sum(c['qtd'] for c in consultas if c['status'] in ['Cancelado', 'Faltou'])
    if total_consultas > 0:
        kpis['absenteismo'] = (canceladas / total_consultas) * 100

    html = render_template('pdfs/relatorio_gerencial_pdf.html', 
                           procedimentos=procedimentos,
                           kpis=kpis,
                           data_inicio=data_inicio,
                           data_fim=data_fim)
                           
    pdf_dir = os.path.join(os.getcwd(), 'pdf_temp')
    os.makedirs(pdf_dir, exist_ok=True)
    filename = f'relatorio_gerencial_{current_user.id}.pdf'
    output_path = os.path.join(pdf_dir, filename)
    
    task = generate_pdf_task.delay(html, output_path)
    return redirect(url_for('documents.pdf_status', task_id=task.id, filename=filename))


@reports_bp.route('/institutional')
def institutional():
    allowed_report_types = get_report_types_for_role(current_user.role)
    if not allowed_report_types:
        flash('Seu perfil não possui acesso aos relatórios institucionais.', 'danger')
        return redirect(url_for('main.dashboard'))

    report_type = request.args.get('tipo') or 'institucional'
    if report_type not in allowed_report_types:
        report_type = allowed_report_types[0]
        flash('Perfil de relatório ajustado conforme sua permissão de acesso.', 'warning')

    report = get_institutional_report(
        start_date=request.args.get('inicio'),
        end_date=request.args.get('fim'),
        report_type=report_type,
    )
    generated_reports = list_generated_reports(limit=12, report_types=allowed_report_types)
    return render_template(
        'reports/institutional.html',
        report=report,
        report_type_choices=get_report_type_choices(allowed_report_types),
        generated_reports=generated_reports,
    )


@reports_bp.route('/institutional/export', methods=['POST'])
def export_institutional_pdf():
    report_type = request.form.get('tipo') or 'institucional'
    if not role_can_access_report_type(current_user.role, report_type):
        flash('Seu perfil não pode gerar este tipo de relatório.', 'danger')
        return redirect(url_for('reports.institutional'))

    report = get_institutional_report(
        start_date=request.form.get('inicio'),
        end_date=request.form.get('fim'),
        report_type=report_type,
    )
    generated_by = current_user.full_name or current_user.username
    html = render_template(
        'pdfs/relatorio_institucional_pdf.html',
        report=report,
        generated_by=generated_by,
    )

    pdf_dir = os.path.join(os.getcwd(), 'pdf_temp')
    os.makedirs(pdf_dir, exist_ok=True)
    profile = get_report_profile(report_type)
    start = report['period']['start'].strftime('%Y%m%d')
    end = report['period']['end'].strftime('%Y%m%d')
    filename = f"{profile['filename_prefix']}_{start}_{end}_{current_user.id}.pdf"
    output_path = os.path.join(pdf_dir, filename)

    report_id = register_generated_report(
        report,
        filename=filename,
        file_path=output_path,
        generated_by=current_user.id,
        source='manual',
        delivery_channel='painel_seguro',
    )
    task = generate_pdf_task.delay(html, output_path, report_id)
    update_generated_report_task(report_id, task.id)
    return redirect(url_for('documents.pdf_status', task_id=task.id, filename=filename))
