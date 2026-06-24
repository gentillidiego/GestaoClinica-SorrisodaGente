import os

from flask import Blueprint, jsonify, redirect, render_template, request, url_for, flash
from flask_login import current_user

from extensions import csrf
from services.communication_service import (
    channel_available,
    count_audience,
    create_campaign,
    create_template,
    get_campaign,
    get_template,
    list_bairros,
    list_campaign_messages,
    list_campaigns,
    list_municipios,
    list_opt_outs,
    list_templates,
    opt_out_whatsapp_by_phone,
    update_template,
    whatsapp_configured,
)
from services.security_service import audit_log

comunicacao_bp = Blueprint('comunicacao', __name__, url_prefix='/comunicacao')


@comunicacao_bp.before_request
def require_comunicacao_access():
    # O webhook é chamado pela Meta, sem sessão de usuário — fica de fora
    # da exigência de login/permissão dos demais endpoints administrativos.
    if request.endpoint == 'comunicacao.whatsapp_webhook':
        return None
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.url))
    if not current_user.can('comunicacao:view'):
        flash('Acesso negado ao módulo de Comunicação.', 'danger')
        return redirect(url_for('main.dashboard'))


def _require_write():
    if not current_user.can('comunicacao:write'):
        flash('Você não tem permissão para alterar dados do módulo de Comunicação.', 'danger')
        return False
    return True


@comunicacao_bp.route('/')
def dashboard():
    campaigns = list_campaigns()
    return render_template(
        'comunicacao/dashboard.html',
        campaigns=campaigns[:10],
        whatsapp_configured=whatsapp_configured(),
    )


@comunicacao_bp.route('/templates')
def templates_list():
    return render_template(
        'comunicacao/templates_list.html',
        templates=list_templates(),
        whatsapp_configured=whatsapp_configured(),
    )


@comunicacao_bp.route('/templates/novo', methods=['GET', 'POST'])
def template_new():
    if request.method == 'POST':
        if not _require_write():
            return redirect(url_for('comunicacao.templates_list'))
        channel = request.form.get('channel')
        if channel == 'whatsapp' and not whatsapp_configured():
            flash('Canal WhatsApp não está configurado nesta instância.', 'danger')
            return redirect(url_for('comunicacao.template_new'))
        template_id = create_template(
            channel=channel,
            category=request.form.get('category', 'campanha'),
            name=request.form.get('name'),
            subject=request.form.get('subject') or None,
            body=request.form.get('body'),
            whatsapp_template_name=request.form.get('whatsapp_template_name') or None,
            whatsapp_template_lang=request.form.get('whatsapp_template_lang') or 'pt_BR',
            created_by=current_user.id,
        )
        audit_log(
            action='communication_template_created',
            module='comunicacao',
            entity_type='communication_templates',
            entity_id=template_id,
        )
        flash('Template criado com sucesso.', 'success')
        return redirect(url_for('comunicacao.templates_list'))

    return render_template(
        'comunicacao/template_form.html',
        template=None,
        whatsapp_configured=whatsapp_configured(),
    )


@comunicacao_bp.route('/templates/<int:template_id>/editar', methods=['GET', 'POST'])
def template_edit(template_id):
    template = get_template(template_id)
    if not template:
        flash('Template não encontrado.', 'danger')
        return redirect(url_for('comunicacao.templates_list'))

    if request.method == 'POST':
        if not _require_write():
            return redirect(url_for('comunicacao.templates_list'))
        update_template(
            template_id,
            name=request.form.get('name'),
            subject=request.form.get('subject') or None,
            body=request.form.get('body'),
            whatsapp_template_name=request.form.get('whatsapp_template_name') or None,
            whatsapp_template_lang=request.form.get('whatsapp_template_lang') or 'pt_BR',
            active=bool(request.form.get('active')),
        )
        audit_log(
            action='communication_template_updated',
            module='comunicacao',
            entity_type='communication_templates',
            entity_id=template_id,
        )
        flash('Template atualizado.', 'success')
        return redirect(url_for('comunicacao.templates_list'))

    return render_template(
        'comunicacao/template_form.html',
        template=template,
        whatsapp_configured=whatsapp_configured(),
    )


