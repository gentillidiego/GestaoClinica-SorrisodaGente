from celery_app import celery
from weasyprint import HTML
from services.institutional_report_service import (
    finalize_generated_report,
    mark_generated_report_failed,
)

@celery.task(bind=True, max_retries=3)
def generate_pdf_task(self, html_content, output_path, report_run_id=None):
    """
    Gera PDF em background e salva em output_path.
    Retorna o caminho do arquivo gerado.
    """
    try:
        HTML(string=html_content).write_pdf(output_path)
        if report_run_id:
            finalize_generated_report(report_run_id, output_path)
        return output_path
    except Exception as exc:
        if report_run_id and self.request.retries >= self.max_retries:
            mark_generated_report_failed(report_run_id, exc)
        raise self.retry(exc=exc, countdown=5)
