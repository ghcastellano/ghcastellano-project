"""
Validador de coerência pasta-documento para Google Drive.

Este módulo valida se documentos de inspeção foram enviados para a pasta correta
(empresa/estabelecimento) e move automaticamente para pasta correta se necessário.
"""

import logging
from typing import Optional, Tuple, Dict
from src.models_db import Company, Establishment, Inspection
from src.services.drive_service import DriveService

logger = logging.getLogger(__name__)

class DocumentFolderValidator:
    """Valida e corrige localização de documentos no Drive."""
    
    def __init__(self, drive_service: DriveService, db_session):
        self.drive_service = drive_service
        self.db = db_session
        
    def extract_company_establishment_from_json(self, json_data: dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrai nome da empresa e estabelecimento do JSON do relatório.
        
        Returns:
            (company_name, establishment_name) ou (None, None) se não encontrar
        """
        try:
            # Tentar diferentes formatos de JSON
            # Formato 1: Dados diretos no JSON
            company_name = json_data.get('nome_empresa') or json_data.get('empresa')
            establishment_name = json_data.get('nome_estabelecimento') or json_data.get('estabelecimento')
            
            # Formato 2: Dentro de um objeto 'metadados'
            if not company_name and 'metadados' in json_data:
                company_name = json_data['metadados'].get('empresa')
                establishment_name = json_data['metadados'].get('estabelecimento')
            
            # Formato 3: Dentro de 'dados_estabelecimento'
            if not establishment_name and 'dados_estabelecimento' in json_data:
                establishment_name = json_data['dados_estabelecimento'].get('nome')
            
            return company_name, establishment_name
            
        except Exception as e:
            logger.error(f"Erro ao extrair dados do JSON: {e}")
            return None, None
    
    def find_correct_folder(self, company_name: str, establishment_name: str) -> Optional[str]:
        """
        Busca ID da pasta correta com base nos nomes da empresa e estabelecimento.
        
        Returns:
            folder_id ou None se não encontrar
        """
        try:
            # Buscar estabelecimento no banco
            establishment = self.db.query(Establishment).filter(
                Establishment.name.ilike(f"%{establishment_name}%")
            ).first()
            
            if not establishment:
                logger.warning(f"Estabelecimento '{establishment_name}' não encontrado no banco")
                return None
            
            # Verificar se empresa bate (validação adicional)
            if establishment.company and company_name:
                if company_name.lower() not in establishment.company.name.lower():
                    logger.warning(
                        f"Empresa no JSON ('{company_name}') não corresponde à "
                        f"empresa do estabelecimento ('{establishment.company.name}')"
                    )
            
            return establishment.drive_folder_id
            
        except Exception as e:
            logger.error(f"Erro ao buscar pasta correta: {e}")
            return None
    
    def validate_and_fix_location(self, file_id: str, file_info: dict) -> Dict[str, any]:
        """
        Valida se arquivo está na pasta correta e move se necessário.
        
        Args:
            file_id: ID do arquivo no Drive
            file_info: Informações do arquivo (name, parents, etc)
            
        Returns:
            dict com resultado da validação:
            {
                'valid': bool,
                'moved': bool,
                'from_folder': str,
                'to_folder': str,
                'company_name': str,
                'establishment_name': str,
                'message': str
            }
        """
        result = {
            'valid': True,
            'moved': False,
            'from_folder': None,
            'to_folder': None,
            'company_name': None,
            'establishment_name': None,
            'message': 'Arquivo na pasta correta'
        }
        
        try:
            # 1. Buscar JSON do relatório
            if not file_info.get('name', '').endswith('.json'):
                return result  # Não é JSON, pular validação
            
            json_data = self.drive_service.read_json(file_id)
            if not json_data:
                result['message'] = 'Não foi possível ler JSON'
                return result
            
            # 2. Extrair dados
            company_name, establishment_name = self.extract_company_establishment_from_json(json_data)
            result['company_name'] = company_name
            result['establishment_name'] = establishment_name
            
            if not establishment_name:
                result['message'] = 'Estabelecimento não identificado no JSON'
                return result
            
            # 3. Buscar pasta correta
            correct_folder_id = self.find_correct_folder(company_name, establishment_name)
            if not correct_folder_id:
                result['message'] = f'Pasta do estabelecimento "{establishment_name}" não encontrada'
                return result
            
            # 4. Verificar se está na pasta correta
            current_parents = file_info.get('parents', [])
            if not current_parents:
                result['message'] = 'Arquivo sem pasta parent'
                return result
            
            current_folder = current_parents[0]
            result['from_folder'] = current_folder
            result['to_folder'] = correct_folder_id
            
            if current_folder == correct_folder_id:
                result['valid'] = True
                result['message'] = 'Arquivo já está na pasta correta'
                return result
            
            # 5. PASTA ERRADA! Mover para pasta correta
            logger.warning(
                f"📂 Arquivo '{file_info.get('name')}' está na pasta ERRADA! "
                f"Movendo de {current_folder} para {correct_folder_id}"
            )
            
            self.drive_service.move_file(file_id, correct_folder_id)
            
            result['valid'] = False
            result['moved'] = True
            result['message'] = (
                f"⚠️ Arquivo movido! Estava em pasta errada. "
                f"Estabelecimento: {establishment_name}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Erro na validação de localização: {e}")
            result['message'] = f'Erro na validação: {str(e)}'
            return result
    
    def create_alert_for_manager(self, file_info: dict, validation_result: dict):
        """
        Cria alerta para o gestor sobre movimento de arquivo.
        
        Por enquanto apenas loga, no futuro pode enviar email ou notificação in-app.
        """
        if validation_result.get('moved'):
            log_message = (
                f"🚨 ALERTA PARA GESTOR: "
                f"Arquivo '{file_info.get('name')}' foi movido automaticamente. "
                f"Estabelecimento: {validation_result.get('establishment_name')}. "
                f"Pasta origem: {validation_result.get('from_folder')}. "
                f"Pasta destino: {validation_result.get('to_folder')}."
            )
            logger.warning(log_message)
            
            # TODO: Implementar notificação real ao gestor
            # - Email
            # - Notificação no dashboard
            # - Registro na tabela de auditoria
