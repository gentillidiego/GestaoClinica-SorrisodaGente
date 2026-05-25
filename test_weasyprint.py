import weasyprint
try:
    pdf = weasyprint.HTML(string="<h1>Test</h1>").write_pdf()
    print("SUCCESS: WeasyPrint can generate PDFs.")
except Exception as e:
    print(f"FAILED: {e}")
