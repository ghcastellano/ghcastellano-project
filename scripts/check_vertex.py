import vertexai
from vertexai.generative_models import GenerativeModel
from google.oauth2.service_account import Credentials
import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("GCP_LOCATION", "us-central1")

print(f"Project: {PROJECT_ID}")
print(f"Location: {LOCATION}")

try:
    print("Carregando credenciais...")
    credentials = Credentials.from_service_account_file("credentials.json")
    print(f"Email: {credentials.service_account_email}")

    print("\n--- Testando Gemini 2.5 Pro ---")
    try:
        from vertexai.generative_models import GenerativeModel
        vertexai.init(project=PROJECT_ID, location="us-central1", credentials=credentials)
        model = GenerativeModel("gemini-2.5-pro")
        response = model.generate_content("Ping")
        print(f"SUCESSO com Gemini 2.5 Pro! Resposta: {response.text}")
    except Exception as e:
        print(f"Falha Gemini 2.5 Pro: {e}")

except Exception as e:
    print(f"\nERRO: {e}")
