# Plano de Design Mobile-Responsive — InspetorAI

> **Objetivo**: Transformar todas as páginas web do InspetorAI em experiências mobile-first com UI/UX modernas, criando versões dedicadas para celular que detectam o dispositivo automaticamente e entregam uma interface otimizada para toque e telas pequenas, mantendo total congruência visual com a versão desktop.

---

## 1. Arquitetura da Solução

### 1.1 Estratégia: Detecção de Dispositivo + Templates Dedicados

Em vez de apenas media queries (que limitam a UX mobile), a abordagem será:

```
Requisição HTTP
    │
    ▼
Middleware Flask (detect_mobile)
    │
    ├── Desktop → templates originais (sem mudanças)
    │
    └── Mobile → templates mobile/ dedicados
         (mesmos dados, UI otimizada para toque)
```

**Por que templates dedicados?**
- Os templates desktop são densos (tabelas, sidebars, grids complexos) — media queries sozinhas não resolvem
- Mobile precisa de padrões UX diferentes: bottom navigation, cards empilhados, swipe actions, sheets
- Manter os templates desktop intactos evita regressões

### 1.2 Estrutura de Arquivos

```
src/
├── templates/
│   ├── layout.html                    # Desktop layout (INTOCADO)
│   ├── mobile/                        # NOVO — Templates mobile
│   │   ├── layout_mobile.html         # Layout base mobile
│   │   ├── login_mobile.html          # Login mobile
│   │   ├── change_password_mobile.html
│   │   ├── dashboard_consultant_mobile.html
│   │   ├── dashboard_manager_mobile.html
│   │   ├── admin_dashboard_mobile.html
│   │   ├── manager_plan_edit_mobile.html
│   │   └── review_mobile.html
│   │
├── static/
│   ├── style.css                      # Desktop CSS (INTOCADO)
│   ├── mobile.css                     # NOVO — CSS mobile completo
│   └── mobile.js                      # NOVO — JS mobile (gestos, menus, interações)
│
├── mobile_detector.py                 # NOVO — Middleware detecção mobile
├── mobile_helpers.py                  # NOVO — Helper para render mobile/desktop
```

---

## 2. Componentes do Sistema

### 2.1 Middleware de Detecção Mobile (`mobile_detector.py`)

```python
# Detecta via User-Agent + tela (fallback com cookie)
# Seta request.is_mobile = True/False
# Permite override via ?desktop=1 ou ?mobile=1
```

**Lógica:**
- Verifica User-Agent para padrões mobile (iPhone, Android, etc.)
- Usuário pode forçar versão via query param `?view=desktop` / `?view=mobile`
- Armazena preferência em cookie `preferred_view`

### 2.2 Helper de Renderização (`mobile_helpers.py`)

```python
def render_adaptive(desktop_template, mobile_template, **context):
    """Renderiza template mobile ou desktop baseado no dispositivo."""
    if request.is_mobile:
        return render_template(f"mobile/{mobile_template}", **context)
    return render_template(desktop_template, **context)
```

### 2.3 Layout Mobile Base (`layout_mobile.html`)

**Estrutura:**
```
┌─────────────────────────┐
│  Status Bar (nome + avatar) │  ← Header compacto 56px
├─────────────────────────┤
│                         │
│                         │
│    Conteúdo Principal   │  ← Scroll area
│    (cards, listas)      │
│                         │
│                         │
├─────────────────────────┤
│ 🏠  📋  ➕  👤         │  ← Bottom Navigation Bar
└─────────────────────────┘
```

**Design System Mobile:**
- **Fontes**: Mesmas (Outfit + Inter), tamanhos ajustados
- **Cores**: Idênticas ao desktop (--primary, --accent, etc.)
- **Border Radius**: Mantidos (16px cards, 8px buttons)
- **Glassmorphism**: Mantido no header e bottom bar
- **Sombras**: Sutilizadas para performance
- **Touch targets**: Mínimo 44x44px em todos os interativos
- **Espaçamento**: Padding 16px lateral padrão

