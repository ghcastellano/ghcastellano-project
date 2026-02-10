"""
Seed script to add fake data for pagination testing.
Run: python seed_test_data.py
Delete with: python seed_test_data.py --delete
"""
import sys
import uuid
from datetime import datetime, timedelta
import random

from werkzeug.security import generate_password_hash

from src.app import app
from src.database import get_db
from src.models_db import (
    Company, Establishment, User, UserRole,
    Inspection, InspectionStatus, Job, JobStatus,
    ActionPlan, ActionPlanItem,
)


SEED_TAG = "SEED_TEST"  # Tag to identify seeded data for cleanup


def seed():
    """Create ~30 companies, ~60 establishments, ~25 managers, ~120 inspections, ~50 jobs."""
    with app.app_context():
        session = next(get_db())

        print("Seeding test data for pagination...")

        # 1. Companies (30)
        companies = []
        company_names = [
            "Supermercado Bom Preco", "Rede Sabor & Saude", "Hipermercado Central",
            "Mercado do Joao", "Atacadao Economia", "Padaria Pao Quente",
            "Restaurante Sabor Caseiro", "Lanchonete Express", "Frigorífico Premium",
            "Distribuidora Alimentos SA", "Cafeteria Aroma", "Pizzaria Bella Napoli",
            "Churrascaria Fogo de Chao", "Sorveteria Gelato", "Confeitaria Doce Mel",
            "Hortifruti Natural", "Emporio Gourmet", "Loja Organica Verde",
            "Hamburgueria Artesanal", "Sushi House Tokyo", "Pastelaria do Ze",
            "Acougue Boi Gordo", "Peixaria Oceano", "Queijaria Minas",
            "Doceria Brigadeiro", "Bar e Petiscos Lua", "Cantina Italiana",
            "Food Truck Sabores", "Mercearia Esquina", "Panificadora Trigo Dourado",
        ]
        for name in company_names:
            c = Company(
                id=uuid.uuid4(),
                name=f"{name} [{SEED_TAG}]",
                cnpj=f"{random.randint(10,99)}.{random.randint(100,999)}.{random.randint(100,999)}/0001-{random.randint(10,99)}",
            )
            session.add(c)
            companies.append(c)

        session.flush()
        print(f"  Created {len(companies)} companies")

        # 2. Establishments (2 per company = 60)
        establishments = []
        for comp in companies:
            for i in range(2):
                est = Establishment(
                    id=uuid.uuid4(),
                    company_id=comp.id,
                    name=f"Filial {i+1} - {comp.name.replace(f' [{SEED_TAG}]', '')}",
                    code=f"F{random.randint(100,999)}",
                    responsible_name=f"Resp. {random.choice(['Maria','Joao','Ana','Pedro','Carlos','Lucia'])}",
                    responsible_email=f"resp{random.randint(1,999)}@test.com",
                    responsible_phone=f"(11) 9{random.randint(1000,9999)}-{random.randint(1000,9999)}",
                )
                session.add(est)
                establishments.append(est)

        session.flush()
        print(f"  Created {len(establishments)} establishments")

        # 3. Managers (25 - spread across companies)
        managers = []
        first_names = ["Ana", "Bruno", "Carla", "Diego", "Elena", "Felipe",
                       "Gabriela", "Hugo", "Isabela", "Jonas", "Karen", "Lucas",
                       "Marina", "Nelson", "Olivia", "Paulo", "Quezia", "Rafael",
                       "Sofia", "Thiago", "Ursula", "Victor", "Wanda", "Xavier", "Yara"]
        for i, name in enumerate(first_names):
            comp = companies[i % len(companies)]
            u = User(
                id=uuid.uuid4(),
                name=f"{name} Gestor [{SEED_TAG}]",
                email=f"gestor.{name.lower()}.{SEED_TAG.lower()}@test.com",
                password_hash=generate_password_hash("test123"),
                role=UserRole.MANAGER,
                company_id=comp.id,
                must_change_password=False,
            )
            session.add(u)
            managers.append(u)

        session.flush()
        print(f"  Created {len(managers)} managers")

        # 4. Inspections (120 - spread across establishments)
        statuses = list(InspectionStatus)
        inspections = []
        for i in range(120):
            est = random.choice(establishments)
            days_ago = random.randint(0, 90)
            status = random.choice(statuses)
            insp = Inspection(
                id=uuid.uuid4(),
                establishment_id=est.id,
                drive_file_id=f"seed_file_{uuid.uuid4().hex[:12]}",
                status=status,
                file_hash=f"seed_hash_{uuid.uuid4().hex[:16]}",
                ai_raw_response={
                    "pontuacao_geral": random.randint(40, 95),
                    "pontuacao_maxima_geral": 100,
                    "resumo_geral": f"Inspecao {i+1} [{SEED_TAG}] - resultado de teste",
                    "areas_inspecionadas": [],
                },
                created_at=datetime.utcnow() - timedelta(days=days_ago, hours=random.randint(0, 23)),
            )
            session.add(insp)
            inspections.append(insp)

        session.flush()
        print(f"  Created {len(inspections)} inspections")

        # 5. Jobs (50)
        job_statuses = [JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.COMPLETED, JobStatus.FAILED]
        for i in range(50):
            est = random.choice(establishments)
            comp = None
            for c in companies:
                if c.id == est.company_id:
                    comp = c
                    break
            status = random.choice(job_statuses)
            job = Job(
                id=uuid.uuid4(),
                type="PROCESS_PDF",
                status=status,
                company_id=comp.id if comp else companies[0].id,
                input_payload={
                    "file_id": f"seed_job_{uuid.uuid4().hex[:8]}",
                    "filename": f"Relatorio_Job_{i+1}_{SEED_TAG}.pdf",
                    "establishment_name": est.name,
                    "establishment_id": str(est.id),
                },
                error_log=f"ERR_TEST: Simulated error for job {i+1}" if status == JobStatus.FAILED else None,
                created_at=datetime.utcnow() - timedelta(hours=random.randint(0, 48)),
                finished_at=datetime.utcnow() - timedelta(hours=random.randint(0, 24)) if status in [JobStatus.COMPLETED, JobStatus.FAILED] else None,
                cost_tokens_input=random.randint(1000, 50000),
                cost_tokens_output=random.randint(500, 20000),
                execution_time_seconds=random.uniform(5, 120) if status != JobStatus.PENDING else None,
            )
            session.add(job)

        session.flush()
        print(f"  Created 50 jobs")

        session.commit()
        print("\nDone! Fake data seeded successfully.")
        print(f"Look for items tagged with [{SEED_TAG}] in the UI.")


