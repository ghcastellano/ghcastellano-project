"""
Seed script to add realistic demo data for existing users.
Adds to Empresa 2 (company of aa@aa.com and ghcastellano@gmail.com).
Run:    python3 seed_demo_users.py
Delete: python3 seed_demo_users.py --delete
"""
import sys
import uuid
from datetime import datetime, timedelta, date, timezone
import random

from src.app import app
from src.database import get_db
from src.models_db import (
    Company, Establishment, Contact, User,
    Inspection, InspectionStatus, ActionPlan, ActionPlanItem,
    SeverityLevel, ActionPlanItemStatus, Job, JobStatus,
)

DEMO_TAG = "DEMO_USERS"
COMPANY_ID = "1592ccab-d90d-4091-9951-5076a34b80a5"  # Empresa 2
CONSULTANT_EMAIL = "aa@aa.com"
MANAGER_EMAIL = "ghcastellano@gmail.com"

# ──────────────────────────────────────────────────────────────────
# New establishments to add to Empresa 2
# ──────────────────────────────────────────────────────────────────

NEW_ESTABLISHMENTS = [
    {
        "name": "Cantina Industrial - Sede Administrativa",
        "code": "CI-001",
        "responsible_name": "Patrícia Mendes Oliveira",
        "responsible_email": "patricia.mendes@empresa2.com.br",
        "responsible_phone": "(11) 99234-5678",
        "contacts": [
            {"name": "Patrícia Mendes Oliveira", "phone": "5511992345678", "email": "patricia.mendes@empresa2.com.br", "role": "Nutricionista RT"},
            {"name": "Carlos Eduardo Ferreira", "phone": "5511981234567", "email": "carlos.ferreira@empresa2.com.br", "role": "Gerente Operacional"},
        ],
    },
    {
        "name": "Refeitório Corporativo - Unidade Fabril",
        "code": "RC-002",
        "responsible_name": "Marcos Antônio da Silva",
        "responsible_email": "marcos.silva@empresa2.com.br",
        "responsible_phone": "(11) 98765-4321",
        "contacts": [
            {"name": "Marcos Antônio da Silva", "phone": "5511987654321", "email": "marcos.silva@empresa2.com.br", "role": "Chefe de Cozinha"},
            {"name": "Juliana Costa Pereira", "phone": "5511976543210", "email": "juliana.costa@empresa2.com.br", "role": "Supervisora de Qualidade"},
        ],
    },
    {
        "name": "Lanchonete Express - Térreo Torre A",
        "code": "LE-003",
        "responsible_name": "Fernanda Rodrigues Lima",
        "responsible_email": "fernanda.lima@empresa2.com.br",
        "responsible_phone": "(11) 97654-3210",
        "contacts": [
            {"name": "Fernanda Rodrigues Lima", "phone": "5511976543210", "email": "fernanda.lima@empresa2.com.br", "role": "Gerente"},
        ],
    },
]

# ──────────────────────────────────────────────────────────────────
# Realistic inspection data by sector (RDC 216/2004)
# ──────────────────────────────────────────────────────────────────

