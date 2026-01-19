# Changelog - MVP Inspeção Sanitária

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

## [2026-01-19] - Implementação ML-Ready para Prazos

### ✨ Adicionado

- **Arquitetura de 3 campos para prazos** em `ActionPlanItem`:
  - `ai_suggested_deadline` (String) - Sugestão original da IA
  - `deadline_date` (Date) - Prazo estruturado definido pelo gestor
  - `deadline_text` (Text) - Prazo textual editado pelo gestor
  
- **Lógica de captura em `manager_routes.py`**:
  - Salva `deadline_text` quando gestor edita prazo diferente da sugestão da IA
  - Tenta converter para `deadline_date` estruturado
  - Preserva sempre `ai_suggested_deadline` original
  
- **Lógica de exibição prioritária**:
  - Prioridade: `deadline_text` > `deadline_date` > `ai_suggested_deadline`
  - Permite fallback gracioso se conversão falhar

- **Documentação completa**:
  - `docs/ml_deadline_strategy.md` - Estratégia ML detalhada
  - README.md atualizado com seção ML-Ready
  - CHANGELOG.md criado

### 🔧 Corrigido

- **Script `migration_app_config.py`**:
  - Corrigido import de módulo `src`
  - Adicionado contexto Flask para acesso ao database
  - Adicionado carregamento de variáveis de ambiente via dotenv

### 📝 Mudanças Técnicas

#### `src/manager_routes.py`

**Linhas ~808-825**: Edição de itens existentes
```python
if 'deadline' in item_data and item_data.get('deadline'):
    deadline_input = item_data.get('deadline')
    
    # [ML-READY] Salvar versão textual se diferente da IA
    if deadline_input != item.ai_suggested_deadline:
        item.deadline_text = deadline_input
    
    # Tentar converter para Date
    try:
        item.deadline_date = datetime.strptime(deadline_input, '%Y-%m-%d').date()
    except:
        try:
            item.deadline_date = datetime.strptime(deadline_input, '%d/%m/%Y').date()
        except:
            pass  # Mantém apenas texto
```

**Linhas ~832-849**: Criação de novos itens
```python
deadline_text = deadline_input if item_data.get('deadline') else None
deadline_date = None  # Tentar converter...
```

**Linhas ~674-684**: Exibição prioritária
```python
deadline_display = item.ai_suggested_deadline or "N/A"
if item.deadline_date:
    deadline_display = item.deadline_date.strftime('%d/%m/%Y')
if item.deadline_text:
    deadline_display = item.deadline_text  # Priorizar edição gestor
```

### 🎯 Objetivo das Mudanças

Permitir aprendizado futuro da IA comparando sugestões originais vs. correções dos gestores, criando dataset para:
- Análise de padrões de correção
- Fine-tuning do modelo de sugestão de prazos
- Calibração de urgência baseada em setor e gravidade

### 🧪 Validação

- ✅ Compilação Python sem erros
- ✅ Migrações executadas com sucesso
- ⏳ Teste end-to-end pendente

### 📚 Referências

- [docs/ml_deadline_strategy.md](docs/ml_deadline_strategy.md)
- [Walkthrough completo](brain/walkthrough.md)

---

## [Histórico Anterior]

### [2026-01-15] - Campo order_index

- Adicionada coluna `order_index` em `ActionPlanItem`
- Removido campo `created_at` para ordenação manual
- Migração: `migration_add_order.py`

### [2026-01-15] - Migração deadline_text

- Adicionada coluna `deadline_text` em `ActionPlanItem`
- Migração: `migration_add_deadline_text.py`
- (Implementação concluída em 19/01/2026)

---

**Formato**: Baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)