---

## 3. Detalhamento por Página

### 3.1 Login Mobile (`login_mobile.html`)

**Atual (Desktop):** Split-screen com imagem à esquerda + form à direita
**Mobile:**
- Full-screen com gradiente sutil no topo
- Logo InspetorAI centralizado
- Card de login centralizado com cantos arredondados
- Inputs com altura 48px (touch-friendly)
- Botão "Entrar" full-width, 52px altura
- Teclado não sobrepõe campos (viewport handling)
- Link "Esqueceu a senha?" como texto abaixo do botão

### 3.2 Troca de Senha Mobile (`change_password_mobile.html`)

**Atual:** Card centralizado (já razoável para mobile)
**Mobile:**
- Mesmo design, padding reduzido para 16px
- Inputs touch-friendly (48px)
- Indicadores de requisitos da senha maiores e mais claros
- Botão full-width

### 3.3 Dashboard Consultor Mobile (`dashboard_consultant_mobile.html`)

**Atual (Desktop):** Stats grid 3 colunas + tabela de vistorias + área de upload

**Mobile — Redesign completo:**

```
┌───────────────────────────┐
│ Bom dia, Maria ☀️         │  Header com saudação
│ 12 de fev, 2026           │
├───────────────────────────┤
│                           │
│ ┌─────┐ ┌─────┐ ┌─────┐ │  Stats: scroll horizontal
│ │  3  │ │  1  │ │  5  │ │  (cards compactos)
│ │Pend.│ │Proc.│ │Done │ │
│ └─────┘ └─────┘ └─────┘ │
│                           │
│ ┌─────────────────────── │  Upload: área touch
│ │ 📎 Toque para enviar  │ │  com drag-drop adaptado
│ │    relatório PDF       │ │
│ └─────────────────────── │
│                           │
│ Minhas Vistorias          │  Lista de cards
│ ┌───────────────────────┐│  (substitui tabela)
│ │ Rest. Bom Sabor       ││
│ │ 📅 10/02 · 🟢 85%    ││
│ │ Status: Aprovado    → ││
│ └───────────────────────┘│
│ ┌───────────────────────┐│
│ │ Padaria Central       ││
│ │ 📅 08/02 · 🟡 62%    ││
│ │ Status: Pendente    → ││
│ └───────────────────────┘│
│                           │
├───────────────────────────┤
│  🏠    📋    ➕    👤    │  Bottom nav
└───────────────────────────┘
```

**Mudanças-chave:**
- Stats: horizontal scroll (snap) em vez de grid
- Tabela → Cards empilhados (cada vistoria = 1 card)
- Upload: área simplificada com ícone grande
- Paginação: infinite scroll ou "Carregar mais"
- Filtros: bottom sheet em vez de dropdowns inline

### 3.4 Dashboard Gestor Mobile (`dashboard_manager_mobile.html`)

**Atual (Desktop):** Sidebar 280px + conteúdo com tabelas, modals, edição inline

**Mobile — Redesign completo:**

```
┌───────────────────────────┐
│ InspetorAI    [☰] [🔔]   │  Header com hamburger menu
├───────────────────────────┤
│                           │
│ [Todos] [Pendentes] [✓]  │  Filtros: pill tabs scrolláveis
│                           │
│ Seletor de Estabelecimento│  Dropdown ou bottom sheet
│ ▼ Rest. Bom Sabor         │
│                           │
│ ┌───────────────────────┐ │
│ │ Inspeção #42          │ │  Cards com swipe actions
│ │ 📅 10/02  Score: 85%  │ │  ← swipe: aprovar
│ │ Consultor: João       │ │  → swipe: ver plano
│ │ [Pendente Revisão]    │ │
│ └───────────────────────┘ │
│                           │
│ ┌───────────────────────┐ │
│ │ Inspeção #41          │ │
│ │ ...                   │ │
│ └───────────────────────┘ │
│                           │
├───────────────────────────┤
│  📊    📋    ➕    👤    │
└───────────────────────────┘
```

