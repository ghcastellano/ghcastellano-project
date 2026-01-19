"""
Script para compartilhar todas as pastas do Drive com o usuário principal.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.app import app, drive_service
from src.models_db import Company, Establishment
from src import database
import logging

logger = logging.getLogger(__name__)

def share_folder(folder_id, email, role='writer'):
    """Compartilha uma pasta do Drive com um email."""
    if not drive_service.service:
        logger.error("Drive service não disponível")
        return False
    
    try:
        permission = {
            'type': 'user',
            'role': role,  # 'reader', 'writer', 'commenter', 'owner'
            'emailAddress': email
        }
        
        drive_service.service.permissions().create(
            fileId=folder_id,
            body=permission,
            fields='id',
            sendNotificationEmail=False  # Não enviar email de notificação para cada pasta
        ).execute()
        
        logger.info(f"✅ Pasta {folder_id} compartilhada com {email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao compartilhar pasta {folder_id}: {e}")
        return False

def main():
    target_email = 'ghcastellano@gmail.com'
    
    print(f"🔐 Compartilhando pastas do Drive com {target_email}...")
    print()
    
    with app.app_context():
        session = next(database.get_db())
        
        # 1. Compartilhar pasta ROOT se existir
        root_id = os.getenv('GDRIVE_ROOT_FOLDER_ID')
        if root_id:
            print(f"📁 Compartilhando pasta ROOT: {root_id}")
            if share_folder(root_id, target_email, role='writer'):
                print(f"✅ ROOT compartilhada!")
            else:
                print(f"⚠️ Falha ao compartilhar ROOT")
            print()
        
        # 2. Compartilhar pastas de empresas
        companies = session.query(Company).filter(Company.drive_folder_id != None).all()
        print(f"📂 Compartilhando {len(companies)} pasta(s) de Empresas...")
        
        for comp in companies:
            if comp.drive_folder_id:
                print(f"  Compartilhando: {comp.name}...", end=' ')
                if share_folder(comp.drive_folder_id, target_email, role='writer'):
                    print("✅")
                else:
                    print("❌")
        
        print()
        
        # 3. Compartilhar pastas de estabelecimentos
        establishments = session.query(Establishment).filter(Establishment.drive_folder_id != None).all()
        print(f"🏪 Compartilhando {len(establishments)} pasta(s) de Estabelecimentos...")
        
        for est in establishments:
            if est.drive_folder_id:
                print(f"  Compartilhando: {est.name}...", end=' ')
                if share_folder(est.drive_folder_id, target_email, role='writer'):
                    print("✅")
                else:
                    print("❌")
        
        print()
        print("🎉 Concluído!")
        
        session.close()

if __name__ == '__main__':
    main()
