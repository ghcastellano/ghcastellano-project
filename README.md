# MVP Inspeção Sanitária

Sistema de gestão de inspeções sanitárias com processamento inteligente de PDFs via IA e geração automática de planos de ação.

## 🎯 Visão Geral

Aplicação web para automatizar o processamento de relatórios de inspeção sanitária, gerando planos de ação corretivos via IA e permitindo gestão colaborativa entre consultores, gestores e administradores.

## 🏗️ Arquitetura

### Stack Tecnológica
- **Backend**: Python 3.14 + Flask
- **Banco de Dados**: PostgreSQL (Neon.tech)
- **IA**: OpenAI API (GPT-4o)
- **Storage**: Google Drive API
- **Deploy**: Google Cloud Run (Serverless)

### Estrutura do Projeto
```
mvp-inspecao-sanitaria/
├── src/                    # Código-fonte principal
│   ├── models_db.py       # Modelos SQLAlchemy
│   ├── app.py             # Aplicação Flask principal
│   ├── manager_routes.py  # Rotas para gestores
│   ├── admin_routes.py    # Rotas para administradores
│   └── services/          # Serviços (Drive, PDF, IA)
├── scripts/               # Scripts de migração e utilitários
├── docs/                  # Documentação técnica
└── tests/                 # Testes automatizados
```

## 📊 Modelos de Dados

### Principais Entidades

- **Company**: Empresas clientes
- **Establishment**: Estabelecimentos (lojas, unidades)
- **User**: Usuários (CONSULTANT, MANAGER, ADMIN)
- **Inspection**: Inspeções processadas
- **ActionPlan**: Planos de ação gerados
- **ActionPlanItem**: Itens individuais do plano

### ⚡ Arquitetura ML-Ready para Prazos

> **IMPORTANTE**: O sistema implementa uma estratégia de 3 campos para capturar prazos, permitindo aprendizado futuro da IA.

#### Campos de Prazo em `ActionPlanItem`

| Campo | Tipo | Propósito | Quando Preencher |
|-------|------|-----------|------------------|
| `ai_suggested_deadline` | String | **Sugestão original da IA** (nunca muda) | Ao processar PDF pela primeira vez |
| `deadline_date` | Date | **Prazo estruturado** (dd/mm/yyyy) | Quando gestor define data específica |
| `deadline_text` | Text | **Prazo textual editado** pelo gestor | Quando gestor edita prazo (diferente da IA) |

#### Fluxo de Dados

```
1. IA Processa PDF
   └─> ai_suggested_deadline: "30 dias"

2. Gestor Edita Prazo
   ├─> ai_suggested_deadline: "30 dias" (preservado)
   ├─> deadline_text: "15/02/2026" (captura edição)
   └─> deadline_date: 2026-02-15 (conversão estruturada)

3. Exibição no Template
   └─> Prioridade: deadline_text > deadline_date > ai_suggested_deadline
```

#### Benefícios para ML

- ✅ Preserva sugestões originais para análise
- ✅ Captura correções humanas para treinamento
- ✅ Permite dataset: "IA sugere X → Gestor corrige para Y"

**Documentação Completa**: [`docs/ml_deadline_strategy.md`](docs/ml_deadline_strategy.md)

### Campos de Ordenação

- **`order_index`**: Controle manual da ordem dos itens (adicionado em V15)
- **`created_at`**: Removido propositalmente de `ActionPlanItem` para evitar ordenação automática por timestamp

## 🔄 Migrações

### Scripts Disponíveis

- `migration_add_order.py` - Adiciona coluna `order_index`
- `migration_add_deadline_text.py` - Adiciona coluna `deadline_text`
- `migration_app_config.py` - Cria tabela de configuração

### Como Executar

```bash
cd /caminho/para/mvp-inspecao-sanitaria
python3 scripts/migration_add_order.py
```

## 🚀 Setup Local

### Pré-requisitos
- Python 3.14+
- PostgreSQL (ou usar Neon.tech)
- Credenciais do Google Drive API
- OpenAI API Key

### Instalação

```bash
# 1. Clonar repositório
git clone <repo-url>
cd mvp-inspecao-sanitaria

# 2. Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# ou: venv\Scripts\activate  # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais

# 5. Executar migrações
python3 scripts/migration_app_config.py

# 6. Iniciar aplicação
python3 run_dev.py
```

## 📝 Desenvolvimento

### Diretrizes do Projeto

Consulte [`DIRETRIZES.md`](DIRETRIZES.md) para:
- Regras de idioma (PT-BR)
- Arquitetura Zero Cost
- Gestão de segredos
- Padrões de commit

### Documentação Técnica

- [`docs/ml_deadline_strategy.md`](docs/ml_deadline_strategy.md) - Estratégia ML para prazos
- [`docs/recurrent_issues.md`](docs/recurrent_issues.md) - Problemas recorrentes e soluções

## 🔧 Troubleshooting

### Erro "ModuleNotFoundError: No module named 'src'"

**Solução**: Scripts devem adicionar o diretório raiz ao `sys.path`:

```python
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
```

### Erro "Database Engine is None"

**Solução**: Use contexto Flask ao acessar database:

```python
from src.app import app
with app.app_context():
    # código aqui
```

## 📊 Roadmap ML

1. **Exportação de Dataset** - Script para exportar dados de treinamento
2. **Dashboard de Análise** - Visualizar padrões de correção
3. **Fine-tuning** - Treinar modelo com dados capturados

## 👥 Contribuindo

Consulte [`CONTRIBUTING.md`](CONTRIBUTING.md) para guidelines de contribuição.

## 📄 Licença

Propriedade de ghcastellano-group. Todos os direitos reservados.

---

**Última Atualização**: 19/01/2026 - Implementação de arquitetura ML-ready para campos de prazo
