# Prompt de Execução — Mobile Responsive InspetorAI

> **INSTRUÇÃO**: Este documento é o guia completo para o Claude no VSCode executar a implementação mobile do InspetorAI. Leia este arquivo inteiro antes de começar. Siga fase por fase, testando cada etapa.

---

## Contexto do Projeto

Este é um web app Flask (Python) para gestão de inspeções sanitárias com IA. O app usa:
- **Flask** como framework web (server-side rendering com Jinja2)
- **Bootstrap 5** + **CSS customizado** (variáveis CSS, glassmorphism)
- **Phosphor Icons** + **FontAwesome 6.4**
- **Google Fonts**: Outfit (headings) + Inter (body)
- **PostgreSQL** via SQLAlchemy
- **Flask-Login** para autenticação com roles: ADMIN, MANAGER, CONSULTANT

### Estrutura Atual
```
src/
├── app.py              # Rotas principais (dashboard_consultant, review, upload)
├── auth.py             # Blueprint auth (login, logout, change_password)
├── admin_routes.py     # Blueprint admin
├── manager_routes.py   # Blueprint manager
├── templates/
│   ├── layout.html                    # Layout base desktop
│   ├── login.html                     # Login (standalone, usa Tailwind CDN)
│   ├── change_password.html           # Troca de senha (standalone)
│   ├── register.html                  # Registro (standalone)
│   ├── dashboard_consultant.html      # Dashboard consultor (1094 linhas)
│   ├── dashboard_manager_v2.html      # Dashboard gestor (1886 linhas)
│   ├── admin_dashboard.html           # Painel admin (1693 linhas)
│   ├── manager_plan_edit.html         # Edição de plano (681 linhas)
│   └── review.html                    # Verificação técnica (931 linhas)
├── static/
│   ├── style.css       # CSS principal (design system completo)
│   ├── app.css         # CSS adicional
│   └── pagination.js   # Componente de paginação
```

### Design System Atual (MANTER CONGRUÊNCIA)
```css
--primary-color: #0F172A;    /* Slate 900 */
--accent-color: #4F46E5;     /* Indigo 600 (layout) / #3B82F6 Blue 500 (style.css) */
--success-color: #10B981;    /* Emerald 500 */
--warning-color: #F59E0B;    /* Amber 500 */
--danger-color: #EF4444;     /* Red 500 */
--bg-body: #F8FAFC;          /* Slate 50 */
--text-primary: #1E293B;
--text-secondary: #64748B;
--text-light: #94A3B8;
--border-color: #E2E8F0;
```
**Fontes**: `'Outfit', sans-serif` para headings, `'Inter', sans-serif` para body
**Ícones**: Phosphor Icons (`ph-fill`, `ph-bold`) + FontAwesome (`fas`, `far`)
**Estilo**: Glassmorphism (backdrop-filter blur), cantos arredondados (8-16px), sombras suaves

---

## FASE 1: Infraestrutura (COMEÇAR AQUI)

### 1.1 Criar `src/mobile_detector.py`

```python
"""Middleware para detecção de dispositivos mobile."""
import re
from flask import request


MOBILE_USER_AGENTS = re.compile(
    r'iPhone|iPod|Android.*Mobile|Windows Phone|BlackBerry|Opera Mini|IEMobile|'
    r'Mobile Safari|webOS|Fennec|Minimo|Opera Mobi|Dolfin|Skyfire|Zune',
    re.IGNORECASE
)


def is_mobile_request():
    """Detecta se a requisição vem de um dispositivo mobile.

    Prioridade:
    1. Query param ?view=desktop ou ?view=mobile (override)
    2. Cookie preferred_view (persistência do override)
    3. User-Agent header (detecção automática)
    """
    # 1. Query param override
    view_param = request.args.get('view')
    if view_param in ('desktop', 'mobile'):
        return view_param == 'mobile'

    # 2. Cookie override
    preferred = request.cookies.get('preferred_view')
    if preferred in ('desktop', 'mobile'):
        return preferred == 'mobile'

    # 3. User-Agent detection
    user_agent = request.headers.get('User-Agent', '')
    return bool(MOBILE_USER_AGENTS.search(user_agent))


def init_mobile_detection(app):
    """Registra o middleware de detecção mobile no app Flask."""

    @app.before_request
    def detect_mobile():
        request.is_mobile = is_mobile_request()

    @app.after_request
    def set_view_cookie(response):
        view_param = request.args.get('view')
        if view_param in ('desktop', 'mobile'):
            response.set_cookie(
                'preferred_view',
                view_param,
                max_age=30 * 24 * 3600,  # 30 dias
                httponly=True,
                samesite='Lax'
            )
        return response

    @app.context_processor
    def inject_mobile_flag():
        return {'is_mobile': getattr(request, 'is_mobile', False)}
```

### 1.2 Criar `src/mobile_helpers.py`

