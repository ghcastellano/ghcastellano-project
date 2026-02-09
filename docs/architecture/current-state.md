# Arquitetura Atual - MVP Inspeção Sanitária

## Visão Geral

Sistema de gestão de inspeções sanitárias construído em Flask, com processamento de PDFs via OpenAI e integração com Google Drive.

## Stack Tecnológico

| Componente | Tecnologia |
|------------|------------|
| Backend | Python 3.11 + Flask |
| Banco de Dados | PostgreSQL (Neon.tech) |
| ORM | SQLAlchemy 2.0 |
| AI Processing | OpenAI GPT-4o-mini |
| Storage | Google Drive + Cloud Storage |
| PDF Generation | WeasyPrint |
| Authentication | Flask-Login |
| Deployment | Google Cloud Run |

## Estrutura de Diretórios

```
src/
├── app.py                    # Aplicação Flask principal (2078 linhas)
├── auth.py                   # Autenticação e login
├── admin_routes.py           # Rotas administrativas
├── manager_routes.py         # Rotas do gestor
├── models_db.py              # Modelos SQLAlchemy
├── database.py               # Conexão com banco
├── db_queries.py             # Queries utilitárias
├── config.py                 # Configurações
├── services/
│   ├── processor.py          # Processamento de PDF + AI
│   ├── drive_service.py      # Google Drive API
│   ├── email_service.py      # Envio de emails
│   ├── pdf_service.py        # Geração de PDFs
│   ├── storage_service.py    # Cloud Storage
│   ├── sync_service.py       # Sincronização Drive
│   └── approval_service.py   # Fluxo de aprovação
├── infrastructure/
│   └── security/
│       └── file_validator.py # Validação de arquivos
└── templates/                # Templates Jinja2
```

## Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────┐
│                    FLUXO DE INSPEÇÃO                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. UPLOAD                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────┐   │
│  │ Consultor│───▶│ FileValidator│───▶│ ProcessorService│   │
│  │  (PDF)   │    │ (magic bytes)│    │   (OpenAI)      │   │
│  └──────────┘    └──────────────┘    └────────┬────────┘   │
│                                               │             │
│  2. PROCESSAMENTO                             ▼             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Job (PROCESSING) → Inspection → ActionPlan → Items   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                               │             │
│  3. REVISÃO                                   ▼             │
│  ┌──────────┐    ┌─────────────────┐                       │
│  │  Gestor  │───▶│ manager_routes  │                       │
│  │ (Review) │    │ (edit/approve)  │                       │
│  └──────────┘    └────────┬────────┘                       │
│                           │                                 │
│  4. APROVAÇÃO             ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ApprovalService → PDF Generation → Email/WhatsApp   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Modelos de Dados

### User
- Roles: CONSULTANT, MANAGER, ADMIN
- Relacionamentos: Company, Establishments

### Company
- Agrupa Establishments e Users
- Possui pasta no Drive

### Establishment
- Loja/Unidade de uma Company
- Pode ter múltiplos Consultants

### Inspection
- Representa um relatório de inspeção
- Status: PROCESSING → PENDING_MANAGER_REVIEW → APPROVED → COMPLETED
- Guarda `ai_raw_response` (resposta original da IA)

### ActionPlan
- Plano de ação gerado para uma Inspection
- Contém múltiplos ActionPlanItems

### ActionPlanItem
- Item individual do plano
- Preserva dados originais da IA para fine-tuning:
  - `original_status`
  - `original_score`
  - `ai_suggested_deadline`

### Job
- Estado de processamento assíncrono
- Rastreia custo (tokens, USD, BRL)

## Segurança Implementada

### Validação de Arquivos
- Magic bytes validation (não apenas extensão)
- Limite de tamanho (50MB PDF, 10MB imagens)
- Validação de estrutura PDF (header, EOF, xref)

### Rate Limiting
- Login: 5 tentativas/minuto por IP
- Upload PDF: 10/minuto por IP
- Upload evidência: 20/minuto por IP

### Autenticação
- Flask-Login com sessões
- CSRF protection (Flask-WTF)
- Cookies seguros em produção

### Debug Endpoints
- Desabilitados em produção (K_SERVICE check)

## Limitações Atuais

1. **Arquivos monolíticos**: app.py com 2078 linhas
2. **Threading**: Usa threading.Thread em vez de task queue
3. **Acoplamento**: Services diretamente importados
4. **Testes**: Cobertura ainda em expansão

## Próximos Passos (Clean Architecture)

Ver plano em `/docs/architecture/adr/001-security-first.md`
