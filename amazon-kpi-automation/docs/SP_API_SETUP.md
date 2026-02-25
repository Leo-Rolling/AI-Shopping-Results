# Guida Setup Amazon SP-API

Questa guida ti accompagna nella configurazione completa per collegare i tuoi seller account Amazon alla SP-API.

## Prerequisiti

- **2 account Amazon Seller Central**: uno per EU+UK, uno per US+CA
- **Credenziali LWA** (Login with Amazon): Client ID e Client Secret (già disponibili)
- **Brand Registry**: necessario per accedere a Search Query Performance e Brand Analytics

---

## Step 1: Creare un Account AWS (gratuito)

L'account AWS serve esclusivamente per il signing delle richieste API (Signature Version 4). Non comporta costi aggiuntivi.

1. Vai su https://aws.amazon.com e clicca **"Create an AWS Account"**
2. Completa la registrazione (email, password, dati di pagamento per verifica)
3. Seleziona il piano **Free Tier**

## Step 2: Creare un IAM User

L'IAM User fornisce le credenziali (Access Key) per firmare le richieste SP-API.

1. Vai alla **AWS IAM Console**: https://console.aws.amazon.com/iam/
2. Nel menu laterale, clicca **Users** → **Create user**
3. Nome utente: `sp-api-signer`
4. **Non** assegnare policy — questo utente serve solo per le credenziali di firma
5. Clicca **Create user**
6. Seleziona l'utente appena creato → tab **Security credentials**
7. Clicca **Create access key** → seleziona **Third-party service**
8. **Salva immediatamente** l'Access Key ID e il Secret Access Key

> **IMPORTANTE**: il Secret Access Key viene mostrato una sola volta. Salvalo in un luogo sicuro.

### (Opzionale) Creare un IAM Role

Amazon raccomanda l'uso di un IAM Role per maggiore sicurezza:

1. IAM Console → **Roles** → **Create role**
2. Trusted entity: **AWS account** → seleziona il tuo account
3. Aggiungi una policy inline:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": "execute-api:Invoke",
         "Resource": "arn:aws:execute-api:*:*:*"
       }
     ]
   }
   ```
4. Nome: `sp-api-role`
5. Salva il **Role ARN** (es. `arn:aws:iam::123456789012:role/sp-api-role`)

## Step 3: Registrare l'App SP-API in Seller Central

> Se hai già registrato l'app e hai le credenziali LWA, puoi saltare questo step.

### Per l'account EU+UK:

1. Login su **Seller Central EU**: https://sellercentral.amazon.co.uk
2. Vai su **Apps & Services** → **Develop Apps**
3. Se non sei ancora registrato come developer:
   - Clicca **Register** e compila il form
   - Data Protection Policy URL: puoi usare l'URL del tuo sito
4. Clicca **Add new app client**
   - Nome: `KPI Automation`
   - API Type: `SP API`
   - IAM ARN: inserisci l'ARN dell'utente IAM (o del role) creato nello Step 2

### Per l'account US+CA:

1. Login su **Seller Central NA**: https://sellercentral.amazon.com
2. Ripeti la stessa procedura

## Step 4: Self-Authorize e ottenere i Refresh Token

Questo è il passaggio più importante. Devi autorizzare la tua app per ciascun account seller.

### Account EU+UK:

1. Login su **Seller Central EU** (https://sellercentral.amazon.co.uk)
2. Vai su **Apps & Services** → **Develop Apps**
3. Trova la tua app e clicca **Edit App** → poi **Authorize**
4. Si aprirà una pagina di autorizzazione — clicca **Confirm**
5. **Copia immediatamente il Refresh Token** mostrato nella pagina
   - Il refresh token inizia con `Atzr|...`
   - Viene mostrato **una sola volta**!

### Account US+CA:

1. Login su **Seller Central NA** (https://sellercentral.amazon.com)
2. Ripeti la stessa procedura
3. Copia il secondo Refresh Token

> **Risultato**: ora hai 2 refresh token — uno per EU+UK, uno per US+CA.

## Step 5: Configurare le Credenziali

### Per sviluppo locale (file .env):

Copia il file `.env.example` in `.env` e compila i campi SP-API:

```bash
cp .env.example .env
```

Modifica `.env` aggiungendo le credenziali in formato JSON:

```env
SP_API_CREDENTIALS_EU_UK={"refresh_token": "Atzr|xxx...", "lwa_app_id": "amzn1.application-oa2-client.xxx", "lwa_client_secret": "amzn1.oa2-cs.v1.xxx", "aws_access_key": "AKIA...", "aws_secret_key": "xxx...", "role_arn": "arn:aws:iam::123456789:role/sp-api-role"}

