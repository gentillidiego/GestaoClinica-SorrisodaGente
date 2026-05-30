from celery_app import celery
from weasyprint import HTML
from database import execute

@celery.task(bind=True, max_retries=3)
def generate_pdf_task(self, html_content, output_path, report_run_id=None):
    """
    Gera PDF em background e salva em output_path.
    Retorna o caminho do arquivo gerado.
    """
    try:
        HTML(string=html_content).write_pdf(output_path)
        if report_run_id:
            execute(
                """
                UPDATE generated_reports
                SET status = 'success', completed_at = NOW()
                WHERE id = %s
                """,
                (report_run_id,)
            )
        return output_path
    except Exception as exc:
        if report_run_id and self.request.retries >= self.max_retries:
            execute(
                """
                UPDATE generated_reports
                SET status = 'failed', completed_at = NOW()
                WHERE id = %s
                """,
                (report_run_id,)
            )
        raise self.retry(exc=exc, countdown=5)
