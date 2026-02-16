"""
Seed script to add realistic demo data for presentations.
Run:    python seed_demo_data.py
Delete: python seed_demo_data.py --delete
"""
import sys
import uuid
from datetime import datetime, timedelta, date
import random
import json

from werkzeug.security import generate_password_hash

from src.app import app
from src.database import get_db
from src.models_db import (
    Company, Establishment, Contact, User, UserRole,
    Inspection, InspectionStatus, ActionPlan, ActionPlanItem,
    SeverityLevel, ActionPlanItemStatus, Job, JobStatus,
)

DEMO_TAG = "DEMO_APRESENTACAO"

# ──────────────────────────────────────────────────────────────────
# Realistic Brazilian food-service data
# ──────────────────────────────────────────────────────────────────

COMPANIES = [
    {
        "name": "Grupo Sabor & Saúde Alimentação",
        "cnpj": "45.123.456/0001-89",
        "establishments": [
            {
                "name": "Restaurante Sabor & Saúde - Unidade Centro",
                "code": "SS-001",
                "responsible_name": "Maria Fernanda Silva",
                "responsible_email": "maria.fernanda@saborsaude.com.br",
                "responsible_phone": "(11) 99876-5432",
                "contacts": [
                    {"name": "Maria Fernanda Silva", "phone": "5511998765432", "email": "maria.fernanda@saborsaude.com.br", "role": "Gerente"},
                    {"name": "José Carlos Mendes", "phone": "5511987654321", "email": "jose.carlos@saborsaude.com.br", "role": "Nutricionista"},
                ],
            },
            {
                "name": "Restaurante Sabor & Saúde - Unidade Jardins",
                "code": "SS-002",
                "responsible_name": "Ana Paula Oliveira",
                "responsible_email": "ana.paula@saborsaude.com.br",
                "responsible_phone": "(11) 99765-4321",
                "contacts": [
                    {"name": "Ana Paula Oliveira", "phone": "5511997654321", "email": "ana.paula@saborsaude.com.br", "role": "Gerente"},
                ],
            },
        ],
    },
    {
        "name": "Rede Pão Dourado Panificação LTDA",
        "cnpj": "67.890.123/0001-45",
        "establishments": [
            {
                "name": "Padaria Pão Dourado - Matriz Pinheiros",
                "code": "PD-001",
                "responsible_name": "Roberto Almeida Santos",
                "responsible_email": "roberto@paodourado.com.br",
                "responsible_phone": "(11) 98765-1234",
                "contacts": [
                    {"name": "Roberto Almeida Santos", "phone": "5511987651234", "email": "roberto@paodourado.com.br", "role": "Proprietário"},
                    {"name": "Luciana Costa", "phone": "5511976543210", "email": "luciana@paodourado.com.br", "role": "Chefe de Cozinha"},
                ],
            },
            {
                "name": "Padaria Pão Dourado - Filial Vila Mariana",
                "code": "PD-002",
                "responsible_name": "Carla Beatriz Lima",
                "responsible_email": "carla@paodourado.com.br",
                "responsible_phone": "(11) 98654-3210",
                "contacts": [
                    {"name": "Carla Beatriz Lima", "phone": "5511986543210", "email": "carla@paodourado.com.br", "role": "Gerente"},
                ],
            },
        ],
    },
    {
        "name": "Churrascaria Fogo Nativo SA",
        "cnpj": "12.345.678/0001-90",
        "establishments": [
            {
                "name": "Churrascaria Fogo Nativo - Moema",
                "code": "FN-001",
                "responsible_name": "Eduardo Martins Ribeiro",
                "responsible_email": "eduardo@fogonativo.com.br",
                "responsible_phone": "(11) 97654-3210",
                "contacts": [
                    {"name": "Eduardo Martins Ribeiro", "phone": "5511976543210", "email": "eduardo@fogonativo.com.br", "role": "Gerente Geral"},
                    {"name": "Patricia Souza", "phone": "5511965432109", "email": "patricia@fogonativo.com.br", "role": "Responsável Técnica"},
                ],
            },
        ],
    },
    {
        "name": "Hotel Estrela do Mar Hospedagem e Eventos",
        "cnpj": "98.765.432/0001-10",
        "establishments": [
            {
                "name": "Hotel Estrela do Mar - Cozinha Principal",
                "code": "HEM-001",
                "responsible_name": "Marcos Vinícius Pereira",
                "responsible_email": "marcos@estreladomar.com.br",
                "responsible_phone": "(13) 99876-5432",
                "contacts": [
                    {"name": "Marcos Vinícius Pereira", "phone": "5513998765432", "email": "marcos@estreladomar.com.br", "role": "Chef Executivo"},
                    {"name": "Fernanda Rodrigues", "phone": "5513987654321", "email": "fernanda@estreladomar.com.br", "role": "Gerente de A&B"},
                ],
            },
        ],
    },
]

