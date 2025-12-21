
import logging
from weasyprint import HTML, CSS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("repro")

def generate_pdf_repro():
    try:
        html_out = "<h1>Teste PDF</h1><p>Hello World</p>"
        temp_pdf = "test_output.pdf"
        
        logger.info("Generating PDF...")
        # Simulating the call in processor.py
        HTML(string=html_out).write_pdf(temp_pdf)
        logger.info("PDF generated successfully.")
        
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    generate_pdf_repro()
