from typing import List, Optional
from pydantic import BaseModel, Field
import uuid

class AcaoCorretiva(BaseModel):
    descricao: str = Field(description="Descrição da ação corretiva a ser tomada.")
    prioridade: str = Field(description="Prioridade da ação: Alta, Média ou Baixa.", pattern="^(Alta|Média|Baixa)$")
    prazo_sugerido: str = Field(description="Prazo sugerido para a adequação.")

class NaoConformidade(BaseModel):
    id: str = Field(description="Identificador único, ex: '1.2'")
    item: str = Field(description="Nome do item/área avaliada")
    descricao: str = Field(description="Descrição detalhada do problema")
    # Novo campo de status
    status_item: str = Field(description="Status do item: 'Parcialmente Conforme' ou 'Não Conforme'")
    legislacao_relacionada: str = Field(description="Artigo/Item da RDC 216")
    acoes_corretivas: List[AcaoCorretiva]
    # Campos de Revisão
    is_corrected: bool = Field(default=False)
    correction_notes: Optional[str] = None
    status_atual: str = Field(default="Pendente")

class PontuacaoTopico(BaseModel):
    topico: str
    pontos_obtidos: float
    pontos_possiveis: float
    percentual: float

class RelatorioInspecao(BaseModel):
    titulo: str = Field(description="Título do Relatório")
    estabelecimento: str = Field(description="Nome do estabelecimento")
    data_inspecao: str = Field(default_factory=lambda: datetime.datetime.now().strftime("%d/%m/%Y"))
    
    # Novos campos de Pontuação
    pontuacao_geral: float = Field(description="Pontuação total em percentual (0-100)")
    detalhe_pontuacao: List[PontuacaoTopico] = Field(default_factory=list, description="Detalhamento da pontuação por tópico")
    
    resumo_geral: str = Field(description="Resumo executivo da situação")
    nao_conformidades: List[NaoConformidade]
    pontos_fortes: List[str]
