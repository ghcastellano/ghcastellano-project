import os
import smtplib
import logging
from src.config_helper import get_config
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        logger.info("EmailService initialized (lazy config)")

    def _get_smtp_config(self):
        """Read SMTP config fresh from DB/env each time (no restart needed)."""
        email = get_config('SMTP_EMAIL')
        password = get_config('SMTP_PASSWORD')
        host = get_config('SMTP_HOST', 'smtp.gmail.com')
        port = int(get_config('SMTP_PORT', '587'))
        return email, password, host, port

    def _is_smtp_configured(self):
        email, password, _, _ = self._get_smtp_config()
        return bool(email and password)

    def send_welcome_email(self, to_email, name, temp_password):
        subject = "Bem-vindo ao InspetorAI - Suas Credenciais"

        html_body = f"""
        <html>
        <head></head>
        <body style="font-family: sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                <h2 style="color: #2563eb;">Bem-vindo ao InspetorAI!</h2>
                <p>Olá, <strong>{name}</strong>.</p>
                <p>Sua conta foi criada com sucesso.</p>
                <div style="background: #f3f4f6; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0; font-size: 0.9rem; color: #666;">Sua senha temporária:</p>
                    <p style="margin: 5px 0 0 0; font-size: 1.5rem; font-weight: bold; letter-spacing: 2px;">{temp_password}</p>
                </div>
                <p>Por motivos de segurança, você será obrigado a alterar esta senha no primeiro acesso.</p>
                <p><a href="{get_config('BASE_URL', 'http://localhost:5000')}/auth/login" style="background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Acessar Dashboard</a></p>
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

        Acesse em: {get_config('BASE_URL', 'http://localhost:5000')}/auth/login
        """

        return self.send_email(to_email, subject, html_body, text_body)

    def send_email(self, to_email, subject, html_body, text_body):
        if self._is_smtp_configured():
            smtp_email, smtp_password, smtp_host, smtp_port = self._get_smtp_config()
            try:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = smtp_email
                msg['To'] = to_email

                msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
                msg.attach(MIMEText(html_body, 'html', 'utf-8'))

                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_email, smtp_password)
                    server.sendmail(smtp_email, to_email, msg.as_string())

                logger.info(f"Email sent to {to_email} via SMTP ({smtp_host})")
                return True
            except Exception as e:
                logger.error(f"SMTP Error sending to {to_email}: {e}")
                return False
        else:
            return self._send_mock_email(to_email, subject, text_body)

    def _send_mock_email(self, to_email, subject, text_body):
        print("="*60)
        print(f" [MOCK EMAIL] To: {to_email}")
        print(f" Subject: {subject}")
        print("-" * 20)
        print(text_body)
        print("="*60)
        logger.info(f"Mock email sent to {to_email}")
        return True

    def send_email_with_attachment(self, to_email, subject, body, attachment_path):
        if self._is_smtp_configured():
            smtp_email, smtp_password, smtp_host, smtp_port = self._get_smtp_config()
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = smtp_email
            msg['To'] = to_email

            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            try:
                with open(attachment_path, 'rb') as f:
                    part = MIMEApplication(f.read())
                    part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                    msg.attach(part)
            except Exception as e:
                logger.error(f"Failed to read attachment {attachment_path}: {e}")
                return False

            try:
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_email, smtp_password)
                    server.sendmail(smtp_email, to_email, msg.as_string())

                logger.info(f"Email with attachment sent to {to_email} via SMTP")
                return True
            except Exception as e:
                logger.error(f"SMTP Error sending attachment email to {to_email}: {e}")
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
