import os
import sys
from jinja2 import Environment, FileSystemLoader, exceptions

# Adiciona raiz do projeto ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def validate_templates():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(base_dir, 'src', 'templates')
    
    print(f"🔍 Validando templates em: {templates_dir}")
    
    env = Environment(loader=FileSystemLoader(templates_dir))
    
    # Mock filters/functions used in templates to avoid runtime errors during compilation
    # Adicione aqui filtros customizados se existirem no app.py
    # env.filters['datetime_format'] = lambda x: x 
    
    has_errors = False
    count = 0
    
    for root, _, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                count += 1
                rel_path = os.path.relpath(os.path.join(root, file), templates_dir)
                try:
                    # Tenta carregar e compilar o template
                    # Apenas enviroment.parse ou get_template já dispara SyntaxError
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        source = f.read()
                    
                    env.parse(source)
                    # print(f"✅ {rel_path} - OK")
                    
                except exceptions.TemplateSyntaxError as e:
                    print(f"❌ ERRO DE SINTAXE em {rel_path}:")
                    print(f"   Linha {e.lineno}: {e.message}")
                    has_errors = True
                except Exception as e:
                    print(f"⚠️  Erro genérico ao ler {rel_path}: {e}")
                    has_errors = True
                    
    print("-" * 40)
    if has_errors:
        print("💥 ERROS ENCONTRADOS! Corrija antes do deploy.")
        sys.exit(1)
    else:
        print(f"✅ Sucesso: {count} templates validados. Nenhum erro de sintaxe encontrado.")
        sys.exit(0)

if __name__ == "__main__":
    validate_templates()
