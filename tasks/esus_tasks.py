"""
Tarefas Celery para envio automático quinzenal de remessas e-SUS APS.

Agendamento (Celery Beat):
  - Executa diariamente às 06:00.
  - A task verifica se hoje é o dia de envio configurado (dia 15 ou dia 5).
  - Se sim, gera o XML e envia por e-mail.
"""
import datetime as dt
import logging

from celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, name='tasks.esus_tasks.gerar_e_enviar_remessa_quinzenal',
             max_retries=2, default_retry_delay=300)
def gerar_e_enviar_remessa_quinzenal(self, force_periodo_label=None, dry_run=False):
    """
    Verifica se hoje é dia de envio de remessa e-SUS e executa automaticamente.

    Parâmetros:
        force_periodo_label: se informado, força a geração do período com esse label
                             (ex: '2026-06 P1'). Útil para reenvios manuais via admin.
        dry_run: se True, gera o XML mas não envia o e-mail.

    Retorna dict com resultado da execução.
    """
    from services.esus_export_service import (
        build_quinzenal_periods,
        enviar_remessa_por_email,
        gerar_remessa_xml,
        get_esus_settings,
        is_settings_complete,
    )

    settings = get_esus_settings()
    email_destino = settings.get('email_destino_remessa', '')
    remessa_ativa = settings.get('remessa_ativa', False)

    if not remessa_ativa and not force_periodo_label:
        logger.info('[e-SUS] Remessa automática inativa. Pulando.')
        return {'status': 'inativo', 'mensagem': 'Remessa automática desativada nas configurações.'}

    if not is_settings_complete(settings) and not force_periodo_label:
        logger.warning('[e-SUS] CNES ou INE não configurados. Remessa bloqueada.')
        return {'status': 'bloqueado', 'mensagem': 'CNES e/ou INE não configurados. Remessa bloqueada.'}

    periods = build_quinzenal_periods()

    resultados = []
    for period in periods:
        if force_periodo_label and period['periodo_label'] != force_periodo_label:
            continue
        if not force_periodo_label and not period['is_due_today']:
            continue

        label = period['periodo_label']
        logger.info(f'[e-SUS] Gerando remessa: {label}')

        try:
            result = gerar_remessa_xml(
                data_inicio=period['periodo_inicio'],
                data_fim=period['periodo_fim'],
                periodo_label=label,
                generated_by=None,  # automático
            )

            if not dry_run and email_destino:
                ok, erro = enviar_remessa_por_email(
                    remessa_id=result['remessa_id'],
                    xml_path=result['xml_path'],
                    periodo_label=label,
                    email_destino=email_destino,
                    filename=result['filename'],
                )
                if ok:
                    logger.info(f'[e-SUS] Remessa {label} enviada para {email_destino}.')
                    resultados.append({'periodo': label, 'status': 'enviado', 'email': email_destino})
                else:
                    logger.error(f'[e-SUS] Falha no envio da remessa {label}: {erro}')
                    resultados.append({'periodo': label, 'status': 'erro_email', 'erro': erro})
            else:
                logger.info(f'[e-SUS] Remessa {label} gerada (dry_run ou sem e-mail destino).')
                resultados.append({
                    'periodo': label,
                    'status': 'gerado_sem_envio',
                    'xml_path': result['xml_path'],
                    'records_ready': result['records_ready'],
                })

        except Exception as exc:
            logger.exception(f'[e-SUS] Erro ao gerar remessa {label}: {exc}')
            resultados.append({'periodo': label, 'status': 'erro', 'erro': str(exc)})
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                pass

    if not resultados:
        return {'status': 'sem_remessa', 'mensagem': 'Nenhum período de envio corresponde a hoje.'}

    return {'status': 'ok', 'resultados': resultados}