```python
"""Helpers para renderização adaptativa mobile/desktop."""
from flask import request, render_template


def render_adaptive(desktop_template, mobile_template, **context):
    """Renderiza o template apropriado baseado no dispositivo.

    Args:
        desktop_template: Caminho do template desktop (ex: 'dashboard_consultant.html')
        mobile_template: Caminho do template mobile (ex: 'mobile/dashboard_consultant_mobile.html')
        **context: Variáveis de contexto do template
    """
    if getattr(request, 'is_mobile', False):
        try:
            return render_template(mobile_template, **context)
        except Exception:
            # Fallback para desktop se template mobile não existir
            return render_template(desktop_template, **context)
    return render_template(desktop_template, **context)
```

### 1.3 Registrar middleware no `src/app.py`

No topo do arquivo, adicionar o import:
```python
from mobile_detector import init_mobile_detection
```

Na função `create_app()`, logo após a criação do app Flask e antes dos blueprints, adicionar:
```python
# Mobile detection middleware
init_mobile_detection(app)
```

### 1.4 Criar `src/static/mobile.css`

Este é o CSS completo do design system mobile. O arquivo deve conter:

```css
/* =============================================
   InspetorAI — Mobile Design System
   Congruente com desktop (mesmas cores, fontes)
   ============================================= */

/* Google Fonts (mesmas do desktop) */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');

/* =============================================
   CSS Variables — Mobile
   ============================================= */
:root {
    /* Cores — IDÊNTICAS ao desktop */
    --primary-color: #0F172A;
    --primary-light: #1E293B;
    --accent-color: #4F46E5;
    --accent-hover: #4338CA;
    --accent-light: rgba(79, 70, 229, 0.1);
    --success-color: #10B981;
    --success-light: rgba(16, 185, 129, 0.1);
    --warning-color: #F59E0B;
    --warning-light: rgba(245, 158, 11, 0.1);
    --danger-color: #EF4444;
    --danger-light: rgba(239, 68, 68, 0.1);
    --info-color: #0EA5E9;
    --info-light: rgba(14, 165, 233, 0.1);

    --bg-body: #F8FAFC;
    --bg-surface: #FFFFFF;
    --text-primary: #1E293B;
    --text-secondary: #64748B;
    --text-light: #94A3B8;
    --border-color: #E2E8F0;

    --glass-bg: rgba(255, 255, 255, 0.85);
    --glass-border: rgba(255, 255, 255, 0.5);

    /* Sombras */
    --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
    --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05);
    --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.03);
    --shadow-card: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03);

    /* Radius */
    --radius-sm: 6px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-xl: 16px;
    --radius-full: 9999px;

    /* Mobile-specific */
    --mobile-padding: 16px;
    --mobile-header-h: 56px;
    --mobile-bottom-nav-h: 64px;
    --mobile-safe-bottom: env(safe-area-inset-bottom, 0px);
    --mobile-touch-min: 44px;

    /* Transitions */
    --transition-fast: all 0.2s ease;
    --transition-smooth: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* =============================================
   Reset & Base
   ============================================= */
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-tap-highlight-color: transparent;
}

html {
    font-size: 16px;
    -webkit-text-size-adjust: 100%;
    scroll-behavior: smooth;
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: var(--bg-body);
    color: var(--text-primary);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    overflow-x: hidden;
    min-height: 100vh;
    min-height: 100dvh;
    padding-bottom: calc(var(--mobile-bottom-nav-h) + var(--mobile-safe-bottom));
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Outfit', sans-serif;
    color: var(--primary-color);
    font-weight: 600;
    line-height: 1.25;
}

a {
    text-decoration: none;
    color: var(--accent-color);
}

/* =============================================
   Mobile Header
   ============================================= */
.mobile-header {
    position: sticky;
    top: 0;
    z-index: 100;
    height: var(--mobile-header-h);
    background: var(--glass-bg);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border-bottom: 1px solid var(--glass-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--mobile-padding);
    box-shadow: 0 1px 8px rgba(0,0,0,0.03);
}

.mobile-header-brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: 'Outfit', sans-serif;
    font-size: 1.25rem;
    font-weight: 800;
    color: var(--primary-color);
}

.mobile-header-brand span {
    color: var(--accent-color);
}

.mobile-header-brand i {
    font-size: 1.5rem;
    color: var(--accent-color);
}

.mobile-header-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.mobile-header-avatar {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, var(--accent-color) 0%, #7c3aed 100%);
    color: white;
    border-radius: var(--radius-lg);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.95rem;
}

.mobile-header-btn {
    width: 36px;
    height: 36px;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    font-size: 1.25rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: var(--transition-fast);
}

.mobile-header-btn:active {
    background: rgba(0,0,0,0.05);
}

/* =============================================
   Bottom Navigation
   ============================================= */
.mobile-bottom-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 200;
    height: calc(var(--mobile-bottom-nav-h) + var(--mobile-safe-bottom));
    padding-bottom: var(--mobile-safe-bottom);
    background: var(--glass-bg);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border-top: 1px solid var(--glass-border);
    display: flex;
    align-items: center;
    justify-content: space-around;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.03);
}

.mobile-nav-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    min-width: 64px;
    padding: 8px 12px;
    border: none;
    background: transparent;
    color: var(--text-light);
    font-family: 'Inter', sans-serif;
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    cursor: pointer;
    transition: var(--transition-fast);
    text-decoration: none;
    border-radius: var(--radius-md);
}

.mobile-nav-item i {
    font-size: 1.35rem;
    margin-bottom: 1px;
}

.mobile-nav-item.active {
    color: var(--accent-color);
}

.mobile-nav-item.active i {
    color: var(--accent-color);
}

.mobile-nav-item:active {
    transform: scale(0.92);
}

/* =============================================
   Mobile Content
   ============================================= */
.mobile-content {
    padding: var(--mobile-padding);
    padding-top: 1.25rem;
    max-width: 100%;
    overflow-x: hidden;
}

/* =============================================
   Greeting / Hero Section
   ============================================= */
.mobile-greeting {
    margin-bottom: 1.5rem;
}

.mobile-greeting h1 {
    font-size: 1.5rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    margin-bottom: 0.25rem;
}

.mobile-greeting .date-text {
    color: var(--text-secondary);
    font-size: 0.875rem;
    font-weight: 500;
}

/* =============================================
   Stats — Horizontal Scroll
   ============================================= */
.mobile-stats-scroll {
    display: flex;
    gap: 0.75rem;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    padding: 0 0 0.75rem 0;
    margin: 0 calc(var(--mobile-padding) * -1);
    padding-left: var(--mobile-padding);
    padding-right: var(--mobile-padding);
    scrollbar-width: none;
}

.mobile-stats-scroll::-webkit-scrollbar {
    display: none;
}

.mobile-stat-card {
    flex: 0 0 auto;
    width: 140px;
    scroll-snap-align: start;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-xl);
    padding: 1rem;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-card);
}

.mobile-stat-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
}

.mobile-stat-card.stat-accent::before { background: var(--accent-color); }
.mobile-stat-card.stat-success::before { background: var(--success-color); }
.mobile-stat-card.stat-warning::before { background: var(--warning-color); }
.mobile-stat-card.stat-danger::before { background: var(--danger-color); }
.mobile-stat-card.stat-info::before { background: var(--info-color); }

.mobile-stat-label {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-light);
    margin-bottom: 0.5rem;
}

.mobile-stat-value {
    font-family: 'Outfit', sans-serif;
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--primary-color);
    line-height: 1;
}

/* =============================================
   Cards (substitute for tables)
   ============================================= */
.mobile-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-xl);
    padding: 1rem;
    margin-bottom: 0.75rem;
    box-shadow: var(--shadow-card);
    transition: var(--transition-fast);
    display: block;
    color: inherit;
    text-decoration: none;
}

.mobile-card:active {
    transform: scale(0.985);
    box-shadow: var(--shadow-sm);
}

.mobile-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.5rem;
}

.mobile-card-title {
    font-family: 'Outfit', sans-serif;
    font-size: 1rem;
    font-weight: 600;
    color: var(--primary-color);
    line-height: 1.3;
}

.mobile-card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    font-size: 0.8rem;
    color: var(--text-secondary);
}

.mobile-card-meta-item {
    display: flex;
    align-items: center;
    gap: 0.3rem;
}

.mobile-card-meta-item i {
    font-size: 0.85rem;
    color: var(--text-light);
}

.mobile-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border-color);
}

.mobile-card-arrow {
    color: var(--text-light);
    font-size: 1.1rem;
}

/* =============================================
   Badges
   ============================================= */
.mobile-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.6rem;
    border-radius: var(--radius-full);
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.02em;
}

.mobile-badge-success { background: var(--success-light); color: var(--success-color); }
.mobile-badge-warning { background: var(--warning-light); color: var(--warning-color); }
.mobile-badge-danger { background: var(--danger-light); color: var(--danger-color); }
.mobile-badge-accent { background: var(--accent-light); color: var(--accent-color); }
.mobile-badge-info { background: var(--info-light); color: var(--info-color); }
.mobile-badge-neutral { background: rgba(100, 116, 139, 0.1); color: var(--text-secondary); }

/* =============================================
   Buttons
   ============================================= */
.mobile-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    min-height: var(--mobile-touch-min);
    padding: 0.75rem 1.25rem;
    border: none;
    border-radius: var(--radius-lg);
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition-fast);
    text-decoration: none;
}

.mobile-btn:active {
    transform: scale(0.97);
}

.mobile-btn-primary {
    background: var(--primary-color);
    color: white;
}

.mobile-btn-accent {
    background: var(--accent-color);
    color: white;
}

.mobile-btn-success {
    background: var(--success-color);
    color: white;
}

.mobile-btn-danger {
    background: var(--danger-color);
    color: white;
}

.mobile-btn-outline {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-primary);
}

.mobile-btn-ghost {
    background: transparent;
    color: var(--text-secondary);
}

.mobile-btn-full {
    width: 100%;
}

.mobile-btn-sm {
    min-height: 36px;
    padding: 0.5rem 1rem;
    font-size: 0.8rem;
}

/* =============================================
   Forms
   ============================================= */
.mobile-form-group {
    margin-bottom: 1rem;
}

.mobile-form-label {
    display: block;
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 0.4rem;
}

.mobile-form-input {
    width: 100%;
    min-height: 48px;
    padding: 0.75rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    background: var(--bg-surface);
    color: var(--text-primary);
    font-family: inherit;
    font-size: 1rem;
    transition: var(--transition-fast);
    -webkit-appearance: none;
    appearance: none;
}

.mobile-form-input:focus {
    outline: none;
    border-color: var(--accent-color);
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.mobile-form-input::placeholder {
    color: var(--text-light);
}

.mobile-form-select {
    width: 100%;
    min-height: 48px;
    padding: 0.75rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    background: var(--bg-surface);
    color: var(--text-primary);
    font-family: inherit;
    font-size: 1rem;
    -webkit-appearance: none;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 1rem center;
    padding-right: 2.5rem;
}

/* =============================================
   Bottom Sheet
   ============================================= */
.mobile-sheet-overlay {
    position: fixed;
    inset: 0;
    z-index: 300;
    background: rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(2px);
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
}

.mobile-sheet-overlay.active {
    opacity: 1;
    visibility: visible;
}

.mobile-sheet {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 301;
    background: var(--bg-surface);
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
    padding: 0.75rem var(--mobile-padding) calc(var(--mobile-padding) + var(--mobile-safe-bottom));
    max-height: 85vh;
    overflow-y: auto;
    transform: translateY(100%);
    transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.1);
}

.mobile-sheet.active {
    transform: translateY(0);
}

.mobile-sheet-handle {
    width: 36px;
    height: 4px;
    background: var(--border-color);
    border-radius: var(--radius-full);
    margin: 0 auto 1rem;
}

.mobile-sheet-title {
    font-family: 'Outfit', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--primary-color);
    margin-bottom: 1rem;
}

/* =============================================
   Pill Tabs (horizontal filters)
   ============================================= */
.mobile-pill-tabs {
    display: flex;
    gap: 0.5rem;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    padding-bottom: 0.5rem;
    margin-bottom: 1rem;
    scrollbar-width: none;
}

.mobile-pill-tabs::-webkit-scrollbar {
    display: none;
}

.mobile-pill-tab {
    flex: 0 0 auto;
    scroll-snap-align: start;
    padding: 0.5rem 1rem;
    border-radius: var(--radius-full);
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-secondary);
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    cursor: pointer;
    transition: var(--transition-fast);
    white-space: nowrap;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
}

.mobile-pill-tab.active {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
}

.mobile-pill-tab:active {
    transform: scale(0.95);
}

/* =============================================
   Section Header
   ============================================= */
.mobile-section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.mobile-section-title {
    font-family: 'Outfit', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--primary-color);
}

.mobile-section-action {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--accent-color);
    cursor: pointer;
}

/* =============================================
   Upload Area Mobile
   ============================================= */
.mobile-upload-area {
    border: 2px dashed var(--border-color);
    border-radius: var(--radius-xl);
    padding: 2rem 1rem;
    text-align: center;
    background: rgba(79, 70, 229, 0.02);
    margin-bottom: 1.5rem;
    transition: var(--transition-fast);
    cursor: pointer;
}

.mobile-upload-area:active {
    border-color: var(--accent-color);
    background: rgba(79, 70, 229, 0.05);
}

.mobile-upload-area i {
    font-size: 2.5rem;
    color: var(--accent-color);
    margin-bottom: 0.75rem;
    display: block;
}

.mobile-upload-area .upload-text {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.25rem;
}

.mobile-upload-area .upload-hint {
    font-size: 0.8rem;
    color: var(--text-secondary);
}

/* =============================================
   Stepper (process status)
   ============================================= */
.mobile-stepper {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    padding: 1rem 0;
    margin-bottom: 1rem;
}

.mobile-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
    position: relative;
    flex: 1;
}

.mobile-step-circle {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.8rem;
    z-index: 1;
    border: 2px solid var(--border-color);
    background: var(--bg-surface);
    color: var(--text-light);
}

.mobile-step.completed .mobile-step-circle {
    background: var(--success-color);
    border-color: var(--success-color);
    color: white;
}

.mobile-step.current .mobile-step-circle {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
}

.mobile-step-label {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--text-light);
}

.mobile-step.completed .mobile-step-label { color: var(--success-color); }
.mobile-step.current .mobile-step-label { color: var(--accent-color); }

.mobile-step-line {
    position: absolute;
    top: 16px;
    left: 50%;
    width: 100%;
    height: 2px;
    background: var(--border-color);
    z-index: 0;
}

.mobile-step.completed .mobile-step-line {
    background: var(--success-color);
}

.mobile-step:last-child .mobile-step-line {
    display: none;
}

/* =============================================
   Slide-in Menu (hamburger)
   ============================================= */
.mobile-menu-overlay {
    position: fixed;
    inset: 0;
    z-index: 400;
    background: rgba(0, 0, 0, 0.5);
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
}

.mobile-menu-overlay.active {
    opacity: 1;
    visibility: visible;
}

.mobile-slide-menu {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 401;
    width: 280px;
    max-width: 85vw;
    background: var(--bg-surface);
    transform: translateX(-100%);
    transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    overflow-y: auto;
    padding: 1.5rem;
    box-shadow: 4px 0 20px rgba(0,0,0,0.1);
}

.mobile-slide-menu.active {
    transform: translateX(0);
}

.mobile-menu-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding-bottom: 1.25rem;
    margin-bottom: 1.25rem;
    border-bottom: 1px solid var(--border-color);
}

.mobile-menu-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem;
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: var(--transition-fast);
    text-decoration: none;
    border: none;
    background: transparent;
    width: 100%;
    text-align: left;
}

.mobile-menu-item:active,
.mobile-menu-item.active {
    background: var(--accent-light);
    color: var(--accent-color);
}

.mobile-menu-item i {
    font-size: 1.2rem;
    width: 24px;
    text-align: center;
}

.mobile-menu-section-title {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-light);
    padding: 1rem 0.75rem 0.5rem;
}

/* =============================================
   Empty State
   ============================================= */
.mobile-empty-state {
    text-align: center;
    padding: 3rem 1rem;
}

.mobile-empty-state i {
    font-size: 3rem;
    color: var(--text-light);
    margin-bottom: 1rem;
    display: block;
}

.mobile-empty-state p {
    color: var(--text-secondary);
    font-size: 0.9rem;
}

/* =============================================
   Toast Messages
   ============================================= */
.mobile-toast-container {
    position: fixed;
    top: calc(var(--mobile-header-h) + 8px);
    left: var(--mobile-padding);
    right: var(--mobile-padding);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.mobile-toast {
    padding: 0.75rem 1rem;
    background: var(--bg-surface);
    border-radius: var(--radius-lg);
    display: flex;
    align-items: center;
    gap: 0.75rem;
    box-shadow: var(--shadow-lg);
    border-left: 4px solid var(--accent-color);
    animation: mobileSlideDown 0.3s ease-out;
    transition: all 0.3s ease;
}

.mobile-toast-success { border-left-color: var(--success-color); }
.mobile-toast-warning { border-left-color: var(--warning-color); }
.mobile-toast-error { border-left-color: var(--danger-color); }

.mobile-toast i {
    font-size: 1.25rem;
    flex-shrink: 0;
}

.mobile-toast-success i { color: var(--success-color); }
.mobile-toast-warning i { color: var(--warning-color); }
.mobile-toast-error i { color: var(--danger-color); }

.mobile-toast-text {
    flex: 1;
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-primary);
}

.mobile-toast-close {
    background: none;
    border: none;
    color: var(--text-light);
    font-size: 1rem;
    cursor: pointer;
    padding: 0;
}

/* =============================================
   Floating Action Button (FAB)
   ============================================= */
.mobile-fab {
    position: fixed;
    right: var(--mobile-padding);
    bottom: calc(var(--mobile-bottom-nav-h) + var(--mobile-safe-bottom) + 16px);
    z-index: 150;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: var(--accent-color);
    color: white;
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    box-shadow: 0 4px 16px rgba(79, 70, 229, 0.35);
    cursor: pointer;
    transition: var(--transition-smooth);
}

.mobile-fab:active {
    transform: scale(0.9);
}

/* =============================================
   Collapsible / Accordion
   ============================================= */
.mobile-collapsible-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem;
    cursor: pointer;
    user-select: none;
}

.mobile-collapsible-header i.chevron {
    transition: transform 0.3s ease;
    font-size: 1.1rem;
    color: var(--text-light);
}

.mobile-collapsible-header.expanded i.chevron {
    transform: rotate(180deg);
}

.mobile-collapsible-body {
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.35s ease;
}

.mobile-collapsible-body.expanded {
    max-height: 2000px;
}

/* =============================================
   Score / Progress indicator
   ============================================= */
.mobile-score-ring {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
}

.mobile-score-circle {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    font-size: 0.8rem;
    color: white;
}

/* =============================================
   Loading / Skeleton
   ============================================= */
.mobile-skeleton {
    background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
    background-size: 200% 100%;
    animation: mobileShimmer 1.5s infinite;
    border-radius: var(--radius-md);
}

.mobile-skeleton-card {
    height: 100px;
    margin-bottom: 0.75rem;
    border-radius: var(--radius-xl);
}

.mobile-skeleton-stat {
    width: 140px;
    height: 90px;
    border-radius: var(--radius-xl);
    flex-shrink: 0;
}

/* =============================================
   View toggle (mobile/desktop)
   ============================================= */
.mobile-view-toggle {
    text-align: center;
    padding: 1rem 0 0.5rem;
    margin-top: 1rem;
}

.mobile-view-toggle a {
    font-size: 0.8rem;
    color: var(--text-light);
    text-decoration: underline;
}

/* =============================================
   Animations
   ============================================= */
@keyframes mobileSlideDown {
    from { transform: translateY(-20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

@keyframes mobileSlideUp {
    from { transform: translateY(20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

@keyframes mobileFadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes mobileShimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

/* Stagger animation for card lists */
.mobile-card:nth-child(1) { animation: mobileSlideUp 0.3s ease-out 0.0s both; }
.mobile-card:nth-child(2) { animation: mobileSlideUp 0.3s ease-out 0.05s both; }
.mobile-card:nth-child(3) { animation: mobileSlideUp 0.3s ease-out 0.1s both; }
.mobile-card:nth-child(4) { animation: mobileSlideUp 0.3s ease-out 0.15s both; }
.mobile-card:nth-child(5) { animation: mobileSlideUp 0.3s ease-out 0.2s both; }
.mobile-card:nth-child(6) { animation: mobileSlideUp 0.3s ease-out 0.25s both; }
.mobile-card:nth-child(7) { animation: mobileSlideUp 0.3s ease-out 0.3s both; }
.mobile-card:nth-child(8) { animation: mobileSlideUp 0.3s ease-out 0.35s both; }

/* =============================================
   Utility classes
   ============================================= */
.m-text-center { text-align: center; }
.m-text-right { text-align: right; }
.m-mt-1 { margin-top: 0.5rem; }
.m-mt-2 { margin-top: 1rem; }
.m-mt-3 { margin-top: 1.5rem; }
.m-mb-1 { margin-bottom: 0.5rem; }
.m-mb-2 { margin-bottom: 1rem; }
.m-mb-3 { margin-bottom: 1.5rem; }
.m-p-1 { padding: 0.5rem; }
.m-p-2 { padding: 1rem; }
.m-hidden { display: none !important; }
.m-flex { display: flex; }
.m-flex-col { flex-direction: column; }
.m-gap-1 { gap: 0.5rem; }
.m-gap-2 { gap: 1rem; }
.m-w-full { width: 100%; }
```

