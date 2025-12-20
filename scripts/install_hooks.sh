#!/bin/bash
set -e

HOOK_PATH=".git/hooks/pre-push"

echo "🛡️ Instalando Git Pre-Push Hook..."

cat > "$HOOK_PATH" << 'EOF'
#!/bin/bash
echo "🛡️  Running Zero Defect Pre-Push Checks..."

# 1. Run Sanity Check
echo "🔍 Executing sanity_check.py..."
if [ -d ".venv" ]; then
    source .venv/bin/activate
    python3 scripts/sanity_check.py
    RESULT=$?
    deactivate
else
    python3 scripts/sanity_check.py
    RESULT=$?
fi

if [ $RESULT -ne 0 ]; then
    echo "❌ Sanity Check FAILED. Push aborted."
    echo "   Fix the errors above to proceed."
    exit 1
fi

echo "✅ All checks passed. Pushing to remote..."
exit 0
EOF

chmod +x "$HOOK_PATH"
echo "✅ Hook instalado com sucesso em $HOOK_PATH"
