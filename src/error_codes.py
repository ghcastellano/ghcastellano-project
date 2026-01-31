"""
Sistema de Códigos de Erro Estruturados
Fornece mensagens padronizadas para usuários e administradores
"""

class ErrorCode:
    """Catálogo de códigos de erro com mensagens para usuário final e administrador"""

    # Upload & Validação (1xxx)
    ERR_1001 = {
        "code": "ERR_1001",
        "admin_msg": "PDF corrompido ou ilegível",
        "user_msg": "O arquivo PDF está corrompido. Por favor, gere o relatório novamente e tente fazer o upload."
    }

    ERR_1002 = {
        "code": "ERR_1002",
        "admin_msg": "PDF vazio (sem texto extraível)",
        "user_msg": "O PDF não contém texto legível. Certifique-se de que o relatório foi salvo corretamente (não como imagem)."
    }

    ERR_1003 = {
        "code": "ERR_1003",
        "admin_msg": "Arquivo muito grande (>32MB)",
        "user_msg": "O arquivo excede o limite de 32MB. Comprima o PDF ou divida em partes menores."
    }

    ERR_1004 = {
        "code": "ERR_1004",
        "admin_msg": "Formato de arquivo inválido (não é PDF)",
        "user_msg": "Apenas arquivos PDF são aceitos. Verifique a extensão do arquivo."
    }

    # OpenAI / IA (2xxx)
    ERR_2001 = {
        "code": "ERR_2001",
        "admin_msg": "OpenAI API timeout",
        "user_msg": "Tempo limite excedido na análise. O sistema está sobrecarregado. Tente novamente em alguns minutos."
    }

    ERR_2002 = {
        "code": "ERR_2002",
        "admin_msg": "OpenAI quota exceeded (limite mensal atingido)",
        "user_msg": "Limite de uso da IA atingido neste mês. Entre em contato com o suporte técnico."
    }

    ERR_2003 = {
        "code": "ERR_2003",
        "admin_msg": "Structured output validation failed (IA não retornou formato esperado)",
        "user_msg": "A IA não conseguiu processar o relatório corretamente. Verifique se o formato do relatório está padrão."
    }

    ERR_2004 = {
        "code": "ERR_2004",
        "admin_msg": "OpenAI API key inválida ou expirada",
        "user_msg": "Configuração da IA inválida. Contate o administrador do sistema urgentemente."
    }

    ERR_2005 = {
        "code": "ERR_2005",
        "admin_msg": "Resposta da IA vazia ou malformada",
        "user_msg": "A IA retornou uma resposta incompleta. Tente enviar o relatório novamente."
    }

    # Banco de Dados (3xxx)
    ERR_3001 = {
        "code": "ERR_3001",
        "admin_msg": "Falha ao salvar dados no banco (commit failed)",
        "user_msg": "Erro ao salvar os dados processados. Tente novamente. Se persistir, contate o suporte."
    }

    ERR_3002 = {
        "code": "ERR_3002",
        "admin_msg": "Estabelecimento não encontrado (match failed)",
        "user_msg": "Não foi possível identificar a loja no relatório. Verifique se o nome da loja está correto no documento."
    }

    ERR_3003 = {
        "code": "ERR_3003",
        "admin_msg": "Conexão com banco de dados perdida",
        "user_msg": "Falha na conexão com o servidor. Verifique sua internet e tente novamente."
    }

    ERR_3004 = {
        "code": "ERR_3004",
        "admin_msg": "Violação de integridade (duplicate key ou constraint)",
        "user_msg": "Este relatório parece estar duplicado no sistema. Verifique a lista de inspeções."
    }

    # Drive/Storage (4xxx)
    ERR_4001 = {
        "code": "ERR_4001",
        "admin_msg": "Drive upload failed (API error)",
        "user_msg": "Falha ao fazer upload para o Google Drive. Verifique sua conexão e tente novamente."
    }

    ERR_4002 = {
        "code": "ERR_4002",
        "admin_msg": "Drive quota exceeded (limite de armazenamento)",
        "user_msg": "Espaço de armazenamento no Google Drive está cheio. Entre em contato com o administrador."
    }

    ERR_4003 = {
        "code": "ERR_4003",
        "admin_msg": "Drive authentication failed (token expirado)",
        "user_msg": "Falha na autenticação com Google Drive. O administrador precisa reautorizar o acesso."
    }

    ERR_4004 = {
        "code": "ERR_4004",
        "admin_msg": "Storage service unavailable (GCS down)",
        "user_msg": "Serviço de armazenamento temporariamente indisponível. Tente novamente em alguns minutos."
    }

    # Sistema / Genérico (9xxx)
    ERR_9001 = {
        "code": "ERR_9001",
        "admin_msg": "Erro não categorizado (exceção genérica)",
        "user_msg": "Ocorreu um erro inesperado. Anote o código deste erro e entre em contato com o suporte."
    }

    ERR_9002 = {
        "code": "ERR_9002",
        "admin_msg": "Timeout geral (operação demorou mais de 2 minutos)",
        "user_msg": "A operação demorou muito tempo. Tente processar um arquivo menor ou contate o suporte."
    }

    @staticmethod
    def get_error(exception_or_code):
        """
        Retorna objeto de erro baseado na exceção ou código.

        Args:
            exception_or_code: Exception object ou string com código (ex: "ERR_1001")

        Returns:
            dict com code, admin_msg, user_msg
        """
        if isinstance(exception_or_code, str):
            # Código direto
            return getattr(ErrorCode, exception_or_code, ErrorCode.ERR_9001)

        # Análise da exceção
        error_str = str(exception_or_code).lower()

        # PDF/Upload
        if "empty" in error_str or "no text" in error_str:
            return ErrorCode.ERR_1002
        if "corrupt" in error_str or "invalid pdf" in error_str:
            return ErrorCode.ERR_1001
        if "file size" in error_str or "too large" in error_str:
            return ErrorCode.ERR_1003

        # OpenAI
        if "timeout" in error_str and "openai" in error_str:
            return ErrorCode.ERR_2001
        if "quota" in error_str or "rate limit" in error_str:
            return ErrorCode.ERR_2002
        if "api key" in error_str or "authentication" in error_str:
            return ErrorCode.ERR_2004
        if "validation" in error_str or "parsing" in error_str:
            return ErrorCode.ERR_2003

        # Database
        if "database" in error_str or "connection" in error_str:
            return ErrorCode.ERR_3003
        if "duplicate" in error_str or "unique constraint" in error_str:
            return ErrorCode.ERR_3004
        if "establishment" in error_str and "not found" in error_str:
            return ErrorCode.ERR_3002

        # Drive/Storage
        if "drive" in error_str and "quota" in error_str:
            return ErrorCode.ERR_4002
        if "drive" in error_str or "upload" in error_str:
            return ErrorCode.ERR_4001
        if "storage" in error_str:
            return ErrorCode.ERR_4004

        # Default
        return ErrorCode.ERR_9001
