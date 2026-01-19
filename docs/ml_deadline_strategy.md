# Estratégia de Campos de Prazo para Machine Learning

## Visão Geral

Este documento descreve a estratégia implementada para capturar dados de prazos de forma que permita o aprendizado futuro da IA a partir das correções feitas pelos gestores.

## Campos Disponíveis

| Campo | Tipo | Propósito | Quando é Preenchido |
|-------|------|-----------|---------------------|
| `ai_suggested_deadline` | String | Sugestão **original** da IA (nunca muda) | Durante processamento inicial do PDF pela IA |
| `deadline_date` | Date | Prazo **estruturado** definido/editado pelo gestor | Quando gestor define data específica (ex: "31/12/2026") |
| `deadline_text` | Text | Prazo **textual** editado pelo gestor | Quando gestor edita o texto do prazo (diferente da sugestão da IA) |

## Fluxo de Dados

### 1. Processamento Inicial (IA)
```
PDF → IA analisa → Gera sugestão de prazo
                 → Salva em `ai_suggested_deadline` (ex: "30 dias")
```

### 2. Ed ição pelo Gestor

**Cenário A: Gestor edita para data específica**
```
IA sugere: "30 dias" (ai_suggested_deadline)
Gestor edita: "15/02/2026"

Sistema salva:
- ai_suggested_deadline: "30 dias" (preservado)
- deadline_text: "15/02/2026" (captura edição)
- deadline_date: 2026-02-15 (conversão estruturada)
```

**Cenário B: Gestor edita texto mas mantém formato livre**
```
IA sugere: "45 dias" (ai_suggested_deadline)
Gestor edita: "Imediato"

Sistema salva:
- ai_suggested_deadline: "45 dias" (preservado)
- deadline_text: "Imediato" (captura edição)
- deadline_date: NULL (não é data válida)
```

### 3. Exibição no Template

Prioridade de exibição:
1. **`deadline_text`** - Se gestor editou, mostrar essa versão
2. **`deadline_date`** - Se tem data estruturada, formatar como dd/mm/yyyy
3. **`ai_suggested_deadline`** - Fallback para sugestão original

## Benefícios para Machine Learning

### Dataset de Treinamento
Ao capturar tanto a sugestão da IA quanto a correção do gestor, podemos construir dataset:

```python
training_data = [
    {
        "ai_suggestion": "30 dias",
        "human_correction": "15/02/2026",
        "context": {
            "severity": "HIGH",
            "sector": "Cozinha",
            "problem": "Falta de higienização"
        }
    },
    ...
]
```

### Análises Possíveis

1. **Padrões de Correção**:
   - Quando IA sugere "X dias", gestores corrigem para data específica?
   - Quais setores têm prazos mais apertados?

2. **Melhoria de Sugestões**:
   - Treinar modelo para sugerir datas específicas ao invés de "X dias"
   - Ajustar prazos baseado em gravidade e setor

3. **Calibração de Urgência**:
   - IA sugere "30 dias" para problema CRITICAL → Gestor corrige para "7 dias"
   - Aprender que problemas CRITICAL necessitam prazos mais curtos

## Implementação

### Código de Captura (manager_routes.py)

```python
# Ao salvar edição do gestor
if 'deadline' in item_data and item_data.get('deadline'):
    deadline_input = item_data.get('deadline')
    
    # [ML-READY] Salvar versão textual se diferente da sugestão da IA
    if deadline_input != item.ai_suggested_deadline:
        item.deadline_text = deadline_input
    
    # Tentar converter para Date estruturado
    try:
        item.deadline_date = datetime.strptime(deadline_input, '%Y-%m-%d').date()
    except:
        try:
            item.deadline_date = datetime.strptime(deadline_input, '%d/%m/%Y').date()
        except:
            # Não é data válida, mantém apenas texto
            pass
```

### Código de Exibição (manager_routes.py)

```python
# Prioridade: deadline_text > deadline_date > ai_suggested_deadline
deadline_display = item.ai_suggested_deadline or "N/A"

if item.deadline_date:
    deadline_display = item.deadline_date.strftime('%d/%m/%Y')

if item.deadline_text:
    # Gestor editou manualmente, priorizar
    deadline_display = item.deadline_text
```

## Próximos Passos (Futuro)

1. **Exportação de Dataset**:
   - Script para exportar dados de treinamento em formato JSON/CSV
   
2. **Dashboard de Análise**:
   - Visualizar padrões de correção dos gestores
   - Identificar áreas com maior divergência IA vs. Gestor

3. **Fine-tuning do Modelo**:
   - Usar dados capturados para retreinar modelo de sugestão de prazos
   - Validar melhoria na acuracidade das sugestões

## Notas Importantes

- **Nunca modificar** `ai_suggested_deadline` após criação inicial
- **Sempre preservar** edições do gestor em `deadline_text`
- **Permitir formato livre** - nem todo prazo precisa ser data estruturada
