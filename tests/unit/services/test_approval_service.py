"""Tests for ApprovalService."""
import json
import os
import threading
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from src.services.approval_service import ApprovalService


class TestProcessApprovalOrShare:
    """Tests for process_approval_or_share orchestration."""

    def test_starts_background_thread(self):
        """Should start a background thread for async processing."""
        svc = ApprovalService()
        data = {
            'resp_name': 'João',
            'resp_phone': '11999998888',
            'via': 'whatsapp',
        }
        with patch.object(svc, '_update_contact_info') as mock_update, \
             patch.object(svc, '_async_generate_and_send') as mock_async, \
             patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            result = svc.process_approval_or_share('file-123', data, is_approval=False)

            assert result is True
            mock_update.assert_called_once_with('file-123', 'João', '11999998888', None, None)
            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()

    def test_passes_email_to_update_contact(self):
        """Should pass email field from data."""
        svc = ApprovalService()
        data = {
            'resp_name': 'Maria',
            'resp_phone': '',
            'email': 'maria@test.com',
            'via': 'email',
        }
        with patch.object(svc, '_update_contact_info') as mock_update, \
             patch.object(svc, '_async_generate_and_send'), \
             patch('threading.Thread') as mock_thread:
            mock_thread.return_value = MagicMock()

            svc.process_approval_or_share('file-456', data, is_approval=True)

            mock_update.assert_called_once_with(
                'file-456', 'Maria', '', 'maria@test.com', None
            )

    def test_passes_contact_id(self):
        """Should pass contact_id from data."""
        svc = ApprovalService()
        data = {
            'resp_name': 'Ana',
            'resp_phone': '21888887777',
            'contact_id': 'contact-uuid-123',
            'via': 'whatsapp',
        }
        with patch.object(svc, '_update_contact_info') as mock_update, \
             patch.object(svc, '_async_generate_and_send'), \
             patch('threading.Thread') as mock_thread:
            mock_thread.return_value = MagicMock()

            svc.process_approval_or_share('file-789', data)

            mock_update.assert_called_once_with(
                'file-789', 'Ana', '21888887777', None, 'contact-uuid-123'
            )

    def test_thread_args_include_via(self):
        """Should pass 'via' to the background thread."""
        svc = ApprovalService()
        data = {
            'resp_name': 'Test',
            'resp_phone': '123',
            'via': 'email',
        }
        with patch.object(svc, '_update_contact_info'), \
             patch('threading.Thread') as mock_thread:
            mock_thread.return_value = MagicMock()

            svc.process_approval_or_share('f1', data, is_approval=True)

            call_args = mock_thread.call_args
            assert call_args[1]['args'] == ('f1', 'Test', '123', None, True, 'email')

    def test_default_via_is_whatsapp(self):
        """Should default to whatsapp when 'via' not specified."""
        svc = ApprovalService()
        data = {'resp_name': 'Test', 'resp_phone': '123'}
        with patch.object(svc, '_update_contact_info'), \
             patch('threading.Thread') as mock_thread:
            mock_thread.return_value = MagicMock()

            svc.process_approval_or_share('f1', data)

            call_args = mock_thread.call_args
            assert call_args[1]['args'][-1] == 'whatsapp'


