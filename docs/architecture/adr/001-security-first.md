# ADR 001: Security First Approach

## Status
Accepted

## Context
O sistema MVP de Inspeção Sanitária tinha vulnerabilidades de segurança que precisavam ser corrigidas antes de continuar com a refatoração de arquitetura.

## Decision
Implementar melhorias de segurança como primeira fase da refatoração:

1. **Validação de arquivos com magic bytes**
   - Não confiar apenas na extensão do arquivo
   - Validar estrutura interna de PDFs
   - Limitar tamanho de uploads

2. **Rate limiting**
   - Proteger endpoints sensíveis contra brute force
   - Limitar uploads para evitar abuso

3. **Desabilitar debug em produção**
   - Endpoints `/debug/*` retornam 404 em Cloud Run

4. **Sanitizar logs**
   - Nunca logar API keys ou credenciais

## Consequences

### Positivas
- Redução de vulnerabilidades críticas
- Proteção contra ataques de força bruta
- Validação robusta de uploads
- Base segura para refatoração futura

### Negativas
- Pequeno overhead em validação de arquivos
- Rate limiting pode afetar usuários legítimos (limites generosos)

## Compliance
- OWASP Top 10: File Upload, Broken Access Control
- LGPD: Proteção de dados sensíveis em logs
