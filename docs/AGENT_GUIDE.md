# Guia para Agentes - MVP Inspeção Sanitária

> **Objetivo**: Este documento orienta agentes de IA e desenvolvedores sobre como trabalhar neste projeto, explicando decisões arquiteturais e padrões implementados.

## 📋 Índice

1. [Princípios do Projeto](#princípios-do-projeto)
2. [Arquitetura de Dados](#arquitetura-de-dados)
3. [Padrões de Código](#padrões-de-código)
4. [Migrações de Banco](#migrações-de-banco)
5. [Estratégia ML-Ready](#estratégia-ml-ready)
6. [Troubleshooting Comum](#troubleshooting-comum)

---

## 🎯 Princípios do Projeto

### 1. Idioma: **Português (PT-BR)**
- Código, commits, documentação e interações devem ser em português
- Exceção: nomes de variáveis/funções em inglês quando for padrão da linguagem
- Comentários explicativos **sempre** em PT-BR

### 2. Arquitetura Zero Cost
- Serverless First (Cloud Run)
- **Proibido**: polling, `setInterval`, tráfego idle
- **Permitido**: webhooks, botões "Atualizar", lógica on-demand

### 3. Segurança
- **Produção**: Secrets no GitHub Actions
- **Local**: `.env` (gitignored)
- **Nunca**: commitar credenciais, API keys, database URLs

Consulte [`DIRETRIZES.md`](../DIRETRIZES.md) para detalhes completos.

---

## 🏗️ Arquitetura de Dados

### Modelos Principais

```python
# Hierarquia Organizacional
Company (Empresa)
  └─> Establishment (Estabelecimento/Loja)
      └─> Inspection (Inspeção)
          └─> ActionPlan (Plano de Ação)
              └─> ActionPlanItem (Item do Plano)

# Usuários
User (role: CONSULTANT | MANAGER | ADMIN)
  └─> M2M com Establishments (consultores podem ter múltiplas lojas)
```

### ⚡ Decisões Arquiteturais Importantes

#### 1. Campos de Prazo (ML-Ready)

**Contexto**: Queremos que a IA aprenda com correções dos gestores.

**Implementação**: 3 campos em `ActionPlanItem`:

```python
ai_suggested_deadline: String  # Sugestão ORIGINAL da IA (nunca muda)
deadline_date: Date            # Prazo estruturado do gestor
deadline_text: Text            # Prazo textual editado pelo gestor
```

**Rationale**:
- `ai_suggested_deadline` = fonte de verdade da sugestão original
- `deadline_text` = captura edições textuais (ex: "Imediato", "30 dias")
- `deadline_date` = facilita queries e ordenação

**Exibição**: `deadline_text` > `deadline_date` > `ai_suggested_deadline`

**Uso Futuro**:
```python
# Dataset de treinamento
{
    "ai_suggestion": "45 dias",
    "human_correction": "15/02/2026",
    "context": {"severity": "CRITICAL", "sector": "Cozinha"}
}
```

Ver: [`ml_deadline_strategy.md`](ml_deadline_strategy.md)

#### 2. Ordenação de Itens

**Por que `order_index` ao invés de `created_at`?**

- **Problema**: `created_at` ordena cronologicamente, mas gestor pode querer reordenar itens por prioridade
- **Solução**: Campo `order_index` (Integer) permite ordenação manual
- **Trade-off**: `created_at` foi **removido** de `ActionPlanItem` para evitar confusão

**Código de Ordenação**:
```python
# manager_routes.py, linha ~648
db_items = sorted(
    inspection.action_items,
    key=lambda i: (i.order_index if i.order_index is not None else float('inf'), str(i.id))
)
```

---

## 💻 Padrões de Código

### Scripts de Migração

**Template Padrão**:
```python
import sys
import os
import logging

# [CRÍTICO] Adicionar raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

# Importar app para contexto Flask
from src.app import app
from src import database

def minha_migracao():
    with app.app_context():  # [OBRIGATÓRIO] para acesso ao DB
        session = next(database.get_db())
        try:
            # ... lógica da migração
            session.commit()
        except Exception as e:
            logger.error(f"❌ Erro: {e}")
            session.rollback()
        finally:
            session.close()

if __name__ == "__main__":
    minha_migracao()
```

### Salvando Dados de Edição (Padrão ML-Ready)

**Ao implementar edição de campos**:

```python
# ERRADO (perde dado original)
item.campo = novo_valor

# CORRETO (preserva original + edição)
if novo_valor != item.ai_suggested_campo:
    item.campo_editado = novo_valor  # Captura para ML

item.campo_estruturado = converter(novo_valor)  # Se aplicável
```

---

## 🔄 Migrações de Banco

### Scripts Disponíveis

| Script | Função | Status |
|--------|--------|--------|
| `migration_add_order.py` | Adiciona `order_index` | ✅ Aplicada |
| `migration_add_deadline_text.py` | Adiciona `deadline_text` | ✅ Aplicada |
| `migration_app_config.py` | Cria tabela `app_config` | ✅ Aplicada |

### Como Criar Nova Migração

1. **Copiar template** de script existente
2. **Verificar** se coluna já existe (evitar erro)
3. **Adicionar** coluna com `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
4. **Testar** localmente antes de commitar
5. **Documentar** no CHANGELOG.md

**Exemplo**:
```python
def add_meu_campo():
    logger.info("🚀 Adicionando coluna meu_campo...")
    
    with app.app_context():
        session = next(database.get_db())
        try:
            # Verificar se já existe
            check = text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='minha_tabela' AND column_name='meu_campo';
            """)
            result = session.execute(check).fetchone()
            
            if result:
                logger.info("✅ Coluna já existe. Pulando.")
                return
            
            # Adicionar coluna
            alter = text("ALTER TABLE minha_tabela ADD COLUMN meu_campo VARCHAR;")
            session.execute(alter)
            session.commit()
            logger.info("✅ Coluna adicionada!")
            
        except Exception as e:
            logger.error(f"❌ Erro: {e}")
            session.rollback()
        finally:
            session.close()
```

---

## 🧠 Estratégia ML-Ready

### Quando Criar Campos "Duplicados"?

**Pergunta-chave**: "Queremos que a IA aprenda com correções humanas neste campo?"

**Se SIM**:
1. Campo `ai_suggested_X` (original, nunca muda)
2. Campo `X_text` (captura edição textual)
3. Campo `X_estruturado` (opcional, para queries)

**Se NÃO**:
- Um único campo é suficiente

### Exemplo Aplicado: Prazos

```python
# IA processa PDF
ai_suggested_deadline = "30 dias"  # Salva sugestão

# Gestor edita
deadline_input = "15/02/2026"

# Sistema captura AMBOS
if deadline_input != ai_suggested_deadline:
    deadline_text = deadline_input       # Para ML
    deadline_date = parse(deadline_input) # Para queries
```

**Benefício**: Dataset `(IA → Humano)` para fine-tuning

---

## 🛠️ Troubleshooting Comum

### Erro: `ModuleNotFoundError: No module named 'src'`

**Causa**: Script não adiciona raiz do projeto ao `sys.path`

**Solução**:
```python
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
```

### Erro: `Database Engine is None`

**Causa**: Acesso ao database fora do contexto Flask

**Solução**:
```python
from src.app import app
with app.app_context():
    # código aqui
```

### Erro: Migração falha com "column already exists"

**Causa**: Executou migração mais de uma vez

**Solução**: Adicionar verificação `IF NOT EXISTS`:
```sql
ALTER TABLE tabela ADD COLUMN IF NOT EXISTS coluna VARCHAR;
```

---

## 📚 Referências Rápidas

| Documento | Descrição |
|-----------|-----------|
| [`DIRETRIZES.md`](../DIRETRIZES.md) | Regras de ouro do projeto |
| [`ml_deadline_strategy.md`](ml_deadline_strategy.md) | Estratégia ML de prazos |
| [`CHANGELOG.md`](../CHANGELOG.md) | Histórico de mudanças |
| [`README.md`](../README.md) | Visão geral e setup |

---

## ✅ Checklist para Novos Agentes

Ao iniciar trabalho neste projeto:

- [ ] Ler [`DIRETRIZES.md`](../DIRETRIZES.md)
- [ ] Ler este guia completo
- [ ] Verificar `.env.example` e configurar `.env`
- [ ] Executar `python3 scripts/migration_app_config.py`
- [ ] Testar aplicação com `python3 run_dev.py`
- [ ] Revisar [`ml_deadline_strategy.md`](ml_deadline_strategy.md) se trabalhar com prazos

---

**Última Atualização**: 19/01/2026
**Autor**: Agente Antigravity + ghcastellano