### 1.5 Criar `src/static/mobile.js`

```javascript
/**
 * InspetorAI — Mobile Interactions
 */

// =============================================
// Bottom Sheet
// =============================================
function openSheet(sheetId) {
    const overlay = document.getElementById(sheetId + '-overlay');
    const sheet = document.getElementById(sheetId);
    if (overlay) { overlay.classList.add('active'); }
    if (sheet) { sheet.classList.add('active'); }
    document.body.style.overflow = 'hidden';
}

function closeSheet(sheetId) {
    const overlay = document.getElementById(sheetId + '-overlay');
    const sheet = document.getElementById(sheetId);
    if (overlay) { overlay.classList.remove('active'); }
    if (sheet) { sheet.classList.remove('active'); }
    document.body.style.overflow = '';
}

// Close sheet on overlay click
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('mobile-sheet-overlay')) {
        e.target.classList.remove('active');
        const sheetId = e.target.id.replace('-overlay', '');
        const sheet = document.getElementById(sheetId);
        if (sheet) sheet.classList.remove('active');
        document.body.style.overflow = '';
    }
    if (e.target.classList.contains('mobile-menu-overlay')) {
        e.target.classList.remove('active');
        const menu = document.querySelector('.mobile-slide-menu');
        if (menu) menu.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// =============================================
// Slide Menu (Hamburger)
// =============================================
function openMobileMenu() {
    const overlay = document.querySelector('.mobile-menu-overlay');
    const menu = document.querySelector('.mobile-slide-menu');
    if (overlay) overlay.classList.add('active');
    if (menu) menu.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeMobileMenu() {
    const overlay = document.querySelector('.mobile-menu-overlay');
    const menu = document.querySelector('.mobile-slide-menu');
    if (overlay) overlay.classList.remove('active');
    if (menu) menu.classList.remove('active');
    document.body.style.overflow = '';
}

// =============================================
// Collapsible sections
// =============================================
document.addEventListener('click', function(e) {
    const header = e.target.closest('.mobile-collapsible-header');
    if (!header) return;
    const body = header.nextElementSibling;
    header.classList.toggle('expanded');
    body.classList.toggle('expanded');
});

// =============================================
// Toast auto-dismiss
// =============================================
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        var toasts = document.querySelectorAll('.mobile-toast');
        toasts.forEach(function(t) {
            t.style.opacity = '0';
            t.style.transform = 'translateY(-20px)';
            setTimeout(function() { t.remove(); }, 300);
        });
    }, 6000);
});

// =============================================
// Pull to refresh (basic)
// =============================================
(function() {
    var startY = 0;
    var pulling = false;

    document.addEventListener('touchstart', function(e) {
        if (window.scrollY === 0) {
            startY = e.touches[0].clientY;
            pulling = true;
        }
    }, { passive: true });

    document.addEventListener('touchmove', function(e) {
        if (!pulling) return;
        var diff = e.touches[0].clientY - startY;
        if (diff > 80) {
            pulling = false;
            window.location.reload();
        }
    }, { passive: true });

    document.addEventListener('touchend', function() {
        pulling = false;
    }, { passive: true });
})();

// =============================================
// Pill tab switching
// =============================================
function switchPillTab(tabGroup, value) {
    var tabs = document.querySelectorAll('[data-tab-group="' + tabGroup + '"]');
    var contents = document.querySelectorAll('[data-tab-content="' + tabGroup + '"]');

    tabs.forEach(function(tab) {
        tab.classList.toggle('active', tab.dataset.tabValue === value);
    });

    contents.forEach(function(content) {
        if (content.dataset.tabValue === value || value === 'all') {
            content.style.display = '';
        } else {
            content.style.display = 'none';
        }
    });
}

// =============================================
// Page loading overlay (same as desktop)
// =============================================
function showPageLoading() {
    var el = document.getElementById('mobileLoadingOverlay');
    if (el) el.style.display = 'flex';
}

window.addEventListener('pageshow', function(e) {
    if (e.persisted) {
        var el = document.getElementById('mobileLoadingOverlay');
        if (el) el.style.display = 'none';
    }
});
```

