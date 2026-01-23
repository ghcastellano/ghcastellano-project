import os
import boto3
from botocore.exceptions import ClientError
from flask import current_app
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

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
        
        return self.send_email(to_email, subject, html_body, text_body)

    def send_email(self, to_email, subject, html_body, text_body):
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
                msg = e.response['Error']['Message']
                if "not verified" in msg:
                    logger.warning(f"SES Sandbox Warning: {msg}. FALLING BACK TO MOCK.")
                    # Fallback to Mock
                    print(f" [MOCK EMAIL FALLBACK] (SES Sandbox Blocked Real Send)")
                    return self._send_mock_email(to_email, subject, text_body)
                else:
                    logger.error(f"SES Error: {msg}")
                return False
        else:
            return self._send_mock_email(to_email, subject, text_body)

    def _send_mock_email(self, to_email, subject, text_body):
        # Mock Provider
        print("="*60)
        print(f" [MOCK EMAIL] To: {to_email}")
        print(f" Subject: {subject}")
        print("-" * 20)
        print(text_body)
        print("="*60)
        logger.info(f"Mock email sent to {to_email}")
        return True

    def send_email_with_attachment(self, to_email, subject, body, attachment_path):
        if self.provider == 'ses' and self.ses_client:
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = self.sender
            msg['To'] = to_email

            # Add body
            msg.attach(MIMEText(body, 'plain'))

            # Add attachment
            try:
                with open(attachment_path, 'rb') as f:
                    part = MIMEApplication(f.read())
                    part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                    msg.attach(part)
            except Exception as e:
                logger.error(f"Failed to read attachment {attachment_path}: {e}")
                return False

            try:
                response = self.ses_client.send_raw_email(
                    Source=self.sender,
                    Destinations=[to_email],
                    RawMessage={'Data': msg.as_string()}
                )
                logger.info(f"Email (Raw) sent to {to_email} via SES. MsgId: {response['MessageId']}")
                return True
            except ClientError as e:
                error_msg = e.response['Error']['Message']
                if "not verified" in error_msg:
                    logger.warning(f"SES Sandbox Warning (Raw): {error_msg}. FALLING BACK TO MOCK.")
                    return self._send_mock_email_attachment(to_email, subject, body, attachment_path)
                else:
                    logger.error(f"SES Raw Error: {error_msg}")
                return False
        else:
            return self._send_mock_email_attachment(to_email, subject, body, attachment_path)

    def _send_mock_email_attachment(self, to_email, subject, body, attachment_path):
        print("="*60)
        print(f" [MOCK EMAIL WITH ATTACHMENT] To: {to_email}")
        print(f" Subject: {subject}")
        print(f" Attachment: {attachment_path}")
        print("-" * 20)
        print(body)
        print("="*60)
        logger.info(f"Mock email with attachment sent to {to_email}")
        return True