SP_API_CREDENTIALS_NA={"refresh_token": "Atzr|yyy...", "lwa_app_id": "amzn1.application-oa2-client.xxx", "lwa_client_secret": "amzn1.oa2-cs.v1.xxx", "aws_access_key": "AKIA...", "aws_secret_key": "xxx...", "role_arn": "arn:aws:iam::123456789:role/sp-api-role"}
```

> **Nota**: `lwa_app_id`, `lwa_client_secret`, `aws_access_key`, `aws_secret_key` e `role_arn` sono gli stessi per entrambi gli account. Solo il `refresh_token` è diverso.

### Per produzione (Google Secret Manager):

```bash
# Crea i secret
echo '{"refresh_token": "Atzr|xxx...", ...}' | \
  gcloud secrets create sp-api-credentials-eu-uk --data-file=-

echo '{"refresh_token": "Atzr|yyy...", ...}' | \
  gcloud secrets create sp-api-credentials-na --data-file=-

# Concedi accesso al service account di Cloud Run
gcloud secrets add-iam-policy-binding sp-api-credentials-eu-uk \
  --member="serviceAccount:amazon-kpi-runner@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding sp-api-credentials-na \
  --member="serviceAccount:amazon-kpi-runner@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## Step 6: Installare le Dipendenze

```bash
pip install -e .
```

Questo installerà automaticamente `python-amazon-sp-api` e tutte le dipendenze necessarie.

## Step 7: Test della Connessione

### Test credenziali:

```bash
amazon-kpi test
```

Verifica che la sezione `sp_api_credentials` mostri `"status": "pass"`.

### Primo fetch di dati:

```bash
# Fetch Sales & Traffic per il marketplace US, ultima settimana
amazon-kpi sp-api --report-type sales_traffic --marketplace US

# Fetch tutti i report per tutti i marketplace
amazon-kpi sp-api --report-type all

# Specificare date custom
amazon-kpi sp-api --report-type search_query --date-range 2024-02-01 2024-02-07

# Export in Excel
amazon-kpi sp-api --report-type all --output excel
```

I file vengono salvati nella cartella `output/`.

---

## Troubleshooting

### "Access Denied" o errori 403
- Verifica che l'app sia stata autorizzata (Step 4)
- Controlla che le credenziali IAM siano corrette
- Assicurati che il refresh token non sia scaduto

### "No data returned"
- Data Kiosk può impiegare fino a 30 minuti per processare una query
- Verifica che il range date contenga dati di vendita
- Per SQP e Brand Analytics, verifica di avere accesso a Brand Registry

### Rate Limiting (errore 429)
- Il sistema gestisce automaticamente i rate limit con retry
- Data Kiosk processa una query alla volta — le richieste vengono serializzate

### Refresh Token non funziona
- I refresh token non scadono normalmente
- Se hai ri-autorizzato l'app, il vecchio token viene invalidato
- Ripeti lo Step 4 per ottenere un nuovo token

---

## Report Disponibili

| Report | Dati | Richiede Brand Registry |
|--------|------|------------------------|
| `sales_traffic` | Vendite, unità, ordini, page views, sessions, buy box % per ASIN | No |
| `search_query` | Keyword, impressions, clicks, CTR, cart adds, purchases per ASIN | Si |
| `market_basket` | Prodotti acquistati insieme, % combinazione | Si |
| `repeat_purchase` | Ordini totali vs ripetuti, tasso di riacquisto per ASIN | Si |

---

## Link Utili

- [AWS SP-API Documentation](https://developer-docs.amazon.com/sp-api/)
- [Data Kiosk API Reference](https://developer-docs.amazon.com/sp-api/docs/data-kiosk-api-v2023-11-15-reference)
- [SP-API Python Library](https://github.com/saleweaver/python-amazon-sp-api)
- [Seller Central Developer Apps](https://sellercentral.amazon.com/apps/develop/ref=xx_myapps_dnav_xx)