### 1.6 Criar `src/templates/mobile/layout_mobile.html`

Este é o layout base que TODOS os templates mobile vão estender. Deve conter:

- DOCTYPE, meta viewport, meta charset
- Google Fonts (Outfit + Inter)
- Phosphor Icons + FontAwesome CDN
- Link para `mobile.css`
- Mobile header com: logo InspetorAI, avatar do usuário, botão menu hamburger
- `{% block content %}` para conteúdo da página
- Flash messages como mobile toasts
- Bottom navigation bar com tabs contextuais por role
- Link para `mobile.js`
- Loading overlay
- Link "Ver versão desktop" no footer

**A bottom nav deve ter tabs diferentes por role:**
- **CONSULTANT**: Início, Vistorias, Upload, Perfil
- **MANAGER**: Início, Planos, Equipe, Perfil
- **ADMIN**: Início, Empresas, Gestores, Config

---

## FASE 2: Páginas de Autenticação

### 2.1 `login_mobile.html`

- Página standalone (NÃO estende layout_mobile)
- Full-screen, gradiente sutil no fundo
- Logo InspetorAI centralizado no topo
- Card branco com border-radius 20px
- Inputs de email e senha com 48px de altura
- Botão "Entrar" full-width, 52px, bg --primary-color
- Spinner de loading ao submeter
- Flash messages como badges coloridos acima do form
- Link "Esqueceu a senha?" abaixo do botão
- CSRF token hidden field
- Sem imagem lateral (remover split-screen do desktop)
- Usar mobile.css para estilos base

