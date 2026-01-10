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
        self.jinja_env.filters['resolve_path'] = self.resolve_path

    def generate_pdf_bytes(self, data: dict, original_filename: str = "relatorio", template_name: str = "pdf_template.html") -> bytes:
        """
        Gera bytes do PDF a partir de um dicionário de dados.
        """
        try:
            template = self.jinja_env.get_template(template_name)
            
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
            # Define o base_url como o diretório src do projeto para resolver /static corretamente
            project_root = os.path.abspath(os.path.join(self.template_dir, '..'))
            
            return HTML(string=html_out, base_url=project_root).write_pdf(stylesheets=stylesheets)
        except Exception as e:
            logger.error(f"Erro gerando PDF: {e}")
            raise

    def resolve_path(self, url):
        """
        Filtro Jinja para resolver caminhos relativos de URL (/static/...) para caminhos absolutos de arquivo.
        Necessário para o WeasyPrint encontrar imagens locais.
        """
        if not url:
            return ""
        
        # Se já for absoluto, retorna
        if url.startswith('http') or url.startswith('file://'):
            return url
            
        # Se começar com /, assume que é relativo à raiz do projeto (src)
        # O app Flask serve /static a partir da pasta static dentro de src
        if url.startswith('/'):
            # Remove a barra inicial para o os.path.join funcionar
            relative_path = url.lstrip('/')
            # Caminho absoluto para a pasta src
            project_root = os.path.abspath(os.path.join(self.template_dir, '..'))
            absolute_path = os.path.join(project_root, relative_path)
            
            # Converte para URI file:// para o WeasyPrint
            return f"file://{absolute_path}"
            
        return url

# Singleton Instance
pdf_service = PDFService()
