#!/usr/bin/env python3
"""
Script para limpar registros órfãos no banco de dados.
- Inspections com status PROCESSING que ficaram travadas
- Jobs com status PENDING que ficaram travados
"""
import sys
import os
from datetime import datetime, timedelta, timezone

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from src.database import get_db, init_db
from src.models_db import Inspection, InspectionStatus, Job, JobStatus

def cleanup_orphans(dry_run=True, threshold_minutes=10):
    """
    Limpa registros órfãos.

    Args:
        dry_run: Se True, apenas mostra o que seria feito sem alterar o banco.
        threshold_minutes: Tempo em minutos para considerar um Job como travado.
    """
    init_db()
    db = next(get_db())

    try:
        print("\n" + "="*60)
        print("🧹 LIMPEZA DE REGISTROS ÓRFÃOS")
        print("="*60)

        if dry_run:
            print("⚠️  MODO DRY-RUN: Nenhuma alteração será feita\n")
        else:
            print("🔴 MODO PRODUÇÃO: Alterações serão aplicadas!\n")

        # 1. Inspections órfãs (status PROCESSING)
        print("\n📋 INSPECTIONS COM STATUS 'PROCESSING':")
        print("-"*40)

        orphan_inspections = db.query(Inspection).filter(
            Inspection.status == InspectionStatus.PROCESSING
        ).all()

        if not orphan_inspections:
            print("✅ Nenhuma inspection órfã encontrada.")
        else:
            for insp in orphan_inspections:
                print(f"  ID: {insp.id}")
                print(f"  File ID: {insp.drive_file_id}")
                print(f"  Establishment: {insp.establishment.name if insp.establishment else 'N/A'}")
                print(f"  Created: {insp.created_at}")
                print()

                if not dry_run:
                    db.delete(insp)
                    print(f"  ❌ REMOVIDA")
                    print()

        # 2. Jobs travados (status PENDING há mais de threshold_minutes)
        print(f"\n📋 JOBS COM STATUS 'PENDING' (threshold: {threshold_minutes} min):")
        print("-"*40)

        now = datetime.now(timezone.utc)
        threshold = now - timedelta(minutes=threshold_minutes)

        stuck_jobs = db.query(Job).filter(
            Job.status == JobStatus.PENDING
        ).all()

        if not stuck_jobs:
            print("✅ Nenhum job pendente encontrado.")
        else:
            for job in stuck_jobs:
                payload = job.input_payload or {}
                created_at = job.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age = now - created_at

                print(f"  ID: {job.id}")
                print(f"  Arquivo: {payload.get('filename', 'N/A')}")
                print(f"  Company ID: {job.company_id}")
                print(f"  Created: {job.created_at}")
                print(f"  Idade: {age}")

                is_stuck = created_at < threshold

                if is_stuck:
                    print(f"  Status: 🔴 TRAVADO")
                    if not dry_run:
                        job.status = JobStatus.FAILED
                        job.error_log = "Timeout: Job ficou travado em PENDING"
                        job.finished_at = datetime.now(timezone.utc)
                        print(f"  ⚠️ MARCADO COMO FAILED")
                else:
                    print(f"  Status: ⏳ Pendente (< {threshold_minutes} min)")
                print()

        # 3. Commit das alterações
        if not dry_run:
            db.commit()
            print("\n✅ Alterações salvas no banco de dados.")

        print("\n" + "="*60)
        print("🏁 LIMPEZA CONCLUÍDA")
        print("="*60)

        # Resumo
        stuck_count = len([j for j in stuck_jobs if j.created_at.replace(tzinfo=timezone.utc) < threshold]) if stuck_jobs else 0
        print(f"\nResumo:")
        print(f"  - Inspections órfãs: {len(orphan_inspections)}")
        print(f"  - Jobs travados: {stuck_count}")

        if dry_run and (orphan_inspections or stuck_count > 0):
            print(f"\n💡 Para aplicar as alterações, execute:")
            print(f"   python scripts/cleanup_orphans.py --apply")

    except Exception as e:
        print(f"❌ Erro: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    apply = "--apply" in sys.argv or "-a" in sys.argv

    # Pegar threshold customizado
    threshold = 10  # default
    for arg in sys.argv:
        if arg.startswith("--threshold="):
            threshold = int(arg.split("=")[1])
        elif arg == "--force":
            threshold = 0  # Força limpeza de todos os pendentes

    cleanup_orphans(dry_run=not apply, threshold_minutes=threshold)
