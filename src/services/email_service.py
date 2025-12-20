import os
import boto3
from botocore.exceptions import ClientError
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, provider='mock'):
        self.provider = provider
        self.ses_client = None
        self.sender = os.getenv('AWS_SES_SENDER', 'noreply@inspetorai.com')
        
        if provider == 'ses':
            try:
                self.ses_client = boto3.client(
                    'ses',
                    region_name=os.getenv('AWS_REGION', 'us-east-1'),
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
                )
                logger.info("AWS SES Client initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize AWS SES: {e}. Falling back to Mock.")
                self.provider = 'mock'

    def send_welcome_email(self, to_email, name, temp_password):
        subject = "Bem-vindo ao InspetorAI - Suas Credenciais"
        
        # HTML Body
        html_body = f"""
        <html>
        <head></head>
        <body style="font-family: sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                <h2 style="color: #2563eb;">Bem-vindo ao InspetorAI!</h2>
                <p>Olá, <strong>{name}</strong>.</p>
                <p>Sua conta de Gestor foi criada com sucesso.</p>
                <div style="background: #f3f4f6; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0; font-size: 0.9rem; color: #666;">Sua senha temporária:</p>
                    <p style="margin: 5px 0 0 0; font-size: 1.5rem; font-weight: bold; letter-spacing: 2px;">{temp_password}</p>
                </div>
                <p>Por motivos de segurança, você será obrigado a alterar esta senha no primeiro acesso.</p>
                <p><a href="{os.getenv('BASE_URL', 'http://localhost:5000')}/auth/login" style="background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Acessar Dashboard</a></p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 0.8rem; color: #999;">Se você não solicitou este acesso, ignore este e-mail.</p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        Bem-vindo ao InspetorAI!
        Olá {name}, sua conta foi criada.
        
        Sua senha temporária: {temp_password}
        
        Acesse em: {os.getenv('BASE_URL', 'http://localhost:5000')}/auth/login
        """
        
        return self._send_email(to_email, subject, html_body, text_body)

    def _send_email(self, to_email, subject, html_body, text_body):
        if self.provider == 'ses' and self.ses_client:
            try:
                response = self.ses_client.send_email(
                    Source=self.sender,
                    Destination={'ToAddresses': [to_email]},
                    Message={
                        'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                        'Body': {
                            'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                            'Text': {'Data': text_body, 'Charset': 'UTF-8'}
                        }
                    }
                )
                logger.info(f"Email sent to {to_email} via SES. MsgId: {response['MessageId']}")
                return True
            except ClientError as e:
                logger.error(f"SES Error: {e.response['Error']['Message']}")
                return False
        else:
            # Mock Provider
            print("="*60)
            print(f" [MOCK EMAIL] To: {to_email}")
            print(f" Subject: {subject}")
            print("-" * 20)
            print(text_body)
            print("="*60)
            logger.info(f"Mock email sent to {to_email}")
            return True
