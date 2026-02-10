"""Unit tests for app.py sharing/evidence routes.

Tests cover:
- GET /api/share_plan/<file_id> (share_plan GET redirect)
- POST /api/whatsapp_plan/<file_id> (whatsapp_plan)
- POST /api/email_plan/<file_id> (email_plan)
- POST /api/upload_evidence (upload_evidence)
- GET /evidence/<filename> (serve_evidence)
- POST /api/batch_details (batch_details)
- GET /api/status (get_status)
- POST /api/save_review/<file_id> (save_review)
- GET /download_revised_pdf/<file_id> (download_revised_pdf)
"""

import pytest
import uuid
import json
from unittest.mock import MagicMock, patch
from werkzeug.security import generate_password_hash


class MockUser:
    """Mock user for Flask-Login."""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.email = kwargs.get('email', 'test@test.com')
        self.name = kwargs.get('name', 'Test User')
        self.role = kwargs.get('role', 'MANAGER')
        self.password_hash = generate_password_hash('password123')
        self.is_active = True
        self.is_authenticated = True
        self.must_change_password = False
        self.company_id = kwargs.get('company_id', uuid.uuid4())
        self.establishments = kwargs.get('establishments', [])

    def get_id(self):
        return str(self.id)


class MockEstablishment:
    """Mock establishment."""
    def __init__(self, name='Loja Teste'):
        self.id = uuid.uuid4()
        self.name = name
        self.responsible_email = 'resp@test.com'
        self.company_id = uuid.uuid4()


def _setup_auth(client, user, mock_auth_uow):
    """Configure mock auth and session."""
    auth_uow = MagicMock()
    auth_uow.users.get_by_id.return_value = user
    mock_auth_uow.return_value = auth_uow

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)

    return auth_uow


# ===================================================================
#  /api/share_plan/<file_id> GET
# ===================================================================

class TestSharePlanGet:
    """Tests for GET /api/share_plan/<file_id>."""

    @patch('src.app.database')
    @patch('src.auth.get_uow')
    def test_share_plan_get_redirects_to_whatsapp(self, mock_auth_uow, mock_db, client, app):
        """GET should redirect to wa.me URL."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_insp = MagicMock()
        mock_insp.establishment = MockEstablishment('Loja ABC')

        mock_session = MagicMock()
        mock_db.db_session = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_insp

        response = client.get('/api/share_plan/test-file-123')

        assert response.status_code == 302
        assert 'wa.me' in response.headers['Location']

    @patch('src.app.database')
    @patch('src.auth.get_uow')
    def test_share_plan_get_no_inspection(self, mock_auth_uow, mock_db, client, app):
        """GET with no inspection should still work (uses fallback name)."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_session = MagicMock()
        mock_db.db_session = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        response = client.get('/api/share_plan/test-file-999')

        assert response.status_code == 302
        assert 'wa.me' in response.headers['Location']


# ===================================================================
#  /api/whatsapp_plan/<file_id>
# ===================================================================