### 2.2 `change_password_mobile.html`

- Página standalone (NÃO estende layout_mobile)
- Design similar ao login_mobile mas com 3 campos
- Indicadores de requisitos da senha com ícones Phosphor
- Validação client-side idêntica ao desktop
- Botão full-width

### 2.3 Atualizar rotas em `auth.py`

Substituir `render_template` por `render_adaptive` nas rotas:
- `login`: desktop=`login.html`, mobile=`mobile/login_mobile.html`
- `change_password`: desktop=`change_password.html`, mobile=`mobile/change_password_mobile.html`

---

## FASE 3: Dashboard Consultor Mobile

### 3.1 `dashboard_consultant_mobile.html`

- Estende `mobile/layout_mobile.html`
- Saudação "Bom dia, [nome]" + data atual
- Stats em scroll horizontal (3+ cards): Pendentes, Em processamento, Concluídos
- Área de upload simplificada (ícone grande + texto)
- Lista de vistorias como CARDS (não tabela):
  - Cada card: nome do estabelecimento, data, score com cor, status badge
  - Tap no card → navega para review
- Paginação: botão "Carregar mais" ou scroll infinito
- Filtro de estabelecimento como dropdown no topo

### 3.2 Atualizar rota `dashboard_consultant` em `app.py`

Substituir `render_template` por `render_adaptive`.

