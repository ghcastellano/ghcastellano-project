import os
from datetime import datetime
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
import logging

# from src import models # Legacy import removed to avoid circular dependency
# import models

logger = logging.getLogger(__name__)

class PDFService:
    def __init__(self, template_dir='src/templates'):
        self.template_dir = template_dir
        # Garante caminho absoluto para robustez em diferentes contextos de execução
        if not os.path.isabs(template_dir):
            self.template_dir = os.path.join(os.getcwd(), template_dir)
            
        self.jinja_env = Environment(loader=FileSystemLoader(self.template_dir))

    def generate_pdf_bytes(self, data: dict, original_filename: str = "relatorio") -> bytes:
        """
        Gera bytes do PDF a partir de um dicionário de dados (ou objeto model dump).
        """
        try:
            template = self.jinja_env.get_template('base_layout.html')
            
            # Parsing de dados para garantir que corresponda às expectativas do template
            # "data" geralmente é um dict vindo da leitura do JSON
            
            html_out = template.render(
                relatorio=data,
                data_geracao=datetime.now().strftime("%d/%m/%Y")
            )
            
            stylesheets = []
            style_path = os.path.join(self.template_dir, 'style.css')
            if os.path.exists(style_path):
                stylesheets.append(CSS(style_path))
                
            # Base URL é crítica para links relativos (imagens, css)
            return HTML(string=html_out, base_url=self.template_dir).write_pdf(stylesheets=stylesheets)
        except Exception as e:
            logger.error(f"Erro gerando PDF: {e}")
            raise

# Singleton Instance
pdf_service = PDFService()