MANAGERS = [
    {"name": "Carolina Mendes Ferreira", "email": "carolina.mendes@demo.com"},
    {"name": "Thiago Henrique Barros", "email": "thiago.barros@demo.com"},
    {"name": "Juliana Rodrigues Costa", "email": "juliana.costa@demo.com"},
]

CONSULTANTS = [
    {"name": "Dr. Ricardo Alves Nutricionista", "email": "ricardo.alves@demo.com", "whatsapp": "5511999001122"},
    {"name": "Dra. Patrícia Gomes Consultora", "email": "patricia.gomes@demo.com", "whatsapp": "5511999003344"},
]

# ──────────────────────────────────────────────────────────────────
# Realistic inspection items by sector
# ──────────────────────────────────────────────────────────────────

SECTORS = {
    "Recebimento de Mercadorias": {
        "items": [
            {
                "problem": "Temperatura de recebimento de carnes acima do permitido (>7°C). Lote de frango recebido a 12°C sem rejeição pelo responsável.",
                "action": "Implementar checklist de recebimento com verificação obrigatória de temperatura. Rejeitar lotes fora da faixa permitida. Treinar equipe de recebimento.",
                "legal": "RDC 216/2004 Art. 4.2.1 - Recebimento de matérias-primas",
                "severity": SeverityLevel.CRITICAL,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Ausência de registro de temperatura no ato do recebimento de produtos refrigerados e congelados.",
                "action": "Criar planilha de controle de recebimento com campos para temperatura, fornecedor, lote e responsável pela conferência.",
                "legal": "RDC 216/2004 Art. 4.2.2",
                "severity": SeverityLevel.HIGH,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Área de recebimento parcialmente organizada, mas sem proteção contra intempéries em dias chuvosos.",
                "action": "Instalar cobertura adequada na área de recebimento para proteger mercadorias durante descarga.",
                "legal": "RDC 216/2004 Art. 4.1.1",
                "severity": SeverityLevel.MEDIUM,
                "status_original": "Parcialmente Conforme",
                "score": 0.5,
            },
        ],
    },
    "Armazenamento e Estoque": {
        "items": [
            {
                "problem": "Produtos armazenados diretamente no chão do estoque seco, sem uso de estrados ou prateleiras apropriadas.",
                "action": "Adquirir estrados plásticos ou prateleiras de inox para elevação mínima de 25cm do piso. Reorganizar estoque imediatamente.",
                "legal": "RDC 216/2004 Art. 4.3.1 - Armazenamento",
                "severity": SeverityLevel.HIGH,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Câmara fria com temperatura oscilando entre 5°C e 9°C (acima do limite de 4°C para refrigerados).",
                "action": "Realizar manutenção preventiva no compressor da câmara fria. Instalar termômetro digital com alarme para variações.",
                "legal": "RDC 216/2004 Art. 4.3.3",
                "severity": SeverityLevel.CRITICAL,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Produtos sem identificação adequada (data de fabricação, validade e data de abertura após manipulação).",
                "action": "Implementar sistema de etiquetagem padrão com data de recebimento, abertura e validade. Capacitar equipe no método PVPS.",
                "legal": "RDC 216/2004 Art. 4.3.2",
                "severity": SeverityLevel.HIGH,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Estoque organizado e limpo, porém com iluminação insuficiente dificultando verificação de validades.",
                "action": "Instalar luminárias adicionais com proteção contra quebra no setor de estoque.",
                "legal": "RDC 216/2004 Art. 4.1.3",
                "severity": SeverityLevel.LOW,
                "status_original": "Parcialmente Conforme",
                "score": 0.5,
            },
        ],
    },
    "Cozinha e Preparo": {
        "items": [
            {
                "problem": "Manipuladores sem utilização completa de EPIs - toucas e luvas ausentes durante preparo de saladas cruas.",
                "action": "Fornecer EPIs em quantidade suficiente e treinar manipuladores sobre uso obrigatório. Fixar cartazes de boas práticas.",
                "legal": "RDC 216/2004 Art. 4.6.2 - Higiene e saúde dos manipuladores",
                "severity": SeverityLevel.HIGH,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Ausência de lavatório exclusivo para higienização das mãos na área de preparo. Manipuladores utilizam a pia de lavagem de utensílios.",
                "action": "Instalar lavatório exclusivo com sabonete líquido antisséptico, papel toalha descartável e coletor com tampa acionada sem contato manual.",
                "legal": "RDC 216/2004 Art. 4.1.9",
                "severity": SeverityLevel.CRITICAL,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Tábuas de corte em bom estado, porém sem diferenciação por cor para tipos de alimentos (carnes, vegetais, etc).",
                "action": "Adquirir conjunto de tábuas coloridas seguindo padrão: vermelha (carnes cruas), verde (vegetais), azul (peixes), branca (alimentos prontos).",
                "legal": "RDC 216/2004 Art. 4.4.1",
                "severity": SeverityLevel.MEDIUM,
                "status_original": "Parcialmente Conforme",
                "score": 0.5,
            },
            {
                "problem": "Superfícies de preparo em inox, limpas e em bom estado de conservação. Equipamentos calibrados e funcionando corretamente.",
                "action": "Manter rotina de limpeza e manutenção preventiva dos equipamentos conforme já praticado.",
                "legal": "RDC 216/2004 Art. 4.1.2",
                "severity": SeverityLevel.LOW,
                "status_original": "Conforme",
                "score": 1.0,
            },
        ],
    },
    "Higiene Pessoal e Manipuladores": {
        "items": [
            {
                "problem": "Manipuladores sem exames médicos periódicos atualizados (ASO vencido há mais de 6 meses).",
                "action": "Agendar exames médicos periódicos para todos os manipuladores. Manter arquivo atualizado de ASOs.",
                "legal": "RDC 216/2004 Art. 4.6.1 - Controle de saúde dos manipuladores",
                "severity": SeverityLevel.HIGH,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Ausência de programa formal de capacitação em boas práticas de manipulação de alimentos.",
                "action": "Elaborar e implementar programa de treinamento semestral em BPF, com registro de presença e conteúdo abordado.",
                "legal": "RDC 216/2004 Art. 4.12.2",
                "severity": SeverityLevel.HIGH,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Uniformes limpos e completos. Manipuladores com unhas curtas e sem adornos. Boa prática de higiene pessoal observada.",
                "action": "Manter padrão atual de higiene pessoal. Realizar verificações periódicas.",
                "legal": "RDC 216/2004 Art. 4.6.3",
                "severity": SeverityLevel.LOW,
                "status_original": "Conforme",
                "score": 1.0,
            },
        ],
    },
    "Sanitização e Controle de Pragas": {
        "items": [
            {
                "problem": "Contrato de dedetização vencido. Último serviço realizado há mais de 8 meses sem renovação.",
                "action": "Renovar contrato com empresa especializada de controle de pragas. Realizar desinsetização e desratização imediata.",
                "legal": "RDC 216/2004 Art. 4.5.1 - Controle integrado de pragas",
                "severity": SeverityLevel.CRITICAL,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Procedimentos de higienização documentados, mas frequência de limpeza de coifas e exaustores não está sendo cumprida.",
                "action": "Revisar cronograma de limpeza de coifas e exaustores. Contratar empresa especializada para limpeza trimestral.",
                "legal": "RDC 216/2004 Art. 4.4.2",
                "severity": SeverityLevel.MEDIUM,
                "status_original": "Parcialmente Conforme",
                "score": 0.5,
            },
            {
                "problem": "Lixeiras com acionamento por pedal e sacos plásticos adequados. Coleta de resíduos realizada 2x ao dia.",
                "action": "Manter rotina de coleta e descarte adequado de resíduos.",
                "legal": "RDC 216/2004 Art. 4.9.1",
                "severity": SeverityLevel.LOW,
                "status_original": "Conforme",
                "score": 1.0,
            },
        ],
    },
    "Documentação e POPs": {
        "items": [
            {
                "problem": "Manual de Boas Práticas desatualizado (última revisão em 2022). Não contempla processos atuais do estabelecimento.",
                "action": "Contratar profissional habilitado para revisão e atualização do Manual de Boas Práticas de Fabricação.",
                "legal": "RDC 216/2004 Art. 4.11.1 - Documentação e registro",
                "severity": SeverityLevel.HIGH,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "POPs de higienização existentes, porém incompletos - faltam procedimentos para higienização de equipamentos específicos.",
                "action": "Complementar POPs com procedimentos detalhados para cada equipamento, incluindo produtos, diluições e frequências.",
                "legal": "RDC 216/2004 Art. 4.11.2",
                "severity": SeverityLevel.MEDIUM,
                "status_original": "Parcialmente Conforme",
                "score": 0.5,
            },
        ],
    },
    "Instalações e Estrutura Física": {
        "items": [
            {
                "problem": "Piso da cozinha com rachaduras e rejunte deteriorado, dificultando higienização adequada e acumulando sujidades.",
                "action": "Realizar reparo do piso com material liso, impermeável e lavável. Renovar rejunte em toda a área de preparo.",
                "legal": "RDC 216/2004 Art. 4.1.1 - Edificação e instalações",
                "severity": SeverityLevel.HIGH,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Telas milimétricas nas janelas em bom estado. Portas com mola e proteção inferior adequada.",
                "action": "Manter manutenção preventiva das telas e vedações. Verificar integridade mensalmente.",
                "legal": "RDC 216/2004 Art. 4.1.5",
                "severity": SeverityLevel.LOW,
                "status_original": "Conforme",
                "score": 1.0,
            },
            {
                "problem": "Ventilação inadequada na área de preparo quente. Ausência de exaustor funcional na região do fogão industrial.",
                "action": "Instalar sistema de exaustão adequado à capacidade da cozinha. Verificar dimensionamento com engenheiro.",
                "legal": "RDC 216/2004 Art. 4.1.4",
                "severity": SeverityLevel.MEDIUM,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
        ],
    },
    "Distribuição e Exposição": {
        "items": [
            {
                "problem": "Balcão térmico de distribuição sem controle de temperatura. Alimentos expostos sem proteção contra contaminação.",
                "action": "Instalar termômetro no balcão térmico. Manter temperatura acima de 60°C. Instalar protetor salivar (sneeze guard).",
                "legal": "RDC 216/2004 Art. 4.8.1 - Exposição ao consumo",
                "severity": SeverityLevel.HIGH,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Área de distribuição limpa e organizada. Utensílios de servir em bom estado e trocados periodicamente.",
                "action": "Manter padrão atual de organização e limpeza na distribuição.",
                "legal": "RDC 216/2004 Art. 4.8.2",
                "severity": SeverityLevel.LOW,
                "status_original": "Conforme",
                "score": 1.0,
            },
        ],
    },
    "Banheiros e Vestiários": {
        "items": [
            {
                "problem": "Banheiro dos funcionários sem sabonete líquido antisséptico e papel toalha descartável no momento da inspeção.",
                "action": "Garantir reposição constante de sabonete antisséptico e papel toalha. Criar checklist de verificação 3x ao dia.",
                "legal": "RDC 216/2004 Art. 4.1.10",
                "severity": SeverityLevel.MEDIUM,
                "status_original": "Não Conforme",
                "score": 0.0,
            },
            {
                "problem": "Vestiário organizado com armários individuais para cada funcionário. Área limpa e ventilada.",
                "action": "Manter organização e limpeza do vestiário.",
                "legal": "RDC 216/2004 Art. 4.1.11",
                "severity": SeverityLevel.LOW,
                "status_original": "Conforme",
                "score": 1.0,
            },
        ],
    },
}

# ──────────────────────────────────────────────────────────────────
# Inspection templates with different scenarios for presentation
# ──────────────────────────────────────────────────────────────────

INSPECTION_SCENARIOS = [
    # Scenario 1: Completed inspection - restaurant with many issues fixed
    {
        "establishment_idx": (0, 0),  # Sabor & Saúde - Centro
        "status": InspectionStatus.COMPLETED,
        "days_ago": 45,
        "overall_score": 62,
        "max_score": 100,
        "summary": "Inspeção sanitária realizada na unidade Centro identificou diversas não conformidades, principalmente nas áreas de armazenamento e higiene de manipuladores. Após plano de ação implementado, melhorias significativas foram observadas na visita de verificação.",
        "strengths": "Equipe receptiva e comprometida com melhorias. Área de distribuição bem mantida. Bom controle de resíduos sólidos.",
        "sectors": ["Armazenamento e Estoque", "Cozinha e Preparo", "Higiene Pessoal e Manipuladores", "Sanitização e Controle de Pragas"],
        "resolve_ratio": 0.8,  # 80% of items resolved
    },
    # Scenario 2: Approved by manager, awaiting consultant verification
    {
        "establishment_idx": (0, 1),  # Sabor & Saúde - Jardins
        "status": InspectionStatus.PENDING_CONSULTANT_VERIFICATION,
        "days_ago": 12,
        "overall_score": 55,
        "max_score": 100,
        "summary": "Inspeção identificou problemas críticos na área de recebimento de mercadorias e documentação desatualizada. Plano de ação aprovado pelo gestor com prazos definidos.",
        "strengths": "Instalações físicas em bom estado. Equipe uniformizada adequadamente.",
        "sectors": ["Recebimento de Mercadorias", "Documentação e POPs", "Instalações e Estrutura Física", "Banheiros e Vestiários"],
        "resolve_ratio": 0.0,
    },
    # Scenario 3: Pending manager review - bakery
    {
        "establishment_idx": (1, 0),  # Pão Dourado - Pinheiros
        "status": InspectionStatus.PENDING_MANAGER_REVIEW,
        "days_ago": 3,
        "overall_score": 71,
        "max_score": 100,
        "summary": "Inspeção na padaria apresentou conformidade geral satisfatória, com pendências pontuais em controle de temperatura e documentação de POPs.",
        "strengths": "Excelente organização do setor de panificação. Boas práticas de higiene pessoal. Área de vendas limpa e organizada.",
        "sectors": ["Armazenamento e Estoque", "Cozinha e Preparo", "Documentação e POPs", "Distribuição e Exposição"],
        "resolve_ratio": 0.0,
    },
    # Scenario 4: Pending manager review - another bakery branch
    {
        "establishment_idx": (1, 1),  # Pão Dourado - Vila Mariana
        "status": InspectionStatus.PENDING_MANAGER_REVIEW,
        "days_ago": 5,
        "overall_score": 48,
        "max_score": 100,
        "summary": "Filial Vila Mariana apresentou número significativo de não conformidades. Necessidade urgente de adequação na área de armazenamento e controle de pragas.",
        "strengths": "Estrutura física adequada. Boa iluminação natural.",
        "sectors": ["Recebimento de Mercadorias", "Armazenamento e Estoque", "Sanitização e Controle de Pragas", "Instalações e Estrutura Física", "Higiene Pessoal e Manipuladores"],
        "resolve_ratio": 0.0,
    },
    # Scenario 5: Completed - steakhouse with great score
    {
        "establishment_idx": (2, 0),  # Fogo Nativo - Moema
        "status": InspectionStatus.COMPLETED,
        "days_ago": 30,
        "overall_score": 88,
        "max_score": 100,
        "summary": "Churrascaria apresentou alto nível de conformidade. Poucas não conformidades identificadas, todas de baixa severidade. Estabelecimento demonstra comprometimento exemplar com segurança alimentar.",
        "strengths": "Excelente controle de temperatura em todas as etapas. Equipe bem treinada. Documentação atualizada. Programa de controle de pragas em dia.",
        "sectors": ["Cozinha e Preparo", "Distribuição e Exposição", "Banheiros e Vestiários"],
        "resolve_ratio": 1.0,
    },
    # Scenario 6: In progress / approved - hotel kitchen
    {
        "establishment_idx": (3, 0),  # Hotel Estrela do Mar
        "status": InspectionStatus.APPROVED,
        "days_ago": 8,
        "overall_score": 59,
        "max_score": 100,
        "summary": "Cozinha do hotel apresentou diversas não conformidades concentradas nas áreas de armazenamento e estrutura física. Plano de ação aprovado com prazos urgentes para itens críticos.",
        "strengths": "Equipe com formação técnica qualificada. Bom sistema de rastreabilidade de fornecedores.",
        "sectors": ["Recebimento de Mercadorias", "Armazenamento e Estoque", "Cozinha e Preparo", "Sanitização e Controle de Pragas", "Instalações e Estrutura Física", "Documentação e POPs"],
        "resolve_ratio": 0.0,
    },
]


def build_ai_raw_response(scenario, items_by_sector):
    """Build realistic ai_raw_response JSON matching the app's expected structure."""
    areas = []
    for sector_name, items in items_by_sector.items():
        sector_score = sum(it["score"] for it in items)
        sector_max = len(items)
        area = {
            "nome_area": sector_name,
            "score_obtido": sector_score,
            "score_maximo": sector_max,
            "aproveitamento": round((sector_score / sector_max * 100), 1) if sector_max > 0 else 0,
            "itens": [
                {
                    "item_verificado": it["problem"],
                    "status": it["status_original"],
                    "score": it["score"],
                    "acao_corretiva_sugerida": it["action"],
                    "fundamento_legal": it["legal"],
                    "prazo_sugerido": random.choice(["7 dias", "14 dias", "30 dias", "Imediato"]),
                }
                for it in items
            ],
        }
        areas.append(area)

    return {
        "pontuacao_geral": scenario["overall_score"],
        "pontuacao_maxima_geral": scenario["max_score"],
        "resumo_geral": scenario["summary"],
        "pontos_positivos": scenario["strengths"],
        "areas_inspecionadas": areas,
    }


def build_stats_json(items_by_sector, overall_score, max_score):
    """Build stats_json for ActionPlan."""
    total_items = sum(len(items) for items in items_by_sector.values())
    total_nc = sum(1 for items in items_by_sector.values() for it in items if it["status_original"] == "Não Conforme")

    by_sector = {}
    for sector_name, items in items_by_sector.items():
        s_score = sum(it["score"] for it in items)
        s_max = len(items)
        nc = sum(1 for it in items if it["status_original"] == "Não Conforme")
        by_sector[sector_name] = {
            "score": s_score,
            "max_score": s_max,
            "percentage": round((s_score / s_max * 100), 1) if s_max > 0 else 0,
            "nc_count": nc,
        }

    return {
        "total_items": total_items,
        "total_nc": total_nc,
        "score": overall_score,
        "max_score": max_score,
        "percentage": round((overall_score / max_score * 100), 1) if max_score > 0 else 0,
        "by_sector": by_sector,
    }


def seed():
    """Create realistic demo data for presentation."""
    with app.app_context():
        session = next(get_db())

        print(f"Seeding demo data (tag: [{DEMO_TAG}])...")

        # 1. Companies
        db_companies = []
        for comp_data in COMPANIES:
            c = Company(
                id=uuid.uuid4(),
                name=f"{comp_data['name']} [{DEMO_TAG}]",
                cnpj=comp_data["cnpj"],
            )
            session.add(c)
            db_companies.append(c)
        session.flush()
        print(f"  Created {len(db_companies)} companies")

        # 2. Establishments + Contacts
        db_establishments = []  # list of lists matching COMPANIES structure
        for comp_idx, comp_data in enumerate(COMPANIES):
            comp_ests = []
            for est_data in comp_data["establishments"]:
                est = Establishment(
                    id=uuid.uuid4(),
                    company_id=db_companies[comp_idx].id,
                    name=est_data["name"],
                    code=est_data["code"],
                    responsible_name=est_data["responsible_name"],
                    responsible_email=est_data["responsible_email"],
                    responsible_phone=est_data["responsible_phone"],
                )
                session.add(est)
                session.flush()

                # Contacts
                for ct in est_data.get("contacts", []):
                    contact = Contact(
                        id=uuid.uuid4(),
                        establishment_id=est.id,
                        name=ct["name"],
                        phone=ct["phone"],
                        email=ct.get("email"),
                        role=ct.get("role"),
                    )
                    session.add(contact)

                comp_ests.append(est)
            db_establishments.append(comp_ests)
        session.flush()
        total_est = sum(len(e) for e in db_establishments)
        print(f"  Created {total_est} establishments with contacts")

        # 3. Users (Managers & Consultants)
        db_managers = []
        for i, mgr in enumerate(MANAGERS):
            comp_idx = i % len(db_companies)
            u = User(
                id=uuid.uuid4(),
                name=f"{mgr['name']} [{DEMO_TAG}]",
                email=f"{DEMO_TAG.lower()}.{mgr['email']}",
                password_hash=generate_password_hash("demo123"),
                role=UserRole.MANAGER,
                company_id=db_companies[comp_idx].id,
                must_change_password=False,
            )
            session.add(u)
            db_managers.append(u)

        db_consultants = []
        for i, cons in enumerate(CONSULTANTS):
            comp_idx = i % len(db_companies)
            u = User(
                id=uuid.uuid4(),
                name=f"{cons['name']} [{DEMO_TAG}]",
                email=f"{DEMO_TAG.lower()}.{cons['email']}",
                password_hash=generate_password_hash("demo123"),
                role=UserRole.CONSULTANT,
                company_id=db_companies[comp_idx].id,
                whatsapp=cons.get("whatsapp"),
                must_change_password=False,
            )
            session.add(u)
            db_consultants.append(u)
            # Assign consultant to all establishments of their company
            for est in db_establishments[comp_idx]:
                u.establishments.append(est)

        session.flush()
        print(f"  Created {len(db_managers)} managers + {len(db_consultants)} consultants")

        # 4. Inspections with full data
        for sc_idx, scenario in enumerate(INSPECTION_SCENARIOS):
            comp_idx, est_idx = scenario["establishment_idx"]
            est = db_establishments[comp_idx][est_idx]

            # Gather items from selected sectors
            items_by_sector = {}
            for sector_name in scenario["sectors"]:
                if sector_name in SECTORS:
                    items_by_sector[sector_name] = SECTORS[sector_name]["items"]

            # Create inspection
            days_ago = scenario["days_ago"]
            created_at = datetime.utcnow() - timedelta(days=days_ago)

            insp = Inspection(
                id=uuid.uuid4(),
                establishment_id=est.id,
                drive_file_id=f"demo_insp_{uuid.uuid4().hex[:12]}",
                status=scenario["status"],
                file_hash=f"demo_hash_{uuid.uuid4().hex[:16]}",
                ai_raw_response=build_ai_raw_response(scenario, items_by_sector),
                created_at=created_at,
                updated_at=created_at + timedelta(hours=random.randint(1, 48)),
            )
            session.add(insp)
            session.flush()

            # Create action plan
            approved_by = random.choice(db_managers) if scenario["status"] in [
                InspectionStatus.APPROVED,
                InspectionStatus.PENDING_CONSULTANT_VERIFICATION,
                InspectionStatus.COMPLETED,
            ] else None

            plan = ActionPlan(
                id=uuid.uuid4(),
                inspection_id=insp.id,
                summary_text=scenario["summary"],
                strengths_text=scenario["strengths"],
                stats_json=build_stats_json(items_by_sector, scenario["overall_score"], scenario["max_score"]),
                approved_by_id=approved_by.id if approved_by else None,
                approved_at=(created_at + timedelta(days=2)) if approved_by else None,
            )
            session.add(plan)
            session.flush()

            # Create action plan items
            order = 0
            for sector_name, items in items_by_sector.items():
                for it in items:
                    is_nc = it["status_original"] != "Conforme"

                    # Determine if resolved based on scenario ratio
                    is_resolved = False
                    if is_nc and scenario["resolve_ratio"] > 0:
                        is_resolved = random.random() < scenario["resolve_ratio"]

                    deadline_days = random.choice([7, 14, 30, 60]) if is_nc else None
                    deadline = (date.today() + timedelta(days=deadline_days)) if deadline_days else None

                    # Pick a random evidence image from existing ones
                    evidence_url = None
                    correction_note = None
                    if is_resolved:
                        evidence_url = f"/static/uploads/evidence/{uuid.uuid4()}_evidence.jpg"
                        correction_note = random.choice([
                            "Correção realizada conforme plano de ação. Verificado in loco.",
                            "Item corrigido. Novo equipamento instalado e funcionando.",
                            "Adequação concluída. Documentação atualizada e disponível.",
                            "Treinamento realizado com toda equipe. Registros arquivados.",
                            "Manutenção preventiva realizada. Laudos técnicos atualizados.",
                        ])

                    api = ActionPlanItem(
                        id=uuid.uuid4(),
                        action_plan_id=plan.id,
                        problem_description=it["problem"],
                        corrective_action=it["action"],
                        legal_basis=it["legal"],
                        severity=it["severity"],
                        status=ActionPlanItemStatus.RESOLVED if is_resolved else ActionPlanItemStatus.OPEN,
                        original_status=it["status_original"],
                        original_score=it["score"],
                        ai_suggested_deadline=f"{deadline_days} dias" if deadline_days else None,
                        deadline_date=deadline,
                        sector=sector_name,
                        order_index=order,
                        correction_notes=correction_note,
                        evidence_image_url=evidence_url,
                        current_status="Corrigido" if is_resolved else ("Pendente" if is_nc else "Conforme"),
                    )
                    session.add(api)
                    order += 1

            session.flush()
            status_label = scenario["status"].value
            print(f"  Inspection {sc_idx+1}: {est.name} | {status_label} | Score: {scenario['overall_score']}% | {order} items")

        # 5. Jobs for some inspections
        inspections = session.query(Inspection).filter(
            Inspection.drive_file_id.like("demo_insp_%")
        ).all()
        for insp in inspections:
            est = insp.establishment
            comp_id = est.company_id if est else db_companies[0].id
            job = Job(
                id=uuid.uuid4(),
                type="PROCESS_PDF",
                status=JobStatus.COMPLETED,
                company_id=comp_id,
                input_payload={
                    "file_id": insp.drive_file_id,
                    "filename": f"Relatorio_Inspecao_{est.name if est else 'Unknown'}.pdf",
                    "establishment_name": est.name if est else "Unknown",
                    "establishment_id": str(est.id) if est else "",
                },
                created_at=insp.created_at - timedelta(minutes=30),
                finished_at=insp.created_at,
                cost_tokens_input=random.randint(15000, 45000),
                cost_tokens_output=random.randint(8000, 25000),
                execution_time_seconds=random.uniform(15, 90),
                api_calls_count=random.randint(2, 5),
                cost_input_usd=random.uniform(0.01, 0.08),
                cost_output_usd=random.uniform(0.005, 0.04),
            )
            session.add(job)

        session.flush()
        session.commit()

        print(f"\nDone! Demo data seeded successfully.")
        print(f"  Tag: [{DEMO_TAG}]")
        print(f"  Companies: {len(db_companies)}")
        print(f"  Establishments: {total_est}")
        print(f"  Users: {len(db_managers) + len(db_consultants)}")
        print(f"  Inspections: {len(INSPECTION_SCENARIOS)}")
        print(f"  Delete with: python seed_demo_data.py --delete")


def delete():
    """Remove all demo data tagged with DEMO_TAG."""
    from sqlalchemy import or_, String

    with app.app_context():
        session = next(get_db())

        print(f"Removing demo data (tag: [{DEMO_TAG}])...")

        # 1. Delete jobs with demo tag
        jobs = session.query(Job).filter(
            Job.input_payload.cast(String).contains("demo_insp_")
        ).all()
        for j in jobs:
            session.delete(j)
        print(f"  Deleted {len(jobs)} jobs")

        # 2. Delete inspections (cascade: action_plan -> items)
        inspections = session.query(Inspection).filter(
            Inspection.drive_file_id.like("demo_insp_%")
        ).all()
        for insp in inspections:
            if insp.action_plan:
                # Delete items first
                session.query(ActionPlanItem).filter(
                    ActionPlanItem.action_plan_id == insp.action_plan.id
                ).delete()
                session.delete(insp.action_plan)
            session.delete(insp)
        print(f"  Deleted {len(inspections)} inspections (with plans + items)")

        # 3. Delete contacts for demo establishments
        # First find demo companies
        demo_companies = session.query(Company).filter(
            Company.name.contains(DEMO_TAG)
        ).all()
        demo_company_ids = [c.id for c in demo_companies]

        demo_ests = session.query(Establishment).filter(
            Establishment.company_id.in_(demo_company_ids)
        ).all() if demo_company_ids else []

        for est in demo_ests:
            contacts = session.query(Contact).filter(
                Contact.establishment_id == est.id
            ).all()
            for ct in contacts:
                session.delete(ct)

        # 4. Delete users with demo tag
        demo_users = session.query(User).filter(
            User.name.contains(DEMO_TAG)
        ).all()
        for u in demo_users:
            u.establishments = []  # Clear M2M
            session.delete(u)
        print(f"  Deleted {len(demo_users)} users")

        # 5. Delete establishments
        for est in demo_ests:
            session.delete(est)
        print(f"  Deleted {len(demo_ests)} establishments")

        # 6. Delete companies
        for comp in demo_companies:
            session.delete(comp)
        print(f"  Deleted {len(demo_companies)} companies")

        session.commit()
        print(f"\nDone! All demo data removed.")


if __name__ == "__main__":
    if "--delete" in sys.argv:
        delete()
    else:
        seed()