---

## FASE 4: Dashboard Gestor Mobile

### 4.1 `dashboard_manager_mobile.html`

- Estende `mobile/layout_mobile.html`
- Saudação + data
- Seletor de estabelecimento (dropdown ou bottom sheet com busca)
- Pill tabs para filtrar: Todos, Pendentes, Aprovados, Concluídos
- Cards de inspeção com:
  - Nome do estabelecimento
  - Data, score, consultor responsável
  - Status badge
  - Tap → navega para manager_plan_edit
- Seções de gestão (Consultores, Estabelecimentos) acessíveis via hamburger menu
- Formulários de criação/edição em bottom sheets

### 4.2 Atualizar rotas em `manager_routes.py`

Substituir `render_template` por `render_adaptive` em:
- `dashboard_manager`
- `manager_plan_edit`

---

## FASE 5: Dashboard Admin Mobile

### 5.1 `admin_dashboard_mobile.html`

- Estende `mobile/layout_mobile.html`
- Stats grid 2x2 (Empresas, Gestores, Jobs, Erros)
- Lista de seções como cards clicáveis:
  - Empresas, Gestores, Monitoramento, Logs, Configurações
- Cada seção expande inline ou navega para sub-view
- Tabelas → Cards empilhados
- Formulários de criação em bottom sheets
- Filtro de empresa como dropdown no topo

