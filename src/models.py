from pydantic import BaseModel, Field
from typing import List, Optional

class AcaoCorretiva(BaseModel):
    descricao: str = Field(description="Descrição da ação a ser tomada.")
    prioridade: str = Field(description="Alta, Média ou Baixa")
    prazo_sugerido: str = Field(description="Prazo sugerido (ex: Imediato, 7 dias)")

class NaoConformidade(BaseModel):
    item: str = Field(description="Nome do item avaliado (ex: Higiene Pessoal)")
    descricao: str = Field(description="Descrição do problema encontrado")
    legislacao_relacionada: Optional[str] = Field(description="Artigo da RDC 216 ou legislação pertinente")
    acoes_corretivas: List[AcaoCorretiva] = Field(description="Lista de ações corretivas sugeridas")
    status_item: str = Field(description="Status na vistoria (ex: Não Conforme, Parcialmente Conforme)")

class RelatorioInspecao(BaseModel):
    estabelecimento: str = Field(description="Nome do estabelecimento identificado")
    data_inspecao: str = Field(description="Data da vistoria (DD/MM/AAAA)")
    pontuacao_geral: int = Field(description="Nota de 0 a 100")
    nao_conformidades: List[NaoConformidade]
    resumo_geral: str = Field(description="Breve resumo da situação geral")