SECTOR_ITEMS = {
    "Recebimento de Mercadorias": [
        {
            "problem": "Temperatura de recebimento de carnes acima do permitido (>7°C). Lote de frango recebido a 12°C sem rejeição pelo responsável.",
            "action": "Implementar checklist de recebimento com verificação obrigatória de temperatura. Rejeitar lotes fora da faixa. Treinar equipe.",
            "legal": "RDC 216/2004 Art. 4.2.1 - Recebimento de matérias-primas",
            "severity": SeverityLevel.CRITICAL,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Ausência de registro de temperatura no ato do recebimento de produtos refrigerados e congelados.",
            "action": "Criar planilha de controle de recebimento com campos para temperatura, fornecedor, lote e responsável.",
            "legal": "RDC 216/2004 Art. 4.2.2",
            "severity": SeverityLevel.HIGH,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Área de recebimento parcialmente organizada, mas sem proteção contra intempéries.",
            "action": "Instalar cobertura adequada na área de recebimento.",
            "legal": "RDC 216/2004 Art. 4.1.1",
            "severity": SeverityLevel.MEDIUM,
            "orig_status": "Parcialmente Conforme", "score": 0.5,
        },
    ],
    "Armazenamento e Estoque": [
        {
            "problem": "Produtos armazenados diretamente no chão sem estrados ou prateleiras.",
            "action": "Adquirir estrados plásticos ou prateleiras de inox para elevação mínima de 25cm do piso.",
            "legal": "RDC 216/2004 Art. 4.3.1",
            "severity": SeverityLevel.HIGH,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Câmara fria com temperatura oscilando entre 5°C e 9°C (limite: 4°C).",
            "action": "Manutenção preventiva no compressor. Instalar termômetro digital com alarme.",
            "legal": "RDC 216/2004 Art. 4.3.3",
            "severity": SeverityLevel.CRITICAL,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Produtos sem identificação adequada (data de fabricação, validade, abertura).",
            "action": "Implementar sistema de etiquetagem padrão. Capacitar equipe no método PVPS.",
            "legal": "RDC 216/2004 Art. 4.3.2",
            "severity": SeverityLevel.HIGH,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Estoque organizado e limpo, porém com iluminação insuficiente.",
            "action": "Instalar luminárias adicionais com proteção contra quebra.",
            "legal": "RDC 216/2004 Art. 4.1.3",
            "severity": SeverityLevel.LOW,
            "orig_status": "Parcialmente Conforme", "score": 0.5,
        },
    ],
    "Cozinha e Preparo": [
        {
            "problem": "Manipuladores sem toucas e luvas durante preparo de saladas cruas.",
            "action": "Fornecer EPIs e treinar manipuladores sobre uso obrigatório. Fixar cartazes de boas práticas.",
            "legal": "RDC 216/2004 Art. 4.6.2",
            "severity": SeverityLevel.HIGH,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Ausência de lavatório exclusivo para higienização das mãos na área de preparo.",
            "action": "Instalar lavatório exclusivo com sabonete antisséptico, papel toalha e coletor com tampa sem contato.",
            "legal": "RDC 216/2004 Art. 4.1.9",
            "severity": SeverityLevel.CRITICAL,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Tábuas de corte sem diferenciação por cor para tipos de alimentos.",
            "action": "Adquirir conjunto de tábuas coloridas: vermelha (carnes), verde (vegetais), azul (peixes), branca (prontos).",
            "legal": "RDC 216/2004 Art. 4.4.1",
            "severity": SeverityLevel.MEDIUM,
            "orig_status": "Parcialmente Conforme", "score": 0.5,
        },
        {
            "problem": "Superfícies de preparo em inox, limpas e em bom estado. Equipamentos calibrados.",
            "action": "Manter rotina de limpeza e manutenção preventiva.",
            "legal": "RDC 216/2004 Art. 4.1.2",
            "severity": SeverityLevel.LOW,
            "orig_status": "Conforme", "score": 1.0,
        },
    ],
    "Higiene Pessoal e Manipuladores": [
        {
            "problem": "ASOs (Atestados de Saúde Ocupacional) vencidos há mais de 6 meses para 3 manipuladores.",
            "action": "Agendar exames médicos periódicos para todos. Manter arquivo atualizado.",
            "legal": "RDC 216/2004 Art. 4.6.1",
            "severity": SeverityLevel.HIGH,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Ausência de programa formal de capacitação em boas práticas de manipulação.",
            "action": "Elaborar programa de treinamento semestral em BPF com registro de presença.",
            "legal": "RDC 216/2004 Art. 4.12.2",
            "severity": SeverityLevel.HIGH,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Uniformes limpos e completos. Unhas curtas, sem adornos. Boa higiene pessoal.",
            "action": "Manter padrão atual. Realizar verificações periódicas.",
            "legal": "RDC 216/2004 Art. 4.6.3",
            "severity": SeverityLevel.LOW,
            "orig_status": "Conforme", "score": 1.0,
        },
    ],
    "Sanitização e Controle de Pragas": [
        {
            "problem": "Contrato de dedetização vencido. Último serviço há mais de 8 meses.",
            "action": "Renovar contrato com empresa especializada. Realizar desinsetização e desratização imediata.",
            "legal": "RDC 216/2004 Art. 4.5.1",
            "severity": SeverityLevel.CRITICAL,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Frequência de limpeza de coifas e exaustores não está sendo cumprida.",
            "action": "Revisar cronograma. Contratar empresa especializada para limpeza trimestral.",
            "legal": "RDC 216/2004 Art. 4.4.2",
            "severity": SeverityLevel.MEDIUM,
            "orig_status": "Parcialmente Conforme", "score": 0.5,
        },
        {
            "problem": "Lixeiras com acionamento por pedal e sacos plásticos adequados. Coleta 2x/dia.",
            "action": "Manter rotina atual de coleta e descarte.",
            "legal": "RDC 216/2004 Art. 4.9.1",
            "severity": SeverityLevel.LOW,
            "orig_status": "Conforme", "score": 1.0,
        },
    ],
    "Documentação e POPs": [
        {
            "problem": "Manual de Boas Práticas desatualizado (última revisão em 2023).",
            "action": "Contratar profissional habilitado para revisão e atualização do MBP.",
            "legal": "RDC 216/2004 Art. 4.11.1",
            "severity": SeverityLevel.HIGH,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "POPs de higienização incompletos - faltam procedimentos para equipamentos específicos.",
            "action": "Complementar POPs com procedimentos detalhados incluindo produtos, diluições e frequências.",
            "legal": "RDC 216/2004 Art. 4.11.2",
            "severity": SeverityLevel.MEDIUM,
            "orig_status": "Parcialmente Conforme", "score": 0.5,
        },
    ],
    "Instalações e Estrutura Física": [
        {
            "problem": "Piso da cozinha com rachaduras e rejunte deteriorado, dificultando higienização.",
            "action": "Reparar piso com material liso, impermeável e lavável. Renovar rejunte.",
            "legal": "RDC 216/2004 Art. 4.1.1",
            "severity": SeverityLevel.HIGH,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Telas milimétricas nas janelas em bom estado. Portas com mola e proteção inferior.",
            "action": "Manter manutenção preventiva. Verificar integridade mensalmente.",
            "legal": "RDC 216/2004 Art. 4.1.5",
            "severity": SeverityLevel.LOW,
            "orig_status": "Conforme", "score": 1.0,
        },
        {
            "problem": "Ventilação inadequada na área de preparo quente. Sem exaustor funcional.",
            "action": "Instalar sistema de exaustão adequado. Verificar dimensionamento.",
            "legal": "RDC 216/2004 Art. 4.1.4",
            "severity": SeverityLevel.MEDIUM,
            "orig_status": "Não Conforme", "score": 0.0,
        },
    ],
    "Distribuição e Exposição": [
        {
            "problem": "Balcão térmico sem controle de temperatura. Alimentos sem proteção contra contaminação.",
            "action": "Instalar termômetro no balcão (>60°C). Instalar protetor salivar.",
            "legal": "RDC 216/2004 Art. 4.8.1",
            "severity": SeverityLevel.HIGH,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Área de distribuição limpa e organizada. Utensílios em bom estado.",
            "action": "Manter padrão atual de organização.",
            "legal": "RDC 216/2004 Art. 4.8.2",
            "severity": SeverityLevel.LOW,
            "orig_status": "Conforme", "score": 1.0,
        },
    ],
    "Banheiros e Vestiários": [
        {
            "problem": "Banheiro dos funcionários sem sabonete antisséptico e papel toalha no momento da inspeção.",
            "action": "Garantir reposição constante. Criar checklist de verificação 3x/dia.",
            "legal": "RDC 216/2004 Art. 4.1.10",
            "severity": SeverityLevel.MEDIUM,
            "orig_status": "Não Conforme", "score": 0.0,
        },
        {
            "problem": "Vestiário organizado com armários individuais. Área limpa e ventilada.",
            "action": "Manter organização e limpeza.",
            "legal": "RDC 216/2004 Art. 4.1.11",
            "severity": SeverityLevel.LOW,
            "orig_status": "Conforme", "score": 1.0,
        },
    ],
}