class TestWhatsappPlan:
    """Tests for POST /api/whatsapp_plan/<file_id>."""

    @patch('src.auth.get_uow')
    def test_whatsapp_plan_no_phone(self, mock_auth_uow, client, app):
        """Should return 400 if no phone provided."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        response = client.post(
            '/api/whatsapp_plan/test-file-1',
            json={'phone': '', 'name': 'João'},
            content_type='application/json',
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Telefone' in data['error']

    @patch('src.whatsapp.WhatsAppService')
    @patch('src.auth.get_uow')
    def test_whatsapp_plan_not_configured(self, mock_auth_uow, mock_wa_cls, client, app):
        """Should return 503 if WhatsApp not configured."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_wa = MagicMock()
        mock_wa.is_configured.return_value = False
        mock_wa_cls.return_value = mock_wa

        response = client.post(
            '/api/whatsapp_plan/test-file-2',
            json={'phone': '11999998888', 'name': 'João'},
            content_type='application/json',
        )

        assert response.status_code == 503

    @patch('src.app.database')
    @patch('src.whatsapp.WhatsAppService')
    @patch('src.auth.get_uow')
    def test_whatsapp_plan_success(self, mock_auth_uow, mock_wa_cls, mock_db, client, app):
        """Should send WhatsApp and return success."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_insp = MagicMock()
        mock_insp.establishment = MockEstablishment('Loja X')

        mock_wa = MagicMock()
        mock_wa.is_configured.return_value = True
        mock_wa.send_text.return_value = True
        mock_wa_cls.return_value = mock_wa

        mock_session = MagicMock()
        mock_db.db_session = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_insp

        response = client.post(
            '/api/whatsapp_plan/test-file-3',
            json={'phone': '11999998888', 'name': 'João'},
            content_type='application/json',
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    @patch('src.app.database')
    @patch('src.whatsapp.WhatsAppService')
    @patch('src.auth.get_uow')
    def test_whatsapp_plan_send_fails(self, mock_auth_uow, mock_wa_cls, mock_db, client, app):
        """Should return 500 when send_text fails."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_insp = MagicMock()
        mock_insp.establishment = MockEstablishment('Loja Y')

        mock_wa = MagicMock()
        mock_wa.is_configured.return_value = True
        mock_wa.send_text.return_value = False
        mock_wa_cls.return_value = mock_wa

        mock_session = MagicMock()
        mock_db.db_session = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_insp

        response = client.post(
            '/api/whatsapp_plan/test-file-4',
            json={'phone': '5511999998888', 'name': 'Maria'},
            content_type='application/json',
        )

        assert response.status_code == 500

    @patch('src.app.database')
    @patch('src.whatsapp.WhatsAppService')
    @patch('src.auth.get_uow')
    def test_whatsapp_plan_adds_country_code(self, mock_auth_uow, mock_wa_cls, mock_db, client, app):
        """Should add BR country code for short numbers."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_insp = MagicMock()
        mock_insp.establishment = MockEstablishment()

        mock_wa = MagicMock()
        mock_wa.is_configured.return_value = True
        mock_wa.send_text.return_value = True
        mock_wa_cls.return_value = mock_wa

        mock_session = MagicMock()
        mock_db.db_session = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_insp

        response = client.post(
            '/api/whatsapp_plan/test-file-5',
            json={'phone': '(11) 99999-8888', 'name': 'Ana'},
            content_type='application/json',
        )

        assert response.status_code == 200
        call_args = mock_wa.send_text.call_args
        assert '5511999998888' in str(call_args)


# ===================================================================
#  /api/email_plan/<file_id>
# ===================================================================

class TestEmailPlan:
    """Tests for POST /api/email_plan/<file_id>."""

    @patch('src.app.database')
    @patch('src.auth.get_uow')
    def test_email_plan_success(self, mock_auth_uow, mock_db, client, app):
        """Should send email and return success."""
        user = MockUser(email='user@test.com', role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_insp = MagicMock()
        mock_est = MockEstablishment('Loja Email')
        mock_insp.establishment = mock_est

        mock_session = MagicMock()
        mock_db.db_session = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_insp

        mock_email_svc = MagicMock()
        mock_email_svc.send_email.return_value = True
        app.email_service = mock_email_svc

        response = client.post(
            '/api/email_plan/test-file-email-1',
            json={'target_email': 'dest@test.com', 'target_name': 'Destinatário'},
            content_type='application/json',
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        mock_email_svc.send_email.assert_called_once()

    @patch('src.app.database')
    @patch('src.auth.get_uow')
    def test_email_plan_no_email_service(self, mock_auth_uow, mock_db, client, app):
        """Should return 500 if email service unavailable."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_insp = MagicMock()
        mock_insp.establishment = MockEstablishment()

        mock_session = MagicMock()
        mock_db.db_session = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_insp

        app.email_service = None

        response = client.post(
            '/api/email_plan/test-file-email-2',
            json={'target_email': 'dest@test.com'},
            content_type='application/json',
        )

        assert response.status_code == 500

    @patch('src.app.database')
    @patch('src.auth.get_uow')
    def test_email_plan_ses_not_verified(self, mock_auth_uow, mock_db, client, app):
        """Should return 400 for SES 'not verified' error."""
        user = MockUser(email='user@test.com', role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_insp = MagicMock()
        mock_insp.establishment = MockEstablishment()

        mock_session = MagicMock()
        mock_db.db_session = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_insp

        mock_email_svc = MagicMock()
        mock_email_svc.send_email.side_effect = Exception("Email address is not verified in SES")
        app.email_service = mock_email_svc

        response = client.post(
            '/api/email_plan/test-file-email-3',
            json={'target_email': 'unverified@test.com'},
            content_type='application/json',
        )

        assert response.status_code == 400

    @patch('src.app.database')
    @patch('src.auth.get_uow')
    def test_email_plan_defaults_to_user_email(self, mock_auth_uow, mock_db, client, app):
        """Should default target_email to current user's email."""
        user = MockUser(email='myself@test.com', role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_insp = MagicMock()
        mock_insp.establishment = MockEstablishment()

        mock_session = MagicMock()
        mock_db.db_session = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_insp

        mock_email_svc = MagicMock()
        mock_email_svc.send_email.return_value = True
        app.email_service = mock_email_svc

        response = client.post(
            '/api/email_plan/test-file-email-4',
            json={},  # No target_email
            content_type='application/json',
        )

        assert response.status_code == 200
        call_args = mock_email_svc.send_email.call_args[0]
        assert call_args[0] == 'myself@test.com'


# ===================================================================
#  /api/upload_evidence
# ===================================================================

class TestUploadEvidence:
    """Tests for POST /api/upload_evidence."""

    @patch('src.auth.get_uow')
    def test_upload_evidence_no_file(self, mock_auth_uow, client, app):
        """Should return 400 if no file part."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        response = client.post('/api/upload_evidence')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'file' in data['error'].lower() or 'No file' in data['error']

    @patch('src.auth.get_uow')
    def test_upload_evidence_empty_filename(self, mock_auth_uow, client, app):
        """Should return 400 for empty filename."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        from io import BytesIO
        data = {'file': (BytesIO(b''), '')}
        response = client.post(
            '/api/upload_evidence',
            data=data,
            content_type='multipart/form-data',
        )
        assert response.status_code == 400

    @patch('src.auth.get_uow')
    def test_upload_evidence_invalid_file_type(self, mock_auth_uow, client, app):
        """Should reject non-image files."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        from io import BytesIO
        data = {'file': (BytesIO(b'This is not an image'), 'test.png')}
        response = client.post(
            '/api/upload_evidence',
            data=data,
            content_type='multipart/form-data',
        )
        assert response.status_code == 400

    @patch('src.app.storage_service')
    @patch('src.auth.get_uow')
    def test_upload_evidence_success(self, mock_auth_uow, mock_storage, client, app):
        """Should upload successfully with valid image."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_storage.upload_file.return_value = '/static/uploads/evidence/test.jpg'

        from io import BytesIO
        jpeg_content = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        data = {'file': (BytesIO(jpeg_content), 'evidence.jpg')}
        response = client.post(
            '/api/upload_evidence',
            data=data,
            content_type='multipart/form-data',
        )

        assert response.status_code == 200
        resp_data = json.loads(response.data)
        assert 'url' in resp_data
        assert '/evidence/' in resp_data['url']

    @patch('src.app.storage_service')
    @patch('src.auth.get_uow')
    def test_upload_evidence_gcs_url_normalized(self, mock_auth_uow, mock_storage, client, app):
        """Should normalize GCS URLs to proxy route."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_storage.upload_file.return_value = 'https://storage.googleapis.com/bucket/evidence/img.jpg'

        from io import BytesIO
        jpeg_content = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        data = {'file': (BytesIO(jpeg_content), 'evidence.jpg')}
        response = client.post(
            '/api/upload_evidence',
            data=data,
            content_type='multipart/form-data',
        )

        assert response.status_code == 200
        resp_data = json.loads(response.data)
        assert '/evidence/' in resp_data['url']
        assert 'storage.googleapis.com' not in resp_data['url']


# ===================================================================
#  /evidence/<filename>
# ===================================================================

class TestServeEvidence:
    """Tests for GET /evidence/<filename>."""

    @patch('src.services.storage_service.storage_service')
    def test_serve_evidence_not_found(self, mock_storage, client, app):
        """Should return 404 when evidence not found anywhere."""
        mock_storage.client = None
        mock_storage.bucket_name = None

        with patch('os.path.exists', return_value=False):
            response = client.get('/evidence/nonexistent.png')

        assert response.status_code == 404

    @patch('src.services.storage_service.storage_service')
    def test_serve_evidence_gcs(self, mock_storage, client, app):
        """Should serve from GCS when available."""
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_bytes.return_value = b'\x89PNG\r\n\x1a\n' + b'\x00' * 10

        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        mock_storage.client = MagicMock()
        mock_storage.bucket_name = 'test-bucket'
        mock_storage.client.bucket.return_value = mock_bucket

        response = client.get('/evidence/gcs_image.png')

        assert response.status_code == 200
        assert response.content_type.startswith('image/')


# ===================================================================
#  /api/batch_details
# ===================================================================

class TestBatchDetails:
    """Tests for POST /api/batch_details."""

    def test_batch_details_empty_ids(self, client, app):
        """Should return empty dict for empty ids."""
        response = client.post(
            '/api/batch_details',
            json={'ids': []},
            content_type='application/json',
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == {}

    @patch('src.container.get_uow')
    def test_batch_details_with_inspections(self, mock_uow, client, app):
        """Should return inspection details for given IDs."""
        mock_insp = MagicMock()
        mock_insp.drive_file_id = 'file-123'
        mock_insp.ai_raw_response = {'titulo': 'Relatório A'}
        mock_insp.establishment = MockEstablishment('Loja A')

        uow = MagicMock()
        uow.inspections.get_batch_by_file_ids.return_value = [mock_insp]
        mock_uow.return_value = uow

        with patch('src.app.drive_service', None):
            response = client.post(
                '/api/batch_details',
                json={'ids': ['file-123', 'file-missing']},
                content_type='application/json',
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'file-123' in data
        assert data['file-123']['name'] == 'Relatório A'

    @patch('src.container.get_uow')
    def test_batch_details_with_drive_fallback(self, mock_uow, client, app):
        """Should fall back to Drive for missing IDs."""
        uow = MagicMock()
        uow.inspections.get_batch_by_file_ids.return_value = []
        mock_uow.return_value = uow

        mock_drive = MagicMock()
        mock_drive.read_json.return_value = {
            'titulo': 'Drive Report',
            'estabelecimento': 'Loja Drive',
            'data_inspecao': '01/01/2024',
        }

        with patch('src.app.drive_service', mock_drive):
            response = client.post(
                '/api/batch_details',
                json={'ids': ['drive-file-1']},
                content_type='application/json',
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'drive-file-1' in data
        assert data['drive-file-1']['name'] == 'Drive Report'


# ===================================================================
#  /api/save_review/<file_id>
# ===================================================================

class TestSaveReview:
    """Tests for POST /api/save_review/<file_id>."""

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_save_review_updates_items(self, mock_auth_uow, mock_app_uow, client, app):
        """Should update action plan items."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        item_id = str(uuid.uuid4())
        mock_item = MagicMock()

        uow = MagicMock()
        uow.action_plans.get_item_by_id.return_value = mock_item
        mock_app_uow.return_value = uow

        response = client.post(
            '/api/save_review/test-file-sr1',
            json={item_id: {'is_corrected': True, 'correction_notes': 'Fixed'}},
            content_type='application/json',
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        uow.commit.assert_called_once()

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_save_review_skips_missing_items(self, mock_auth_uow, mock_app_uow, client, app):
        """Should skip items not found in DB."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        item_id = str(uuid.uuid4())

        uow = MagicMock()
        uow.action_plans.get_item_by_id.return_value = None
        mock_app_uow.return_value = uow

        response = client.post(
            '/api/save_review/test-file-sr2',
            json={item_id: {'is_corrected': True}},
            content_type='application/json',
        )

        assert response.status_code == 200

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_save_review_updates_evidence_url(self, mock_auth_uow, mock_app_uow, client, app):
        """Should update evidence_image_url."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        item_id = str(uuid.uuid4())
        mock_item = MagicMock()

        uow = MagicMock()
        uow.action_plans.get_item_by_id.return_value = mock_item
        mock_app_uow.return_value = uow

        response = client.post(
            '/api/save_review/test-file-sr3',
            json={item_id: {'evidence_image_url': '/evidence/photo.png'}},
            content_type='application/json',
        )

        assert response.status_code == 200
        assert mock_item.evidence_image_url == '/evidence/photo.png'

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_save_review_error_returns_500(self, mock_auth_uow, mock_app_uow, client, app):
        """Should return 500 on error."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_app_uow.side_effect = Exception("DB error")

        response = client.post(
            '/api/save_review/test-file-sr4',
            json={'item-id': {'is_corrected': True}},
            content_type='application/json',
        )

        assert response.status_code == 500


# ===================================================================
#  /download_revised_pdf/<file_id>
# ===================================================================

class TestDownloadRevisedPdf:
    """Tests for GET /download_revised_pdf/<file_id>."""

    @patch('src.container.get_inspection_data_service')
    def test_download_pdf_success(self, mock_data_svc, client, app):
        """Should generate and return PDF."""
        svc = MagicMock()
        svc.get_pdf_data.return_value = {
            'nome_estabelecimento': 'Loja PDF',
            'areas_inspecionadas': [],
        }
        mock_data_svc.return_value = svc

        with patch('src.app.pdf_service') as mock_pdf:
            mock_pdf.generate_pdf_bytes.return_value = b'%PDF-1.4 fake'
            mock_pdf.enrich_data = MagicMock()

            response = client.get('/download_revised_pdf/test-pdf-1')

        assert response.status_code == 200
        assert response.content_type == 'application/pdf'

    @patch('src.container.get_inspection_data_service')
    def test_download_pdf_not_found(self, mock_data_svc, client, app):
        """Should return 404 when no data found."""
        svc = MagicMock()
        svc.get_pdf_data.return_value = None
        mock_data_svc.return_value = svc

        response = client.get('/download_revised_pdf/nonexistent-file')

        assert response.status_code == 404

    def test_download_pdf_no_service(self, client, app):
        """Should return 500 when pdf_service is None."""
        with patch('src.app.pdf_service', None):
            response = client.get('/download_revised_pdf/test-pdf-3')

        assert response.status_code == 500