**Sidebar → Hamburger menu (slide-in):**
- Menu lateral deslizante com overlay escuro
- Mesmas seções: Consultores, Estabelecimentos, Vistorias
- Gestão de consultores e estabelecimentos via formulários full-screen

**Tabelas → Cards:**
- Cada inspeção é um card com info essencial
- Tap para expandir/ver detalhes
- Ações (aprovar, compartilhar) via menu contextual ou bottom sheet

### 3.5 Admin Dashboard Mobile (`admin_dashboard_mobile.html`)

**Atual (Desktop):** Sidebar + multi-seções (Overview, Empresas, Gestores, Monitoramento, Logs, Config)

**Mobile:**

```
┌───────────────────────────┐
│ Admin Panel       [☰]     │
├───────────────────────────┤
│                           │
│ Stats Overview             │  Cards em grid 2x2
│ ┌──────┐ ┌──────┐        │
│ │ 12   │ │  3   │        │
│ │Empres│ │Gestor│        │
│ └──────┘ └──────┘        │
│ ┌──────┐ ┌──────┐        │
│ │ 847  │ │  5   │        │
│ │Jobs  │ │Erros │        │
│ └──────┘ └──────┘        │
│                           │
│ Seções                    │  Lista de seções (links)
│ ┌───────────────────────┐ │
│ │ 🏢 Empresas        → │ │
│ ├───────────────────────┤ │
│ │ 👤 Gestores        → │ │
│ ├───────────────────────┤ │
│ │ 📊 Monitoramento   → │ │
│ ├───────────────────────┤ │
│ │ 🔧 Configurações   → │ │
│ └───────────────────────┘ │
│                           │
├───────────────────────────┤
│  📊    🏢    ⚙️    👤    │
└───────────────────────────┘
```

**Cada seção → página full-screen com back button**
- Empresas: lista de cards, tap para expandir
- Gestores: lista com avatar + info
- Monitoramento: cards com status de jobs
- Configurações: formulário full-width

### 3.6 Edição de Plano (Gestor) Mobile (`manager_plan_edit_mobile.html`)

**Atual (Desktop):** Stepper + resumo + tabela de itens com edição inline + botões de ação

**Mobile:**

```
┌───────────────────────────┐
│ ← Validação do Plano      │  Header com back button
├───────────────────────────┤
│ ●───●───○  Etapa 1/3      │  Stepper compacto
├───────────────────────────┤
│                           │
│ 📊 Resumo                 │  Collapsible summary
│ Score: 85% | Itens: 12    │
│                           │
│ Itens do Plano            │
│ ┌───────────────────────┐ │  Cada item = card expandível
│ │ 🔴 Item crítico       │ │
│ │ Controle de pragas    │ │
│ │ Prazo: 15/03/2026     │ │
│ │ [Editar] [Resolver]   │ │
│ └───────────────────────┘ │
│ ┌───────────────────────┐ │
│ │ 🟡 Item médio         │ │
│ │ Higiene de mãos       │ │
│ │ Prazo: 20/03/2026     │ │
│ │ [Editar] [Resolver]   │ │
│ └───────────────────────┘ │
│                           │
│ ┌───────────────────────┐ │
│ │ ✅ Aprovar Plano      │ │  Floating action button
│ └───────────────────────┘ │
│                           │
└───────────────────────────┘
```

**Edição de item:** Bottom sheet (slide up) com form de edição
**Aprovar:** Confirmação via bottom sheet modal
**Compartilhar (WhatsApp/Email):** Share sheet nativo do dispositivo

### 3.7 Review/Verificação (Consultor) Mobile (`review_mobile.html`)

**Atual (Desktop):** Stepper + resumo + itens com evidências + finalizar

**Mobile:**