### 5.2 Atualizar rotas em `admin_routes.py`

Substituir `render_template` por `render_adaptive`.

---

## FASE 6: Páginas de Detalhe

### 6.1 `manager_plan_edit_mobile.html`

- Estende `mobile/layout_mobile.html`
- Back button no header
- Stepper compacto (3 etapas com ícones)
- Resumo da inspeção colapsável
- Itens do plano como cards expandíveis:
  - Severidade (cor), nome, prazo, status
  - Expandir: detalhes completos + botões de ação
- Edição de item via bottom sheet (form com campos do item)
- Botão "Aprovar Plano" fixo no bottom (acima da bottom nav)
- Compartilhar (WhatsApp/Email) via bottom sheet

### 6.2 `review_mobile.html`

- Estende `mobile/layout_mobile.html`
- Back button no header
- Stepper compacto
- Resumo colapsável
- Itens para verificar como cards:
  - Upload de evidência: botão que abre seletor de arquivo/câmera
  - Campo de observação com auto-resize
  - Status visual (pendente/resolvido)
- Botão "Finalizar Verificação" fixo no bottom

---

## FASE 7: Integração e Testes

### 7.1 Atualizar TODAS as rotas que renderizam templates

Cada rota que usa `render_template` e tem um template mobile correspondente deve ser atualizada para usar `render_adaptive`. A lista completa está no MOBILE_RESPONSIVE_PLAN.md seção 7.

