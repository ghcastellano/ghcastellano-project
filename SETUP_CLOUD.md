# ☁️ Guia de Configuração Cloud (Premium + Zero Cost)

Este guia descreve os passos manuais necessários no Google Cloud Console para ativar as novas funcionalidades de "Sincronização Automática do Drive" e "Armazenamento de Fotos".

## 1. Ativar Google Cloud Storage (Fotos)
Para que as fotos das evidências não se percam quando o Cloud Run reiniciar, usaremos um Bucket.

1.  Acesse o [Console do Google Cloud Storage](https://console.cloud.google.com/storage/browser).
2.  Clique em **CRIAR**.
3.  **Nome:** Escolha um nome único (ex: `inspecao-sanitaria-assets`).
4.  **Localização:** `Region` > `us-central1` (ou a mesma do seu Cloud Run para latência zero).
5.  **Classe de Armazenamento:** `Standard`.
6.  **Controle de Acesso:** Escolha `Uniforme`.
7.  **Proteção de Dados:** Desmarque "Impedir acesso público" (se quisermos links públicos fáceis) OU Mantenha marcado se for configurar Signed URLs depois. *Recomendação MVP: Desmarque para facilitar, mas em dados sensíveis use Signed URLs.*
    *   *Dica:* Para deixar público para leitura: Na lista de buckets -> Permissões -> Adicionar principal -> `allUsers` -> Role: `Storage Object Viewer`.
8.  **Variável de Ambiente:**
    *   No Cloud Run, adicione a variável: `GCP_STORAGE_BUCKET` = `inspecao-sanitaria-assets`.

## 2. Configurar Cloud Scheduler (Sync Drive)
Para fazer o sistema "acordar" e checar o Drive sozinho.

1.  Acesse o [Cloud Scheduler](https://console.cloud.google.com/cloudscheduler).
2.  Clique em **CRIAR JOB**.
3.  **Nome:** `sync-drive-cron`.
4.  **Região:** `us-east1` (ou a mesma do app).
5.  **Frequência:** `*/15 * * * *` (A cada 15 minutos) ou `*/10 * * * *`.
6.  **Fuso horário:** `Brasilia Standard Time`.
7.  **Destino (Target):** `HTTP`.
8.  **URL:** `https://<SEU-DOMINIO-CLOUD-RUN>/admin/api/cron/sync_drive`.
9.  **Método:** `POST`.
10. **Auth Header:**
    *   Selecione `Add OIDC Token`.
    *   **Service Account:** Selecione a conta de serviço padrão do Cloud Run (Compute Engine default service account) ou a que você criou customizada.
    *   **Audience (Público-alvo):** Coloque a mesma URL do endpoint (`https://<SEU-DOMINIO-CLOUD-RUN>/admin/api/cron/sync_drive`).

## 3. Permissões da Service Account
A conta de serviço do Cloud Run precisa de permissão para ler/escrever no Bucket.

1.  Vá em **IAM & Admin**.
2.  Localize a conta de serviço que o Cloud Run usa (ex: `...-compute@developer.gserviceaccount.com`).
3.  Edite e **Adicione o papel (Role):** `Storage Object Admin` (Admin de Objetos do Storage).

---

## ✅ Resumo das Variáveis Novas no Cloud Run
Adicione/Verifique estas variáveis no painel do Cloud Run:

| Variável | Valor Exemplo | Descrição |
| :--- | :--- | :--- |
| `GCP_STORAGE_BUCKET` | `meu-bucket-assets` | Nome do bucket criado |
| `WEBHOOK_SECRET_TOKEN` | `secreta123...` | Token para proteger o Cron (Opcional se usar OIDC) |

Feito isso, o sistema estará 100% autônomo! 🚀