```
┌───────────────────────────┐
│ ← Verificação Técnica     │
├───────────────────────────┤
│ ●───●───○  Visita 2/3     │  Stepper
├───────────────────────────┤
│                           │
│ 📊 Resumo [▼ expandir]   │
│                           │
│ Itens para Verificar      │
│ ┌───────────────────────┐ │
│ │ Controle de pragas    │ │
│ │ 🔴 Crítico            │ │
│ │                       │ │
│ │ 📎 Adicionar evidência│ │  Botão que abre câmera
│ │ 📷 foto_001.jpg  [×]  │ │  ou galeria
│ │                       │ │
│ │ 💬 Observação:        │ │
│ │ [__________________] │ │
│ └───────────────────────┘ │
│                           │
│ ┌───────────────────────┐ │
│ │ ✅ Finalizar Verificação│ │
│ └───────────────────────┘ │
└───────────────────────────┘
```

**Upload de evidências:** Integração direta com câmera do celular
**Observações:** Textarea expansível com auto-resize

---

## 4. Design System Mobile

### 4.1 CSS Variables (mobile.css)

```css
:root {
    /* Mesmas cores do desktop — congruência total */
    --primary-color: #0F172A;
    --accent-color: #4F46E5;
    --success-color: #10B981;
    --warning-color: #F59E0B;
    --danger-color: #EF4444;

    /* Mobile-specific spacing */
    --mobile-padding: 16px;
    --mobile-header-height: 56px;
    --mobile-bottom-nav-height: 64px;
    --mobile-safe-area-bottom: env(safe-area-inset-bottom, 0px);
    --mobile-touch-target: 44px;

    /* Mobile typography */
    --mobile-font-size-xs: 0.75rem;
    --mobile-font-size-sm: 0.875rem;
    --mobile-font-size-base: 1rem;
    --mobile-font-size-lg: 1.125rem;
    --mobile-font-size-xl: 1.25rem;
    --mobile-font-size-2xl: 1.5rem;
}
```

### 4.2 Componentes Mobile Reutilizáveis

| Componente | Descrição |
|---|---|
| **Mobile Header** | Glassmorphism, 56px, logo + avatar + menu |
| **Bottom Navigation** | 4 tabs, ícones Phosphor, indicador ativo |
| **Card Mobile** | Border-radius 16px, padding 16px, shadow suave |
| **Bottom Sheet** | Slide-up modal para ações e formulários |
| **Pill Tabs** | Filtros horizontais scrolláveis |
| **Action Button** | FAB (Floating Action Button) para ação primária |
| **Toast Mobile** | Notificações no topo, full-width |
| **Skeleton Loader** | Loading state animado para cards |
| **Pull-to-Refresh** | Puxar para atualizar (JS nativo) |
| **Swipe Actions** | Deslizar cards para ações rápidas |

### 4.3 Animações

```css
/* Entrada de página */
@keyframes slideUp { from { transform: translateY(20px); opacity: 0; } }

/* Bottom sheet */
@keyframes slideInBottom { from { transform: translateY(100%); } }

/* Card appear */
@keyframes fadeInUp {
    from { transform: translateY(10px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}
```

### 4.4 Gestos (mobile.js)

- **Pull-to-refresh**: Puxar para baixo atualiza a página
- **Swipe horizontal**: Em cards de inspeção para ações rápidas
- **Long press**: Em itens para menu contextual
- **Bottom sheet drag**: Arrastar sheet para fechar

---

## 5. Plano de Implementação

### Fase 1: Infraestrutura (Fundação)
1. Criar `mobile_detector.py` (middleware de detecção)
2. Criar `mobile_helpers.py` (helper de renderização)
3. Registrar middleware no `app.py`
4. Criar `static/mobile.css` (design system mobile)
5. Criar `static/mobile.js` (interações mobile)
6. Criar `templates/mobile/layout_mobile.html` (layout base)

