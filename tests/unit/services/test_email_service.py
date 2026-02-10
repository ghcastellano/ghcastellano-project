"""Tests for EmailService."""
import os
from unittest.mock import patch, MagicMock, mock_open

import pytest

from src.services.email_service import EmailService


class TestSmtpConfig:
    """Tests for SMTP configuration."""

    @patch('src.services.email_service.get_config')
    def test_get_smtp_config_returns_all_fields(self, mock_config):
        """Should return email, password, host, port tuple."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': 'test@gmail.com',
            'SMTP_PASSWORD': 'secret123',
            'SMTP_HOST': 'smtp.custom.com',
            'SMTP_PORT': '465',
        }.get(key, default)

        svc = EmailService()
        email, password, host, port = svc._get_smtp_config()

        assert email == 'test@gmail.com'
        assert password == 'secret123'
        assert host == 'smtp.custom.com'
        assert port == 465

    @patch('src.services.email_service.get_config')
    def test_get_smtp_config_defaults(self, mock_config):
        """Should use default host and port when not configured."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': 'user@test.com',
            'SMTP_PASSWORD': 'pass',
        }.get(key, default)

        svc = EmailService()
        email, password, host, port = svc._get_smtp_config()

        assert host == 'smtp.gmail.com'
        assert port == 587

    @patch('src.services.email_service.get_config')
    def test_is_smtp_configured_true(self, mock_config):
        """Should return True when email and password are set."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': 'user@test.com',
            'SMTP_PASSWORD': 'pass',
            'SMTP_HOST': 'smtp.gmail.com',
            'SMTP_PORT': '587',
        }.get(key, default)

        svc = EmailService()
        assert svc._is_smtp_configured() is True

    @patch('src.services.email_service.get_config')
    def test_is_smtp_configured_false_no_email(self, mock_config):
        """Should return False when email is missing."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': None,
            'SMTP_PASSWORD': 'pass',
            'SMTP_HOST': 'smtp.gmail.com',
            'SMTP_PORT': '587',
        }.get(key, default)

        svc = EmailService()
        assert svc._is_smtp_configured() is False

    @patch('src.services.email_service.get_config')
    def test_is_smtp_configured_false_no_password(self, mock_config):
        """Should return False when password is missing."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': 'user@test.com',
            'SMTP_PASSWORD': None,
            'SMTP_HOST': 'smtp.gmail.com',
            'SMTP_PORT': '587',
        }.get(key, default)

        svc = EmailService()
        assert svc._is_smtp_configured() is False


class TestSendEmail:
    """Tests for send_email method."""

    @patch('src.services.email_service.get_config')
    @patch('src.services.email_service.smtplib.SMTP')
    def test_send_email_via_smtp(self, mock_smtp_cls, mock_config):
        """Should send email via SMTP when configured."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': 'sender@test.com',
            'SMTP_PASSWORD': 'pass123',
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
        }.get(key, default)

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        svc = EmailService()
        result = svc.send_email(
            'recipient@test.com',
            'Test Subject',
            '<h1>HTML</h1>',
            'Text body'
        )

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('sender@test.com', 'pass123')
        mock_server.sendmail.assert_called_once()

    @patch('src.services.email_service.get_config')
    @patch('src.services.email_service.smtplib.SMTP')
    def test_send_email_smtp_error_returns_false(self, mock_smtp_cls, mock_config):
        """Should return False on SMTP error."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': 'sender@test.com',
            'SMTP_PASSWORD': 'pass123',
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
        }.get(key, default)

        mock_smtp_cls.side_effect = Exception("Connection refused")

        svc = EmailService()
        result = svc.send_email(
            'recipient@test.com',
            'Test Subject',
            '<h1>HTML</h1>',
            'Text body'
        )

        assert result is False

    @patch('src.services.email_service.get_config')
    def test_send_email_falls_back_to_mock(self, mock_config):
        """Should use mock email when SMTP not configured."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': None,
            'SMTP_PASSWORD': None,
            'SMTP_HOST': 'smtp.gmail.com',
            'SMTP_PORT': '587',
        }.get(key, default)

        svc = EmailService()
        result = svc.send_email(
            'recipient@test.com',
            'Test Subject',
            '<h1>HTML</h1>',
            'Text body'
        )

        assert result is True  # Mock always returns True


