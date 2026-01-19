
import sys
import os
import logging

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from dotenv import load_dotenv
load_dotenv()

from src.app import app
from src import database

from src.models_db import Company, Establishment
from src.services.drive_service import drive_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_drive")


def backfill_drive_folders():
    """
    Garante que todas as Empresas e Estabelecimentos tenham uma Pasta no Drive correspondente.
    """
    with app.app_context():
        session = next(database.get_db())
        
        # 1. Backfill Companies
        companies = session.query(Company).all()
        logger.info(f"Verificando {len(companies)} Empresas...")
        
        for company in companies:
            if not company.drive_folder_id:
                logger.info(f"🚫 Empresa '{company.name}' sem pasta. Criando...")
                folder_id, web_link = drive_service.create_folder(company.name, parent_id=None)
                if folder_id:
                    company.drive_folder_id = folder_id
                    logger.info(f"✅ Pasta Criada para Empresa '{company.name}': {folder_id}")
                else:
                    logger.error(f"❌ Falha ao criar pasta para Empresa '{company.name}'")
            else:
                 logger.debug(f"Empresa '{company.name}' já possui pasta: {company.drive_folder_id}")
        
        session.commit()
        
        # 2. Backfill Establishments
        establishments = session.query(Establishment).all()
        logger.info(f"Verificando {len(establishments)} Estabelecimentos...")
        
        for est in establishments:
            if not est.drive_folder_id:
                logger.info(f"🚫 Estabelecimento '{est.name}' sem pasta. Criando...")
                
                # Get Parent Folder (Company)
                parent_id = None
                if est.company and est.company.drive_folder_id:
                    parent_id = est.company.drive_folder_id
                
                if not parent_id:
                    logger.warning(f"⚠️ Estabelecimento '{est.name}' sem Empresa Pai ou Empresa sem Pasta. Criando no ROOT.")
                
                folder_id, web_link = drive_service.create_folder(est.name, parent_id=parent_id)
                if folder_id:
                    est.drive_folder_id = folder_id
                    logger.info(f"✅ Pasta Criada para Estabelecimento '{est.name}': {folder_id} (Pai: {parent_id})")
                else:
                    logger.error(f"❌ Falha ao criar pasta para Estabelecimento '{est.name}'")
            else:
                logger.debug(f"Estabelecimento '{est.name}' já possui pasta: {est.drive_folder_id}")
                
        session.commit()
        logger.info("✨ Backfill Completo.")

if __name__ == "__main__":
    backfill_drive_folders()