# ──────────────────────────────────────────────────────────────────
# Inspection scenarios for existing establishments + new ones
# ──────────────────────────────────────────────────────────────────

INSPECTIONS = [
    # --- NEW establishments ---
    {
        "est_source": "new",
        "est_idx": 0,  # Cantina Industrial
        "status": InspectionStatus.COMPLETED,
        "days_ago": 35,
        "overall_score": 72,
        "max_score": 100,
        "summary": "Inspeção na cantina industrial identificou não conformidades pontuais em armazenamento e documentação. Após implementação do plano de ação, todas as correções foram verificadas em campo pelo consultor.",
        "strengths": "Equipe bem treinada e colaborativa. Excelente controle de temperatura na distribuição. Área de preparo limpa e organizada.",
        "sectors": ["Armazenamento e Estoque", "Cozinha e Preparo", "Documentação e POPs", "Distribuição e Exposição"],
        "resolve_ratio": 0.9,
    },
    {
        "est_source": "new",
        "est_idx": 0,  # Cantina Industrial (second inspection - older)
        "status": InspectionStatus.COMPLETED,
        "days_ago": 120,
        "overall_score": 54,
        "max_score": 100,
        "summary": "Primeira inspeção na cantina industrial revelou múltiplas não conformidades graves. Plano de ação extenso elaborado com prazos urgentes.",
        "strengths": "Estrutura física do prédio em bom estado. Boa ventilação natural.",
        "sectors": ["Recebimento de Mercadorias", "Armazenamento e Estoque", "Higiene Pessoal e Manipuladores", "Sanitização e Controle de Pragas", "Instalações e Estrutura Física"],
        "resolve_ratio": 1.0,
    },
    {
        "est_source": "new",
        "est_idx": 1,  # Refeitório Corporativo
        "status": InspectionStatus.PENDING_MANAGER_REVIEW,
        "days_ago": 2,
        "overall_score": 45,
        "max_score": 100,
        "summary": "Inspeção no refeitório identificou número elevado de não conformidades críticas. Necessidade urgente de adequação em armazenamento, controle de pragas e estrutura física. Recomendação de interdição parcial da área de preparo até regularização.",
        "strengths": "Equipe receptiva às orientações. Registro de fornecedores atualizado.",
        "sectors": ["Recebimento de Mercadorias", "Armazenamento e Estoque", "Cozinha e Preparo", "Sanitização e Controle de Pragas", "Instalações e Estrutura Física", "Documentação e POPs", "Banheiros e Vestiários"],
        "resolve_ratio": 0.0,
    },
    {
        "est_source": "new",
        "est_idx": 2,  # Lanchonete Express
        "status": InspectionStatus.APPROVED,
        "days_ago": 10,
        "overall_score": 67,
        "max_score": 100,
        "summary": "Lanchonete apresentou conformidade parcial. Principais pendências em higiene de manipuladores e documentação. Plano de ação aprovado pelo gestor.",
        "strengths": "Espaço compacto e bem organizado. Equipamentos novos e calibrados. Bom fluxo operacional.",
        "sectors": ["Cozinha e Preparo", "Higiene Pessoal e Manipuladores", "Documentação e POPs", "Distribuição e Exposição", "Banheiros e Vestiários"],
        "resolve_ratio": 0.0,
    },
    {
        "est_source": "new",
        "est_idx": 2,  # Lanchonete Express (consultant verification)
        "status": InspectionStatus.PENDING_CONSULTANT_VERIFICATION,
        "days_ago": 60,
        "overall_score": 58,
        "max_score": 100,
        "summary": "Inspeção anterior identificou problemas de recebimento e armazenamento. Plano aprovado, aguardando verificação de campo pelo consultor.",
        "strengths": "Equipe motivada. Boa comunicação entre turnos.",
        "sectors": ["Recebimento de Mercadorias", "Armazenamento e Estoque", "Sanitização e Controle de Pragas"],
        "resolve_ratio": 0.3,
    },
    # --- EXISTING establishments (Loja 1, Loja 2) ---
    {
        "est_source": "existing",
        "est_id": "392d3629-e50b-4d09-b46f-5e74df8fcac9",  # Loja 1
        "status": InspectionStatus.PENDING_MANAGER_REVIEW,
        "days_ago": 4,
        "overall_score": 61,
        "max_score": 100,
        "summary": "Inspeção na Loja 1 identificou problemas significativos na cozinha e controle de pragas. Documento enviado ao gestor para análise e aprovação do plano de ação.",
        "strengths": "Boa apresentação da área de vendas. Funcionários uniformizados. Documentação parcialmente atualizada.",
        "sectors": ["Cozinha e Preparo", "Sanitização e Controle de Pragas", "Higiene Pessoal e Manipuladores", "Instalações e Estrutura Física"],
        "resolve_ratio": 0.0,
    },
    {
        "est_source": "existing",
        "est_id": "d7d1f586-59b0-4a4c-b33a-ec790d965544",  # Loja 2
        "status": InspectionStatus.COMPLETED,
        "days_ago": 25,
        "overall_score": 83,
        "max_score": 100,
        "summary": "Loja 2 apresentou bom nível de conformidade. Poucas não conformidades identificadas, maioria de baixa severidade. Todas as correções foram implementadas e verificadas.",
        "strengths": "Excelente organização geral. Equipe bem treinada em BPF. Documentação atualizada. Ótimo controle de temperatura.",
        "sectors": ["Armazenamento e Estoque", "Documentação e POPs", "Distribuição e Exposição", "Banheiros e Vestiários"],
        "resolve_ratio": 1.0,
    },
    {
        "est_source": "existing",
        "est_id": "d7d1f586-59b0-4a4c-b33a-ec790d965544",  # Loja 2 (older)
        "status": InspectionStatus.COMPLETED,
        "days_ago": 90,
        "overall_score": 65,
        "max_score": 100,
        "summary": "Primeira inspeção na Loja 2. Diversas não conformidades em armazenamento e cozinha. Após plano de ação, melhorias substanciais implementadas.",
        "strengths": "Estrutura física adequada. Boa iluminação.",
        "sectors": ["Recebimento de Mercadorias", "Armazenamento e Estoque", "Cozinha e Preparo", "Higiene Pessoal e Manipuladores"],
        "resolve_ratio": 1.0,
    },
]

