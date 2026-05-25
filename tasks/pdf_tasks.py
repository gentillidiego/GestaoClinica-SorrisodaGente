from celery_app import celery
from weasyprint import HTML
import tempfile
import os

@celery.task(bind=True, max_retries=3)
def generate_pdf_task(self, html_content, output_path):
    """
    Gera PDF em background e salva em output_path.
    Retorna o caminho do arquivo gerado.
    """
    try:
        HTML(string=html_content).write_pdf(output_path)
        return output_path
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)
