#!/bin/bash
# WhatsApp Business API - Registrar número +55 13 98850-7947
# Phone Number ID: 1011177555406814
# WABA ID: 865543462793036
#
# BLOQUEIO ATUAL: account_review_status da WABA está PENDING
# Executar SOMENTE após o account_review_status mudar para APPROVED
# Acompanhe em: https://business.facebook.com/wa/manage/phone-numbers/

TOKEN="EAA67CEZAiq6sBQv6J4bRVxeJZAzn2quPXEwM74cRvjSlQED03fuJWki0CT8T3ISN4n8IwMvXvuftb9wtZBENdQqDvGyNy9apXYctRP6eCfx7yZBaRdRVGrLd76kGP9cuVee4300SZCRXSJHRKUwulM5PZAVzuZBCjg1J7tJdafpsec23AZBd5VBUZCkBPuPekot4HWrZCd7rdEvAfVN4ZAUDKTxLCKoRX6R2R2nN4naht7Yr0mevev7JvxXmOAZCm3hRRgKEZBuMfZCM8eXltSUJWcMnttDIZAGY"
PHONE_ID="1011177555406814"
WABA_ID="865543462793036"

echo "=== Verificando status da conta WABA ==="
python3 -c "
import urllib.request, json
token = '${TOKEN}'
url = f'https://graph.facebook.com/v21.0/${WABA_ID}?fields=name,account_review_status,business_verification_status'
req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())
    print(json.dumps(data, indent=2))
    if data.get('account_review_status') != 'APPROVED':
        print()
        print('⚠️  WABA account_review_status NÃO está APPROVED. Registro bloqueado.')
        print('Acompanhe em: https://business.facebook.com/wa/manage/phone-numbers/')
        exit(1)
"

if [ $? -ne 0 ]; then
    echo ""
    echo "Abortando registro - WABA ainda não aprovada."
    exit 1
fi

echo ""
echo "=== Verificando status do número ==="
python3 -c "
import urllib.request, json
token = '${TOKEN}'
url = f'https://graph.facebook.com/v21.0/${PHONE_ID}?fields=display_phone_number,name_status,status,code_verification_status,quality_rating'
req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())
    print(json.dumps(data, indent=2))
"

echo ""
echo "=== Registrando número ==="
python3 -c "
import urllib.request, json
token = '${TOKEN}'
url = f'https://graph.facebook.com/v21.0/${PHONE_ID}/register'
payload = json.dumps({'messaging_product': 'whatsapp', 'pin': '123456'}).encode()
req = urllib.request.Request(url, data=payload, headers={
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())
    print(json.dumps(data, indent=2))
"
