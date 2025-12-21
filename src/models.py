from pydantic import BaseModel, Field
from typing import List, Optional

class AcaoCorretiva(BaseModel):
    descricao: str = Field(description="Descrição da ação a ser tomada.")
    prioridade: str = Field(description="Alta, Média ou Baixa")
    prazo_sugerido: str = Field(description="Prazo sugerido (ex: Imediato, 7 dias)")

class NaoConformidade(BaseModel):
    item: str = Field(description="Nome do item avaliado (ex: Higiene Pessoal)")
    setor: Optional[str] = Field(description="Setor ou área onde o problema foi encontrado (ex: Cozinha, Estoque)")
    descricao: str = Field(description="Descrição do problema encontrado")
    legislacao_relacionada: Optional[str] = Field(description="Artigo da RDC 216 ou legislação pertinente")
    acoes_corretivas: List[AcaoCorretiva] = Field(description="Lista de ações corretivas sugeridas")
    status_item: str = Field(description="Status na vistoria (ex: Não Conforme, Parcialmente Conforme)")
    is_corrected: bool = Field(default=False, description="Se o item foi corrigido em relação à visita anterior")
    correction_notes: Optional[str] = Field(default=None, description="Notas sobre a correção ou pendência")

class TopicoPontuacao(BaseModel):
    topico: str = Field(description="Nome do tópico ou área (ex: Edificação, Equipamentos)")
    pontos_obtidos: float = Field(description="Pontos ganhos")
    pontos_possiveis: float = Field(description="Máximo de pontos")
    percentual: float = Field(description="Aproveitamento percentual")

class RelatorioInspecao(BaseModel):
    titulo: str = Field(default="Relatório de Inspeção Sanitária", description="Título do relatório")
    estabelecimento: str = Field(description="Nome do estabelecimento identificado")
    data_inspecao: str = Field(description="Data da vistoria (DD/MM/AAAA)")
    pontuacao_geral: float = Field(description="Nota de 0 a 100")
    resumo_geral: str = Field(description="Breve resumo da situação geral")
    pontos_fortes: List[str] = Field(default_factory=list, description="Destaques positivos encontrados")
    detalhe_pontuacao: List[TopicoPontuacao] = Field(default_factory=list, description="Detalhamento de pontos por área")
    nao_conformidades: List[NaoConformidade]