class TestSendWelcomeEmail:
    """Tests for send_welcome_email."""

    @patch('src.services.email_service.get_config')
    def test_send_welcome_email_calls_send_email(self, mock_config):
        """Should compose and send welcome email."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': None,
            'SMTP_PASSWORD': None,
            'SMTP_HOST': 'smtp.gmail.com',
            'SMTP_PORT': '587',
            'BASE_URL': 'http://localhost:5000',
        }.get(key, default)

        svc = EmailService()
        with patch.object(svc, 'send_email', return_value=True) as mock_send:
            result = svc.send_welcome_email('new@user.com', 'João', 'temp123')

            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0]
            assert call_args[0] == 'new@user.com'
            assert 'Bem-vindo' in call_args[1]
            assert 'temp123' in call_args[2]  # HTML body
            assert 'temp123' in call_args[3]  # Text body

    @patch('src.services.email_service.get_config')
    def test_welcome_email_contains_user_name(self, mock_config):
        """Should include user name in email body."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': None,
            'SMTP_PASSWORD': None,
            'SMTP_HOST': 'smtp.gmail.com',
            'SMTP_PORT': '587',
            'BASE_URL': 'http://localhost:5000',
        }.get(key, default)

        svc = EmailService()
        with patch.object(svc, 'send_email', return_value=True) as mock_send:
            svc.send_welcome_email('new@user.com', 'Maria Silva', 'pass456')

            call_args = mock_send.call_args[0]
            assert 'Maria Silva' in call_args[2]  # HTML body


class TestSendEmailWithAttachment:
    """Tests for send_email_with_attachment."""

    @patch('src.services.email_service.get_config')
    @patch('src.services.email_service.smtplib.SMTP')
    def test_send_with_attachment_via_smtp(self, mock_smtp_cls, mock_config):
        """Should attach file and send via SMTP."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': 'sender@test.com',
            'SMTP_PASSWORD': 'pass123',
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
        }.get(key, default)

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        svc = EmailService()
        with patch('builtins.open', mock_open(read_data=b'fake-pdf-content')):
            result = svc.send_email_with_attachment(
                'recipient@test.com',
                'Report',
                'Please find attached.',
                '/tmp/report.pdf'
            )

        assert result is True
        mock_server.sendmail.assert_called_once()

    @patch('src.services.email_service.get_config')
    @patch('src.services.email_service.smtplib.SMTP')
    def test_attachment_read_error_returns_false(self, mock_smtp_cls, mock_config):
        """Should return False when attachment can't be read."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': 'sender@test.com',
            'SMTP_PASSWORD': 'pass123',
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
        }.get(key, default)

        svc = EmailService()
        with patch('builtins.open', side_effect=FileNotFoundError("No such file")):
            result = svc.send_email_with_attachment(
                'recipient@test.com',
                'Report',
                'Body',
                '/tmp/nonexistent.pdf'
            )

        assert result is False

    @patch('src.services.email_service.get_config')
    @patch('src.services.email_service.smtplib.SMTP')
    def test_smtp_send_error_returns_false(self, mock_smtp_cls, mock_config):
        """Should return False on SMTP error during send."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': 'sender@test.com',
            'SMTP_PASSWORD': 'pass123',
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
        }.get(key, default)

        mock_server = MagicMock()
        mock_server.sendmail.side_effect = Exception("SMTP error")
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        svc = EmailService()
        with patch('builtins.open', mock_open(read_data=b'content')):
            result = svc.send_email_with_attachment(
                'recipient@test.com',
                'Report',
                'Body',
                '/tmp/report.pdf'
            )

        assert result is False

    @patch('src.services.email_service.get_config')
    def test_fallback_to_mock_attachment(self, mock_config):
        """Should use mock when SMTP not configured."""
        mock_config.side_effect = lambda key, default=None: {
            'SMTP_EMAIL': None,
            'SMTP_PASSWORD': None,
            'SMTP_HOST': 'smtp.gmail.com',
            'SMTP_PORT': '587',
        }.get(key, default)

        svc = EmailService()
        result = svc.send_email_with_attachment(
            'recipient@test.com',
            'Report',
            'Body',
            '/tmp/report.pdf'
        )

        assert result is True  # Mock always returns True


class TestMockEmails:
    """Tests for mock email methods."""

    def test_mock_email_returns_true(self):
        """Mock email should always return True."""
        svc = EmailService()
        result = svc._send_mock_email('test@test.com', 'Subject', 'Body')
        assert result is True

    def test_mock_email_attachment_returns_true(self):
        """Mock email with attachment should always return True."""
        svc = EmailService()
        result = svc._send_mock_email_attachment(
            'test@test.com', 'Subject', 'Body', '/tmp/file.pdf'
        )
        assert result is True