### Fase 2: Páginas de Autenticação
7. Criar `templates/mobile/login_mobile.html`
8. Criar `templates/mobile/change_password_mobile.html`
9. Atualizar rotas em `auth.py` para usar `render_adaptive`

### Fase 3: Dashboard Consultor
10. Criar `templates/mobile/dashboard_consultant_mobile.html`
11. Atualizar rota em `app.py` para usar `render_adaptive`

### Fase 4: Dashboard Gestor
12. Criar `templates/mobile/dashboard_manager_mobile.html`
13. Atualizar rotas em `manager_routes.py` para usar `render_adaptive`

### Fase 5: Dashboard Admin
14. Criar `templates/mobile/admin_dashboard_mobile.html`
15. Atualizar rotas em `admin_routes.py` para usar `render_adaptive`

### Fase 6: Páginas de Detalhe
16. Criar `templates/mobile/manager_plan_edit_mobile.html`
17. Criar `templates/mobile/review_mobile.html`
18. Atualizar rotas correspondentes

### Fase 7: Polimento e Testes
19. Testar em Chrome DevTools (iPhone SE, iPhone 14, Pixel 7, Galaxy S21)
20. Ajustar safe areas para iPhone (notch/dynamic island)
21. Testar orientação landscape
22. Testar com teclado virtual aberto
23. Verificar performance (Lighthouse mobile)
24. Link "Ver versão desktop" no footer mobile
25. Link "Ver versão mobile" no footer desktop (quando detectado mobile)

---

## 6. Princípios de UX Mobile

1. **Touch-first**: Todos os alvos de toque >= 44x44px
2. **Thumb zone**: Ações primárias na parte inferior da tela
3. **Progressive disclosure**: Mostrar resumo, expandir sob demanda
4. **Offline-aware**: Feedback visual quando sem conexão
5. **Performance**: CSS mínimo, lazy loading de conteúdo
6. **Accessibility**: Contraste AA, font-size mínimo 14px, focus visible
7. **Congruência visual**: Mesmas cores, fontes, e linguagem visual do desktop
8. **Feedback tátil**: Ripple effects em botões, estados de loading visíveis

---

## 7. Rotas que Precisam de Atualização

| Arquivo | Rota | Template Desktop | Template Mobile |
|---|---|---|---|
| `auth.py` | `/auth/login` | `login.html` | `mobile/login_mobile.html` |
| `auth.py` | `/auth/change-password` | `change_password.html` | `mobile/change_password_mobile.html` |
| `app.py` | `/dashboard/consultant` | `dashboard_consultant.html` | `mobile/dashboard_consultant_mobile.html` |
| `manager_routes.py` | `/manager/dashboard/manager` | `dashboard_manager_v2.html` | `mobile/dashboard_manager_mobile.html` |
| `admin_routes.py` | `/admin/` | `admin_dashboard.html` | `mobile/admin_dashboard_mobile.html` |
| `manager_routes.py` | `/manager/plan/<file_id>` | `manager_plan_edit.html` | `mobile/manager_plan_edit_mobile.html` |
| `app.py` | `/review/<file_id>` | `review.html` | `mobile/review_mobile.html` |

---

## 8. Decisões Técnicas

| Decisão | Escolha | Justificativa |
|---|---|---|
| Templates separados vs Media queries | Templates separados | UX fundamentalmente diferente entre desktop/mobile |
| Detecção server-side vs client-side | Server-side (User-Agent) + override | Evita flash/layout shift no cliente |
| Framework CSS mobile | CSS puro + variáveis | Manter stack leve, sem dependência nova |
| Bottom navigation vs hamburger | Bottom nav (4 tabs) | Padrão mobile moderno, acesso com polegar |
| Tabelas mobile | Cards empilhados | Tabelas não funcionam bem em < 768px |
| Modals mobile | Bottom sheets | Mais natural e acessível em mobile |
| Abordagem de build | Zero build step | Mantém simplicidade do Flask + Jinja2 |