@comunicacao_bp.route('/campanhas')
def campaigns_list():
    return render_template('comunicacao/campaigns_list.html', campaigns=list_campaigns())


@comunicacao_bp.route('/campanhas/nova', methods=['GET', 'POST'])
def campaign_new():
    if request.method == 'POST':
        if not _require_write():
            return redirect(url_for('comunicacao.campaigns_list'))

        audience_filter = {
            'municipios': request.form.getlist('municipios'),
            'bairros': request.form.getlist('bairros'),
            'generos': request.form.getlist('generos'),
            'idade_min': request.form.get('idade_min') or None,
            'idade_max': request.form.get('idade_max') or None,
        }
        try:
            campaign_id = create_campaign(
                name=request.form.get('name'),
                channel=request.form.get('channel'),
                template_id=request.form.get('template_id') or None,
                audience_filter=audience_filter,
                created_by=current_user.id,
            )
        except ValueError as exc:
            flash(str(exc), 'danger')
            return redirect(url_for('comunicacao.campaign_new'))

        audit_log(
            action='communication_campaign_created',
            module='comunicacao',
            entity_type='communication_campaigns',
            entity_id=campaign_id,
        )

        if request.form.get('send_now'):
            from tasks.communication_tasks import send_campaign_task

            send_campaign_task.delay(campaign_id)
            flash('Campanha criada e envio iniciado.', 'success')
        else:
            flash('Campanha salva como rascunho.', 'success')

        return redirect(url_for('comunicacao.campaign_detail', campaign_id=campaign_id))

    return render_template(
        'comunicacao/campaign_form.html',
        templates=list_templates(active_only=True),
        municipios=list_municipios(),
        bairros=list_bairros(),
        whatsapp_configured=whatsapp_configured(),
    )


@comunicacao_bp.route('/campanhas/<int:campaign_id>')
def campaign_detail(campaign_id):
    campaign = get_campaign(campaign_id)
    if not campaign:
        flash('Campanha não encontrada.', 'danger')
        return redirect(url_for('comunicacao.campaigns_list'))
    return render_template(
        'comunicacao/campaign_detail.html',
        campaign=campaign,
        messages=list_campaign_messages(campaign_id),
    )


@comunicacao_bp.route('/campanhas/contagem-publico', methods=['POST'])
def audience_count():
    audience_filter = {
        'municipios': request.form.getlist('municipios'),
        'bairros': request.form.getlist('bairros'),
        'generos': request.form.getlist('generos'),
        'idade_min': request.form.get('idade_min') or None,
        'idade_max': request.form.get('idade_max') or None,
    }
    channel = request.form.get('channel', 'email')
    return jsonify({'total': count_audience(audience_filter, channel)})


@comunicacao_bp.route('/preferencias')
def preferences_list():
    return render_template('comunicacao/preferences.html', opt_outs=list_opt_outs())


@comunicacao_bp.route('/webhook/whatsapp', methods=['GET', 'POST'])
@csrf.exempt
def whatsapp_webhook():
    if request.method == 'GET':
        verify_token = os.getenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN')
        if (
            request.args.get('hub.mode') == 'subscribe'
            and verify_token
            and request.args.get('hub.verify_token') == verify_token
        ):
            return request.args.get('hub.challenge', ''), 200
        return 'Verificação inválida.', 403

    payload = request.get_json(silent=True) or {}
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            for message in value.get('messages', []):
                text = (message.get('text') or {}).get('body', '').strip().upper()
                if text in {'PARAR', 'SAIR', 'CANCELAR', 'STOP'}:
                    opt_out_whatsapp_by_phone(message.get('from'))
    return jsonify({'status': 'ok'})
