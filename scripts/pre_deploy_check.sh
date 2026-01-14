#!/bin/bash
echo "🚀 Iniciando bateria de testes completa..."

echo "---------------------------------------------------"
echo "STAGE 1: Análise Estática (Code & Templates)"
echo "---------------------------------------------------"
python3 scripts/audit_codebase.py
if [ $? -ne 0 ]; then
    echo "❌ Falha na auditoria estática."
    exit 1
fi

echo "---------------------------------------------------"
echo "STAGE 2: Smoke Test (Visual/Runtime)"
echo "---------------------------------------------------"
python3 scripts/smoke_test_local.py
if [ $? -ne 0 ]; then
    echo "❌ Falha no smoke test. O servidor não iniciou ou retornou erros."
    exit 1
fi

echo "---------------------------------------------------"
echo "✅ TUDO OK! O app está seguro para uso/deploy."
echo "---------------------------------------------------"
exit 0
