import os
import sys
import logging
import structlog
from dotenv import load_dotenv

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()

# Load env
load_dotenv()

if __name__ == "__main__":
    from src.services.processor import processor_service
    
    # Detecta argumentos
    run_once = "--once" in sys.argv or os.getenv("CLOUD_RUN_JOB")
    
    logger.info("📢 Iniciando Worker (Wrapper)...")
    
    if run_once:
        logger.info("Modo Run-Once (Job/Poll) Ativado.")
        count = processor_service.process_pending_files()
        logger.info(f"Finalizado. Arquivos processados: {count}")
    else:
        logger.info("Modo Loop Infinito (Local Dev).")
        import time
        while True:
            try:
                processor_service.process_pending_files()
                time.sleep(10) # 10s Poll local
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error loop: {e}")
                time.sleep(10)