class TestUpdateContactInfo:
    """Tests for _update_contact_info."""

    def _make_mocks(self):
        mock_db = MagicMock()
        mock_est = MagicMock()
        mock_est.id = 'est-uuid'
        return mock_db, mock_est

    @patch('src.services.approval_service.get_db')
    @patch('src.services.approval_service.drive_service')
    def test_creates_new_contact_when_no_contact_id(self, mock_drive, mock_get_db):
        """Should create new Contact if no contact_id provided."""
        mock_db, mock_est = self._make_mocks()
        mock_get_db.return_value = iter([mock_db])
        mock_drive.read_json.return_value = {'estabelecimento': 'Loja A'}
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_est

        svc = ApprovalService()
        svc._update_contact_info('file-1', 'João', '11999', 'j@t.com', None)

        mock_db.add.assert_called_once()
        new_contact = mock_db.add.call_args[0][0]
        assert new_contact.name == 'João'
        assert new_contact.phone == '11999'
        assert new_contact.email == 'j@t.com'
        mock_db.commit.assert_called_once()

    @patch('src.services.approval_service.get_db')
    @patch('src.services.approval_service.drive_service')
    def test_updates_existing_contact_when_contact_id(self, mock_drive, mock_get_db):
        """Should update existing Contact if contact_id provided."""
        mock_db, mock_est = self._make_mocks()
        mock_get_db.return_value = iter([mock_db])
        mock_drive.read_json.return_value = {'estabelecimento': 'Loja B'}
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_est

        existing_contact = MagicMock()
        mock_db.query.return_value.get.return_value = existing_contact

        svc = ApprovalService()
        svc._update_contact_info('file-2', 'Maria', '22888', 'm@t.com', 'contact-123')

        assert existing_contact.name == 'Maria'
        assert existing_contact.phone == '22888'
        assert existing_contact.email == 'm@t.com'
        mock_db.add.assert_not_called()
        mock_db.commit.assert_called_once()

    @patch('src.services.approval_service.get_db')
    @patch('src.services.approval_service.drive_service')
    def test_updates_establishment_responsible(self, mock_drive, mock_get_db):
        """Should update establishment's responsible_name and phone."""
        mock_db, mock_est = self._make_mocks()
        mock_get_db.return_value = iter([mock_db])
        mock_drive.read_json.return_value = {'estabelecimento': 'Loja C'}
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_est

        svc = ApprovalService()
        svc._update_contact_info('file-3', 'Ana', '33777', None, None)

        assert mock_est.responsible_name == 'Ana'
        assert mock_est.responsible_phone == '33777'

    @patch('src.services.approval_service.get_db')
    @patch('src.services.approval_service.drive_service')
    def test_no_establishment_found_still_commits(self, mock_drive, mock_get_db):
        """Should handle missing establishment gracefully."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_drive.read_json.return_value = {'estabelecimento': 'Nonexistent'}
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        svc = ApprovalService()
        # No establishment found - should not error
        svc._update_contact_info('file-4', 'Test', '123', None, None)
        # Should still close the session
        mock_db.close.assert_called_once()

    @patch('src.services.approval_service.get_db')
    @patch('src.services.approval_service.drive_service')
    def test_no_est_name_in_json(self, mock_drive, mock_get_db):
        """Should handle missing 'estabelecimento' key in JSON."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_drive.read_json.return_value = {}  # no 'estabelecimento'

        svc = ApprovalService()
        svc._update_contact_info('file-5', 'Test', '123', None, None)
        mock_db.close.assert_called_once()

    @patch('src.services.approval_service.get_db')
    @patch('src.services.approval_service.drive_service')
    def test_error_is_reraised(self, mock_drive, mock_get_db):
        """Should re-raise exceptions after logging."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_drive.read_json.side_effect = Exception("Drive error")

        svc = ApprovalService()
        with pytest.raises(Exception, match="Drive error"):
            svc._update_contact_info('file-6', 'Test', '123', None, None)
        mock_db.close.assert_called_once()


class TestAsyncGenerateAndSend:
    """Tests for _async_generate_and_send."""

    @patch('src.services.approval_service.os.path.exists', return_value=True)
    @patch('src.services.approval_service.os.remove')
    @patch('src.services.approval_service.drive_service')
    @patch('src.services.approval_service.pdf_service')
    def test_whatsapp_path_sends_document(self, mock_pdf, mock_drive, mock_remove, mock_exists):
        """Should send via WhatsApp when via='whatsapp'."""
        mock_drive.read_json.return_value = {
            'estabelecimento': 'Loja X',
            'data_inspecao': '01/01/2024',
        }
        mock_pdf.generate_pdf_bytes.return_value = b'%PDF-fake'

        svc = ApprovalService()

        with patch('src.services.approval_service.get_db') as mock_get_db, \
             patch('builtins.open', MagicMock()), \
             patch('src.services.approval_service.WhatsAppService') as mock_wa_cls:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            mock_wa = MagicMock()
            mock_wa_cls.return_value = mock_wa

            svc._async_generate_and_send('file-1', 'João', '11999', None, False, 'whatsapp')

            mock_wa.send_document.assert_called_once()
            call_args = mock_wa.send_document.call_args[0]
            assert '11999' in call_args

    @patch('src.services.approval_service.os.path.exists', return_value=True)
    @patch('src.services.approval_service.os.remove')
    @patch('src.services.approval_service.drive_service')
    @patch('src.services.approval_service.pdf_service')
    def test_email_path_sends_email(self, mock_pdf, mock_drive, mock_remove, mock_exists):
        """Should send via email when via='email'."""
        mock_drive.read_json.return_value = {
            'estabelecimento': 'Loja Y',
            'data_inspecao': '15/06/2024',
        }
        mock_pdf.generate_pdf_bytes.return_value = b'%PDF-fake'

        svc = ApprovalService()

        with patch('src.services.approval_service.get_db') as mock_get_db, \
             patch('builtins.open', MagicMock()), \
             patch('src.services.email_service.EmailService') as mock_email_cls:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            mock_email = MagicMock()
            mock_email_cls.return_value = mock_email

            svc._async_generate_and_send('file-2', 'Maria', None, 'maria@test.com', False, 'email')

            mock_email.send_email_with_attachment.assert_called_once()
            call_kwargs = mock_email.send_email_with_attachment.call_args
            assert call_kwargs[1]['to_email'] == 'maria@test.com'

    @patch('src.services.approval_service.os.path.exists', return_value=True)
    @patch('src.services.approval_service.os.remove')
    @patch('src.services.approval_service.drive_service')
    @patch('src.services.approval_service.pdf_service')
    def test_whatsapp_no_phone_logs_warning(self, mock_pdf, mock_drive, mock_remove, mock_exists):
        """Should log warning when WhatsApp but no phone."""
        mock_drive.read_json.return_value = {
            'estabelecimento': 'Loja Z',
            'data_inspecao': '01/01/2024',
        }
        mock_pdf.generate_pdf_bytes.return_value = b'%PDF-fake'

        svc = ApprovalService()

        with patch('src.services.approval_service.get_db') as mock_get_db, \
             patch('builtins.open', MagicMock()), \
             patch('src.services.approval_service.WhatsAppService') as mock_wa_cls:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            mock_wa = MagicMock()
            mock_wa_cls.return_value = mock_wa

            # No phone number - should not send
            svc._async_generate_and_send('file-3', 'Test', None, None, False, 'whatsapp')
            mock_wa.send_document.assert_not_called()

    @patch('src.services.approval_service.os.path.exists', return_value=True)
    @patch('src.services.approval_service.os.remove')
    @patch('src.services.approval_service.drive_service')
    @patch('src.services.approval_service.pdf_service')
    def test_approval_updates_drive_json(self, mock_pdf, mock_drive, mock_remove, mock_exists):
        """Should update Drive JSON with 'Aprovado' status when is_approval=True."""
        mock_drive.read_json.return_value = {
            'estabelecimento': 'Loja W',
            'data_inspecao': '01/01/2024',
        }
        mock_pdf.generate_pdf_bytes.return_value = b'%PDF-fake'

        svc = ApprovalService()

        with patch('src.services.approval_service.get_db') as mock_get_db, \
             patch('builtins.open', MagicMock()), \
             patch('src.services.approval_service.WhatsAppService') as mock_wa_cls:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            mock_wa = MagicMock()
            mock_wa_cls.return_value = mock_wa

            svc._async_generate_and_send('file-4', 'Test', '999', None, True, 'whatsapp')

            mock_drive.update_file.assert_called_once()
            call_args = mock_drive.update_file.call_args[0]
            assert call_args[0] == 'file-4'
            updated_data = json.loads(call_args[1])
            assert updated_data['status'] == 'Aprovado'

    @patch('src.services.approval_service.os.path.exists', return_value=False)
    @patch('src.services.approval_service.drive_service')
    @patch('src.services.approval_service.pdf_service')
    def test_cleanup_skips_if_file_not_exists(self, mock_pdf, mock_drive, mock_exists):
        """Should not try to remove temp file if it doesn't exist."""
        mock_drive.read_json.return_value = {
            'estabelecimento': 'Loja V',
            'data_inspecao': '01/01/2024',
        }
        mock_pdf.generate_pdf_bytes.return_value = b'%PDF-fake'

        svc = ApprovalService()

        with patch('src.services.approval_service.get_db') as mock_get_db, \
             patch('builtins.open', MagicMock()), \
             patch('src.services.approval_service.os.remove') as mock_remove, \
             patch('src.services.approval_service.WhatsAppService') as mock_wa_cls:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter_by.return_value.first.return_value = None
            mock_wa_cls.return_value = MagicMock()

            svc._async_generate_and_send('file-5', 'Test', '999', None, False, 'whatsapp')
            mock_remove.assert_not_called()

    @patch('src.services.approval_service.drive_service')
    def test_exception_is_caught_and_logged(self, mock_drive):
        """Should catch and log exceptions without crashing."""
        mock_drive.read_json.side_effect = Exception("Drive unavailable")

        svc = ApprovalService()
        # Should not raise
        svc._async_generate_and_send('file-6', 'Test', '999', None, False, 'whatsapp')

    @patch('src.services.approval_service.os.path.exists', return_value=True)
    @patch('src.services.approval_service.os.remove')
    @patch('src.services.approval_service.drive_service')
    @patch('src.services.approval_service.pdf_service')
    def test_polyfill_aproveitamento_geral(self, mock_pdf, mock_drive, mock_remove, mock_exists):
        """Should polyfill 'aproveitamento_geral' if missing."""
        json_data = {
            'estabelecimento': 'Loja P',
            'data_inspecao': '01/01/2024',
            'areas_inspecionadas': [
                {'nome_area': 'Cozinha', 'itens': []}
            ],
            # No 'aproveitamento_geral' key
        }
        mock_drive.read_json.return_value = json_data
        mock_pdf.generate_pdf_bytes.return_value = b'%PDF-fake'

        svc = ApprovalService()

        with patch('src.services.approval_service.get_db') as mock_get_db, \
             patch('builtins.open', MagicMock()), \
             patch('src.services.approval_service.WhatsAppService') as mock_wa_cls:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter_by.return_value.first.return_value = None
            mock_wa_cls.return_value = MagicMock()

            svc._async_generate_and_send('file-p', 'Test', '999', None, False, 'whatsapp')

            # The polyfill should have added 'aproveitamento_geral'
            assert 'aproveitamento_geral' in json_data

    @patch('src.services.approval_service.os.path.exists', return_value=True)
    @patch('src.services.approval_service.os.remove')
    @patch('src.services.approval_service.drive_service')
    @patch('src.services.approval_service.pdf_service')
    def test_polyfill_area_aproveitamento_from_sector_stats(self, mock_pdf, mock_drive, mock_remove, mock_exists):
        """Should polyfill area 'aproveitamento' from detalhe_pontuacao."""
        json_data = {
            'estabelecimento': 'Loja Q',
            'data_inspecao': '01/01/2024',
            'detalhe_pontuacao': {
                'Cozinha': {'percentage': 85.0}
            },
            'areas_inspecionadas': [
                {'nome_area': 'Cozinha', 'itens': []}
                # Missing 'aproveitamento'
            ],
        }
        mock_drive.read_json.return_value = json_data
        mock_pdf.generate_pdf_bytes.return_value = b'%PDF-fake'

        svc = ApprovalService()

        with patch('src.services.approval_service.get_db') as mock_get_db, \
             patch('builtins.open', MagicMock()), \
             patch('src.services.approval_service.WhatsAppService') as mock_wa_cls:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter_by.return_value.first.return_value = None
            mock_wa_cls.return_value = MagicMock()

            svc._async_generate_and_send('file-q', 'Test', '999', None, False, 'whatsapp')

            area = json_data['areas_inspecionadas'][0]
            assert area['aproveitamento'] == 85.0

    @patch('src.services.approval_service.os.path.exists', return_value=True)
    @patch('src.services.approval_service.os.remove')
    @patch('src.services.approval_service.drive_service')
    @patch('src.services.approval_service.pdf_service')
    def test_rebuilds_data_from_db_action_plan(self, mock_pdf, mock_drive, mock_remove, mock_exists):
        """Should rebuild areas from DB ActionPlan items."""
        json_data = {
            'estabelecimento': 'Loja R',
            'data_inspecao': '01/01/2024',
            'areas_inspecionadas': [],
        }
        mock_drive.read_json.return_value = json_data
        mock_pdf.generate_pdf_bytes.return_value = b'%PDF-fake'

        # Mock DB inspection with action plan
        mock_insp = MagicMock()
        mock_plan = MagicMock()
        mock_plan.stats_json = {
            'score': 80,
            'max_score': 100,
            'by_sector': {
                'Cozinha': {'score': 40, 'max_score': 50},
                'Estoque': {'score': 40, 'max_score': 50},
            }
        }

        mock_item1 = MagicMock()
        mock_item1.sector = 'Cozinha'
        mock_item1.status.name = 'OPEN'
        mock_item1.problem_description = 'Problema 1'
        mock_item1.original_score = 5.0
        mock_item1.original_status = 'Não Conforme'
        mock_item1.manager_notes = None
        mock_item1.evidence_image_url = None

        # Need to make enum comparison work
        from src.models_db import ActionPlanItemStatus
        mock_item1.status = ActionPlanItemStatus.OPEN

        mock_plan.items = [mock_item1]
        mock_insp.action_plan = mock_plan
        mock_insp.status = MagicMock()
        mock_insp.status.value = 'PENDING_MANAGER_REVIEW'

        svc = ApprovalService()

        with patch('src.services.approval_service.get_db') as mock_get_db, \
             patch('builtins.open', MagicMock()), \
             patch('src.services.approval_service.WhatsAppService') as mock_wa_cls:
            mock_db = MagicMock()
            mock_db_async = MagicMock()

            # First call = _update_contact (skipped by calling _async directly)
            # The method calls get_db() internally for db_async
            mock_get_db.return_value = iter([mock_db_async])
            mock_db_async.query.return_value.filter_by.return_value.first.return_value = mock_insp
            mock_wa_cls.return_value = MagicMock()

            svc._async_generate_and_send('file-r', 'Test', '999', None, False, 'whatsapp')

            # Should have rebuilt areas from DB data
            assert len(json_data['areas_inspecionadas']) > 0

    @patch('src.services.approval_service.os.path.exists', return_value=True)
    @patch('src.services.approval_service.os.remove')
    @patch('src.services.approval_service.drive_service')
    @patch('src.services.approval_service.pdf_service')
    def test_email_no_address_logs_warning(self, mock_pdf, mock_drive, mock_remove, mock_exists):
        """Should log warning when email via but no email address."""
        mock_drive.read_json.return_value = {
            'estabelecimento': 'Loja E',
            'data_inspecao': '01/01/2024',
        }
        mock_pdf.generate_pdf_bytes.return_value = b'%PDF-fake'

        svc = ApprovalService()

        with patch('src.services.approval_service.get_db') as mock_get_db, \
             patch('builtins.open', MagicMock()), \
             patch('src.services.email_service.EmailService') as mock_email_cls:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter_by.return_value.first.return_value = None
            mock_email = MagicMock()
            mock_email_cls.return_value = mock_email

            svc._async_generate_and_send('file-e', 'Test', None, None, False, 'email')

            mock_email.send_email_with_attachment.assert_not_called()

    @patch('src.services.approval_service.os.path.exists', return_value=True)
    @patch('src.services.approval_service.os.remove')
    @patch('src.services.approval_service.drive_service')
    @patch('src.services.approval_service.pdf_service')
    def test_approval_caption_includes_aprovado(self, mock_pdf, mock_drive, mock_remove, mock_exists):
        """Should include 'aprovado' in WhatsApp caption when is_approval=True."""
        mock_drive.read_json.return_value = {
            'estabelecimento': 'Loja Cap',
            'data_inspecao': '01/01/2024',
        }
        mock_pdf.generate_pdf_bytes.return_value = b'%PDF-fake'

        svc = ApprovalService()

        with patch('src.services.approval_service.get_db') as mock_get_db, \
             patch('builtins.open', MagicMock()), \
             patch('src.services.approval_service.WhatsAppService') as mock_wa_cls:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            mock_db.query.return_value.filter_by.return_value.first.return_value = None
            mock_wa = MagicMock()
            mock_wa_cls.return_value = mock_wa

            svc._async_generate_and_send('file-cap', 'João', '999', None, True, 'whatsapp')

            call_args = mock_wa.send_document.call_args[0]
            caption = call_args[2]  # 3rd positional arg is caption
            assert 'aprovado' in caption
