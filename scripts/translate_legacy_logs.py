
import os
import sys
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))
sys.path.append(os.getcwd())

from src.database import get_db, engine
from src.models_db import Inspection

def translate_logs():
    print("Iniciando tradução de logs antigos...")
    
    replacements = {
        "Started processing": "Iniciando processamento de",
        "Downloading from Drive...": "Baixando arquivo do Drive...",
        "Download complete": "Download concluído",
        "Sending to OpenAI...": "Enviando para análise da IA (OpenAI)...",
        "Analysis complete": "Análise de IA concluída",
        "Generating Action Plan PDF...": "Gerando PDF do Plano de Ação...",
        "PDF generated:": "PDF gerado com sucesso:",
        "Saving to Database...": "Salvando dados no Banco de Dados...",
        "Processing completely finished.": "Processamento finalizado com sucesso.",
        "Duplicate file detected.": "Arquivo duplicado detectado."
    }

    with engine.connect() as conn:
        # Busca inspeções com logs
        # Nota: processing_logs é JSONB, mas vamos tratar como texto/dict no python
        # Melhor iterar e update via ORM ou SQL direto se for complexo.
        # Vamos via SQL direto update com replace string simples onde der, ou python loop.
        # Python loop é mais seguro para JSON list.
        pass

    # Usando Session
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        inspections = session.query(Inspection).filter(Inspection.processing_logs.isnot(None)).all()
        count = 0
        
        for insp in inspections:
            logs = insp.processing_logs
            if not logs: continue
            
            modified = False
            new_logs = []
            
            for entry in logs:
                msg = entry.get('message', '')
                original_msg = msg
                
                # Tenta match exato ou parcial
                for en, pt in replacements.items():
                    if en in msg and pt not in msg: # Evita traduzir o que já está traduzido
                        if en == "Started processing":
                             # Mantém o filename se tiver
                             # "Started processing file.pdf" -> "Iniciando processamento de file.pdf"
                             msg = msg.replace(en, "Iniciando processamento de").replace("Iniciando processamento de ", "Iniciando processamento de ")
                        else:
                             msg = msg.replace(en, pt)
                
                if msg != original_msg:
                    entry['message'] = msg
                    modified = True
                
                new_logs.append(entry)
            
            if modified:
                # Forçar update do JSON
                insp.processing_logs = list(new_logs) 
                count += 1
                print(f"Atualizado ID: {insp.id}")

        if count > 0:
            session.commit()
            print(f"Sucesso! {count} inspeções tiveram seus logs traduzidos.")
        else:
            print("Nenhum log precisou ser traduzido.")

    except Exception as e:
        session.rollback()
        print(f"Erro: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    translate_logs()