### 7.2 Testes a realizar

1. Abrir Chrome DevTools → Toggle Device Toolbar
2. Testar em: iPhone SE (375px), iPhone 14 (390px), Pixel 7 (412px), Galaxy S21 (360px)
3. Verificar:
   - [ ] Login funciona (submit, flash messages, spinner)
   - [ ] Troca de senha funciona (validação client-side, submit)
   - [ ] Dashboard consultor: stats, lista de vistorias, upload
   - [ ] Dashboard gestor: filtros, cards, navegação para plano
   - [ ] Dashboard admin: seções, formulários, monitoramento
   - [ ] Edição de plano: itens, bottom sheet, aprovar
   - [ ] Review: evidências, observações, finalizar
   - [ ] Bottom navigation funciona em todas as páginas
   - [ ] Hamburger menu abre/fecha
   - [ ] Toast messages aparecem e somem
   - [ ] Link "Ver versão desktop" funciona
   - [ ] Todos os forms enviam CSRF token

### 7.3 Pontos críticos de atenção

- **CSRF**: Todo form mobile DEVE incluir `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />`
- **Safe Area**: iPhone com notch/dynamic island precisa de `env(safe-area-inset-bottom)` no bottom nav
- **Teclado virtual**: Quando input recebe foco, garantir que não fica escondido pelo bottom nav
- **Performance**: Não carregar JS/CSS desktop nos templates mobile
- **Fallback**: Se template mobile não existir, render_adaptive deve cair para desktop
- **Session**: A seleção de estabelecimento (`selected_est_id`) já está na session Flask, mobile usa o mesmo
- **Formulários POST**: Todas as ações (aprovar, salvar, deletar) usam as MESMAS rotas de API do desktop

---

## REGRAS IMPORTANTES

1. **NÃO modifique os templates desktop** — eles devem continuar funcionando exatamente como antes
2. **NÃO adicione novas dependências** — use apenas CSS puro, JS vanilla, e as libs já incluídas (Bootstrap, Phosphor, FontAwesome)
3. **MANTENHA as mesmas rotas de API** — os templates mobile fazem POST/GET para as mesmas URLs
4. **USE as mesmas variáveis Jinja2** — os dados passados pelo backend são os mesmos
5. **SIGA o design system** — mesmas cores, fontes, ícones, linguagem visual
6. **PRIORIZE mobile-first** — tudo deve funcionar bem em tela de 360px ou mais
7. **TESTE cada fase** antes de passar para a próxima