def delete():
    """Remove all seeded test data."""
    with app.app_context():
        session = next(get_db())

        print("Removing seeded test data...")

        # Delete jobs with seed tag in payload
        jobs = session.query(Job).filter(
            Job.input_payload.cast(String).contains(SEED_TAG)
        ).all()
        for j in jobs:
            session.delete(j)
        print(f"  Deleted {len(jobs)} jobs")

        # Delete inspections with seed tag (by drive_file_id prefix: seed_file_% and seed_plan_%)
        from sqlalchemy import or_
        inspections = session.query(Inspection).filter(
            or_(
                Inspection.drive_file_id.like("seed_file_%"),
                Inspection.drive_file_id.like("seed_plan_%"),
            )
        ).all()
        for insp in inspections:
            if insp.action_plan:
                session.query(ActionPlanItem).filter(
                    ActionPlanItem.action_plan_id == insp.action_plan.id
                ).delete()
                session.delete(insp.action_plan)
            session.delete(insp)
        print(f"  Deleted {len(inspections)} inspections")

        # Delete users with seed tag (managers + consultants)
        seed_users = session.query(User).filter(
            User.name.contains(SEED_TAG)
        ).all()
        for u in seed_users:
            # Remove establishment associations for consultants
            u.establishments = []
            session.delete(u)
        print(f"  Deleted {len(seed_users)} users (managers + consultants)")

        # Delete establishments with seed tag (from any company)
        seed_ests = session.query(Establishment).filter(
            Establishment.name.contains(SEED_TAG)
        ).all()
        for est in seed_ests:
            session.delete(est)
        print(f"  Deleted {len(seed_ests)} establishments")

        # Delete seed companies
        seed_companies = session.query(Company).filter(
            Company.name.contains(SEED_TAG)
        ).all()
        for comp in seed_companies:
            # Delete remaining establishments from seed companies
            ests = session.query(Establishment).filter(
                Establishment.company_id == comp.id
            ).all()
            for est in ests:
                session.delete(est)
            session.delete(comp)
        print(f"  Deleted {len(seed_companies)} seed companies")

        session.commit()
        print("\nDone! All seeded data removed.")


if __name__ == "__main__":
    from sqlalchemy import String

    if "--delete" in sys.argv:
        delete()
    else:
        seed()
