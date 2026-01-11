
import os
import shutil
import glob
import time
from datetime import datetime, timedelta

def get_size(path):
    total_size = 0
    if os.path.isfile(path):
        return os.path.getsize(path)
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def format_bytes(size):
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def clean_workspace():
    print("🧹 Iniciando Limpeza Automática de Disco (Zero Cost Maintenance)...")
    freed_space = 0
    
    # 1. Redundant Virtual Envs (Keep 'venv', delete others)
    # Adjust based on preference, assuming 'venv' is valid based on user context
    redundant_venvs = ['.venv', '.tmp_venv'] 
    for venv in redundant_venvs:
        if os.path.exists(venv):
            size = get_size(venv)
            print(f"🗑️  Removendo ambiente virtual redundante: {venv} ({format_bytes(size)})")
            try:
                shutil.rmtree(venv)
                freed_space += size
            except Exception as e:
                print(f"❌ Erro ao remover {venv}: {e}")

    # 2. Old Logs (*.log)
    # Remove logs older than 3 days or larger than 10MB
    log_files = glob.glob("**/*.log", recursive=True)
    today = time.time()
    for log in log_files:
        if "venv" in log: continue # Skip logs inside venv
        
        stats = os.stat(log)
        size = stats.st_size
        age_days = (today - stats.st_mtime) / (24 * 3600)
        
        if age_days > 3 or size > 10 * 1024 * 1024:
            print(f"🗑️  Removendo log antigo/grande: {log} ({format_bytes(size)})")
            try:
                os.remove(log)
                freed_space += size
            except Exception as e:
                print(f"❌ Erro ao remover {log}: {e}")

    # 3. Cache & Temp Files
    # __pycache__ and .DS_Store
    for root, dirs, files in os.walk("."):
        if "venv" in root: continue
        
        for d in dirs:
            if d == "__pycache__":
                path = os.path.join(root, d)
                size = get_size(path)
                # print(f"🗑️  Limpando cache: {path}") # Verbose
                try:
                    shutil.rmtree(path)
                    freed_space += size
                except: pass
        
        for f in files:
            if f == ".DS_Store":
                 path = os.path.join(root, f)
                 try:
                     size = os.path.getsize(path)
                     os.remove(path)
                     freed_space += size
                 except: pass

    # 4. Old Artifacts (Images/Videos in brain)
    # CAREFUL: Only delete large media files older than 7 days
    brain_dir = os.path.expanduser("~/.gemini/antigravity/brain")
    if os.path.exists(brain_dir):
        # Find all .webp, .png, .mp4 files recursively
        media_files = []
        for ext in ["*.webp", "*.png", "*.mp4", "*.mov"]:
            media_files.extend(glob.glob(os.path.join(brain_dir, "**", ext), recursive=True))
            
        for f in media_files:
            try:
                stats = os.stat(f)
                size = stats.st_size
                age_days = (today - stats.st_mtime) / (24 * 3600)
                
                # Rule: Delete if > 5MB OR older than 14 days
                if size > 5 * 1024 * 1024 or age_days > 14:
                     print(f"🖼️  Removendo artefato antigo: {os.path.basename(f)} ({format_bytes(size)})")
                     os.remove(f)
                     freed_space += size
            except: pass

    # 5. Debug Text Files and Server Logs
    # Delete debug_*.txt and server_*.log
    debug_files = glob.glob("debug_*.txt") + glob.glob("server_*.log")
    for f in debug_files:
        try:
             size = os.path.getsize(f)
             print(f"🐞 Removendo arquivo de debug: {f} ({format_bytes(size)})")
             os.remove(f)
             freed_space += size
        except: pass

    # 6. Temporary PDF Uploads (Local Evidence)
    # Files in src/static/uploads/evidence older than 24h
    upload_dirs = ["src/static/uploads/evidence", "data/backup"]
    for d in upload_dirs:
        if os.path.exists(d):
            for f in glob.glob(os.path.join(d, "*")):
                try:
                    if os.path.isfile(f):
                        stats = os.stat(f)
                        size = stats.st_size
                        age_hours = (today - stats.st_mtime) / 3600
                        
                        # Delete if older than 24 hours
                        if age_hours > 24:
                             print(f"📂 Removendo upload/backup temporário antigo: {f} ({format_bytes(size)})")
                             os.remove(f)
                             freed_space += size
                except: pass

    print(f"\n✅ Limpeza Concluída!")
    print(f"🚀 Espaço Liberado: {format_bytes(freed_space)}")
    
if __name__ == "__main__":
    clean_workspace()
