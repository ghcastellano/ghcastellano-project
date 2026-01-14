import os
import re
import sys
from flask import Flask

# Mock flask app for jinja env
app = Flask(__name__, template_folder='src/templates')

def check_templates_for_csrf():
    print("🔍 [1/3] Auditando Templates por falta de CSRF Token...")
    template_dir = 'src/templates'
    warnings = []
    
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    forms = re.finditer(r'<form[^>]*>', content, re.IGNORECASE)
                    for form_match in forms:
                        form_tag = form_match.group(0)
                        if 'method="get"' in form_tag.lower() or "method='get'" in form_tag.lower():
                            continue
                        
                        start_idx = form_match.end()
                        end_match = re.search(r'</form>', content[start_idx:], re.IGNORECASE)
                        
                        if end_match:
                            form_content = content[start_idx : start_idx + end_match.start()]
                            if 'csrf_token' not in form_content:
                                warnings.append(f"❌ [Missing CSRF] {file}: Form a partir da linha {content[:start_idx].count('\\n') + 1}")
                except Exception as e:
                    warnings.append(f"⚠️ Erro ao ler {file}: {e}")
    
    if warnings:
        for w in warnings:
            print(w)
        return False
    print("✅ CSRF Check OK")
    return True

def check_static_assets():
    print("\n🔍 [2/3] Verificando integridade de Assets (CSS/JS/Imagens)...")
    template_dir = 'src/templates'
    static_dir = 'src/static'
    missing_assets = []
    
    # Regex to find url_for('static', filename='...')
    # Supports single or double quotes
    regex = r"url_for\s*\(\s*['\"]static['\"]\s*,\s*filename\s*=\s*['\"]([^'\"]+)['\"]\s*\)"
    
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    matches = re.finditer(regex, content)
                    for m in matches:
                        asset_path = m.group(1)
                        full_audit_path = os.path.join(static_dir, asset_path)
                        
                        # Handle potential query params in filename if any (uncommon in static but possible)
                        clean_path = full_audit_path.split('?')[0]
                        
                        if not os.path.exists(clean_path):
                            missing_assets.append(f"❌ [Missing Asset] {file}: referenciou '{asset_path}' que não existe em {static_dir}")
                            
                except Exception as e:
                    print(f"Erro ao ler {file} para assets: {e}")

    if missing_assets:
        for m in missing_assets:
            print(m)
        return False
    print("✅ Static Assets Check OK")
    return True

def check_jinja_syntax():
    print("\n🔍 [3/3] Verificando Sintaxe Jinja2...")
    env = app.jinja_env
    template_dir = 'src/templates'
    errors = []
    
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    env.parse(content)
                except Exception as e:
                    errors.append(f"❌ [Jinja Syntax Error] {file}: {e}")

    if errors:
        for e in errors:
            print(e)
        return False
    print("✅ Jinja2 Syntax Check OK")
    return True

if __name__ == "__main__":
    ok_csrf = check_templates_for_csrf()
    ok_assets = check_static_assets()
    ok_jinja = check_jinja_syntax()
    
    if not (ok_csrf and ok_assets and ok_jinja):
        print("\n❌ Audit falhou! Corrija os erros acima.")
        sys.exit(1)
    
    print("\n🚀 Codebase saudável (Static Audit Passed)!")
