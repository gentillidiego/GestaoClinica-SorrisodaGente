from celery_app import celery


@celery.task(bind=True, max_retries=2)
def generate_monthly_reports_task(self, report_type='all', month=None, output_dir=None):
    """
    Gera os relatórios mensais institucionais agendados.
    A importação da aplicação acontece dentro da task para evitar ciclos no boot do Celery.
    """
    try:
        from app import app
        from services.report_generation_service import generate_monthly_reports

        with app.app_context():
            return generate_monthly_reports(
                report_type=report_type,
                month=month,
                output_dir=output_dir,
                source='scheduler',
                task_id=self.request.id,
                skip_existing=True,
            )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