# ──────────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _build_ai_raw(scenario, items_by_sector):
    areas = []
    for sector, items in items_by_sector.items():
        s_score = sum(it["score"] for it in items)
        s_max = len(items)
        area = {
            "nome_area": sector,
            "score_obtido": s_score,
            "score_maximo": s_max,
            "aproveitamento": round(s_score / s_max * 100, 1) if s_max else 0,
            "itens": [
                {
                    "item_verificado": it["problem"],
                    "status": it["orig_status"],
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


def _build_stats(items_by_sector, overall_score, max_score):
    total_items = sum(len(v) for v in items_by_sector.values())
    total_nc = sum(1 for v in items_by_sector.values() for it in v if it["orig_status"] == "Não Conforme")
    by_sector = {}
    for sector, items in items_by_sector.items():
        s = sum(it["score"] for it in items)
        m = len(items)
        by_sector[sector] = {
            "score": s,
            "max_score": m,
            "percentage": round(s / m * 100, 1) if m else 0,
            "nc_count": sum(1 for it in items if it["orig_status"] == "Não Conforme"),
        }
    return {
        "total_items": total_items,
        "total_nc": total_nc,
        "score": overall_score,
        "max_score": max_score,
        "percentage": round(overall_score / max_score * 100, 1) if max_score else 0,
        "by_sector": by_sector,
    }


CORRECTION_NOTES = [
    "Correção realizada conforme plano de ação. Verificado in loco pelo consultor.",
    "Item corrigido. Novo equipamento instalado e operando dentro dos parâmetros.",
    "Adequação concluída. Documentação revisada e disponível para fiscalização.",
    "Treinamento realizado com toda a equipe. Registros de presença arquivados.",
    "Manutenção preventiva executada. Laudos técnicos atualizados e em ordem.",
    "Produto retirado e substituído. Novo fornecedor aprovado e cadastrado.",
    "Reparo concluído. Superfície agora lisa, impermeável e lavável conforme norma.",
    "Contrato renovado com empresa especializada. Certificado atualizado.",
]


def seed():
    with app.app_context():
        session = next(get_db())

        print(f"Seeding demo data for existing users (tag: [{DEMO_TAG}])...")

        # Find existing users
        consultant = session.query(User).filter(User.email == CONSULTANT_EMAIL).first()
        manager = session.query(User).filter(User.email == MANAGER_EMAIL).first()
        if not consultant or not manager:
            print("ERROR: Users not found!")
            return

        print(f"  Consultant: {consultant.name} ({consultant.email})")
        print(f"  Manager: {manager.name} ({manager.email})")

        # 1. Create new establishments
        new_ests = []
        for est_data in NEW_ESTABLISHMENTS:
            est = Establishment(
                id=uuid.uuid4(),
                company_id=uuid.UUID(COMPANY_ID),
                name=f"{est_data['name']} [{DEMO_TAG}]",
                code=est_data["code"],
                responsible_name=est_data["responsible_name"],
                responsible_email=est_data["responsible_email"],
                responsible_phone=est_data["responsible_phone"],
            )
            session.add(est)
            session.flush()

            # Add contacts
            for ct in est_data.get("contacts", []):
                session.add(Contact(
                    id=uuid.uuid4(),
                    establishment_id=est.id,
                    name=ct["name"],
                    phone=ct["phone"],
                    email=ct.get("email"),
                    role=ct.get("role"),
                ))

            # Link consultant to this establishment
            consultant.establishments.append(est)
            new_ests.append(est)

        session.flush()
        print(f"  Created {len(new_ests)} new establishments (linked to {CONSULTANT_EMAIL})")

        # 2. Create inspections
        insp_count = 0
        total_items = 0

        for sc in INSPECTIONS:
            # Resolve establishment
            if sc["est_source"] == "new":
                est = new_ests[sc["est_idx"]]
            else:
                est = session.query(Establishment).get(uuid.UUID(sc["est_id"]))
                if not est:
                    print(f"  WARNING: Establishment {sc['est_id']} not found, skipping")
                    continue

            # Gather sector items
            items_by_sector = {}
            for sector_name in sc["sectors"]:
                if sector_name in SECTOR_ITEMS:
                    items_by_sector[sector_name] = SECTOR_ITEMS[sector_name]

            days_ago = sc["days_ago"]
            created_at = _now() - timedelta(days=days_ago)

            insp = Inspection(
                id=uuid.uuid4(),
                establishment_id=est.id,
                drive_file_id=f"demo_usr_{uuid.uuid4().hex[:12]}",
                status=sc["status"],
                file_hash=f"demo_usr_hash_{uuid.uuid4().hex[:16]}",
                ai_raw_response=_build_ai_raw(sc, items_by_sector),
                created_at=created_at,
                updated_at=created_at + timedelta(hours=random.randint(1, 48)),
            )
            session.add(insp)
            session.flush()

            # Action plan
            is_approved = sc["status"] in [
                InspectionStatus.APPROVED,
                InspectionStatus.PENDING_CONSULTANT_VERIFICATION,
                InspectionStatus.COMPLETED,
            ]

            plan = ActionPlan(
                id=uuid.uuid4(),
                inspection_id=insp.id,
                summary_text=sc["summary"],
                strengths_text=sc["strengths"],
                stats_json=_build_stats(items_by_sector, sc["overall_score"], sc["max_score"]),
                approved_by_id=manager.id if is_approved else None,
                approved_at=(created_at + timedelta(days=1)) if is_approved else None,
            )
            session.add(plan)
            session.flush()

            # Action plan items
            order = 0
            for sector_name, items in items_by_sector.items():
                for it in items:
                    is_nc = it["orig_status"] != "Conforme"
                    is_resolved = is_nc and sc["resolve_ratio"] > 0 and random.random() < sc["resolve_ratio"]

                    deadline_days = random.choice([7, 14, 30, 60]) if is_nc else None
                    dl = (date.today() + timedelta(days=deadline_days)) if deadline_days else None

                    evidence_url = None
                    correction_note = None
                    if is_resolved:
                        evidence_url = f"/static/uploads/evidence/{uuid.uuid4()}_evidence.jpg"
                        correction_note = random.choice(CORRECTION_NOTES)

                    session.add(ActionPlanItem(
                        id=uuid.uuid4(),
                        action_plan_id=plan.id,
                        problem_description=it["problem"],
                        corrective_action=it["action"],
                        legal_basis=it["legal"],
                        severity=it["severity"],
                        status=ActionPlanItemStatus.RESOLVED if is_resolved else ActionPlanItemStatus.OPEN,
                        original_status=it["orig_status"],
                        original_score=it["score"],
                        ai_suggested_deadline=f"{deadline_days} dias" if deadline_days else None,
                        deadline_date=dl,
                        sector=sector_name,
                        order_index=order,
                        correction_notes=correction_note,
                        evidence_image_url=evidence_url,
                        current_status="Corrigido" if is_resolved else ("Pendente" if is_nc else "Conforme"),
                    ))
                    order += 1
                    total_items += 1

            # Job record
            session.add(Job(
                id=uuid.uuid4(),
                type="PROCESS_PDF",
                status=JobStatus.COMPLETED,
                company_id=uuid.UUID(COMPANY_ID),
                input_payload={
                    "file_id": insp.drive_file_id,
                    "filename": f"Relatorio_{est.name.replace(f' [{DEMO_TAG}]', '')}.pdf",
                    "establishment_name": est.name.replace(f" [{DEMO_TAG}]", ""),
                    "establishment_id": str(est.id),
                    "tag": DEMO_TAG,
                },
                created_at=created_at - timedelta(minutes=30),
                finished_at=created_at,
                cost_tokens_input=random.randint(15000, 45000),
                cost_tokens_output=random.randint(8000, 25000),
                execution_time_seconds=random.uniform(15, 90),
                api_calls_count=random.randint(2, 5),
                cost_input_usd=random.uniform(0.01, 0.08),
                cost_output_usd=random.uniform(0.005, 0.04),
            ))

            session.flush()
            insp_count += 1
            est_label = est.name.replace(f" [{DEMO_TAG}]", "")
            print(f"  Inspection {insp_count}: {est_label} | {sc['status'].value} | {sc['overall_score']}% | {order} items")

        session.commit()
        print(f"\nDone! Demo data for users seeded successfully.")
        print(f"  Tag: [{DEMO_TAG}]")
        print(f"  New establishments: {len(new_ests)}")
        print(f"  Inspections: {insp_count}")
        print(f"  Total items: {total_items}")
        print(f"\n  Login as gestor: {MANAGER_EMAIL}")
        print(f"  Login as consultor: {CONSULTANT_EMAIL}")
        print(f"\n  Delete with: python3 seed_demo_users.py --delete")


def delete():
    from sqlalchemy import String

    with app.app_context():
        session = next(get_db())

        print(f"Removing demo user data (tag: [{DEMO_TAG}])...")

        # 1. Delete jobs
        jobs = session.query(Job).filter(
            Job.input_payload.cast(String).contains(DEMO_TAG)
        ).all()
        for j in jobs:
            session.delete(j)
        print(f"  Deleted {len(jobs)} jobs")

        # 2. Delete inspections (with plans + items)
        inspections = session.query(Inspection).filter(
            Inspection.drive_file_id.like("demo_usr_%")
        ).all()
        for insp in inspections:
            if insp.action_plan:
                session.query(ActionPlanItem).filter(
                    ActionPlanItem.action_plan_id == insp.action_plan.id
                ).delete()
                session.delete(insp.action_plan)
            session.delete(insp)
        print(f"  Deleted {len(inspections)} inspections (with plans + items)")

        # 3. Delete contacts for demo establishments
        demo_ests = session.query(Establishment).filter(
            Establishment.name.contains(DEMO_TAG)
        ).all()
        for est in demo_ests:
            contacts = session.query(Contact).filter(
                Contact.establishment_id == est.id
            ).all()
            for ct in contacts:
                session.delete(ct)

        # 4. Remove M2M links and delete establishments
        consultant = session.query(User).filter(User.email == CONSULTANT_EMAIL).first()
        if consultant:
            consultant.establishments = [
                e for e in consultant.establishments
                if DEMO_TAG not in e.name
            ]

        for est in demo_ests:
            est.users = []  # Clear any remaining M2M links
            session.delete(est)
        print(f"  Deleted {len(demo_ests)} establishments (with contacts)")

        session.commit()
        print(f"\nDone! All demo user data removed.")


if __name__ == "__main__":
    if "--delete" in sys.argv:
        delete()
    else:
        seed()
