from pydantic import BaseModel, Field
from typing import List, Optional

class ChecklistItem(BaseModel):
    item_verificado: str = Field(description="O requisito ou item específico que foi inspecionado.")
    status: str = Field(description="O status do item, deve ser 'Conforme' ou 'Não Conforme' ou 'Parcialmente Conforme'.")
    observacao: str = Field(description="Descrição detalhada da evidência encontrada e do problema.")
    fundamento_legal: str = Field(description="A base legal para a não conformidade, citando a legislação relevante (ex: 'RDC 216/2004 item 4.1.1').")
    acao_corretiva_sugerida: str = Field(description="Ação corretiva técnica sugerida para resolver o problema.")
    prazo_sugerido: str = Field(description="Prazo sugerido para correção (ex: 'Imediato', '24h', '7 dias').")

class AreaInspecao(BaseModel):
    nome_area: str = Field(description="Nome da área física inspecionada (ex: 'Cozinha', 'Depósito', 'Vestiários').")
    resumo_area: str = Field(description="Um curto parágrafo resumindo a situação desta área específica, destacando se está em conformidade ou não.")
    pontuacao_obtida: float = Field(description="Pontos obtidos nesta área.")
    pontuacao_maxima: float = Field(description="Pontuação máxima possível para esta área.")
    aproveitamento: float = Field(description="Percentual de aproveitamento da área (0-100).")
    itens: List[ChecklistItem] = Field(description="Lista de itens verificados nesta área. Incluir APENAS itens com não conformidades.")

class ChecklistSanitario(BaseModel):
    nome_estabelecimento: str = Field(description="Nome do estabelecimento que foi auditado.")
    resumo_geral: str = Field(description="Um parágrafo resumindo o resultado geral da inspeção, destacando as principais áreas de preocupação.")
    pontuacao_geral: float = Field(description="Pontuação total obtida no estabelecimento.")
    pontuacao_maxima_geral: float = Field(description="Pontuação máxima possível para o estabelecimento.")
    aproveitamento_geral: float = Field(description="Percentual de aproveitamento global (0-100).")
    pontos_fortes: str = Field(description="Lista de pontos positivos e boas práticas observadas.", default="")
    areas_inspecionadas: List[AreaInspecao] = Field(description="Lista de áreas inspecionadas com seus respectivos itens.")
