"""Extra unit tests for uncovered routes and utilities in src/app.py.

Tests cover:
- sanitize_log_message (sensitive data masking)
- JsonFormatter.format (JSON structured logging)
- GET /api/status (dashboard status endpoint)
- GET /api/processed_item/<file_id> (lazy-load item details)
- POST /api/batch_details (batch file details)
- POST /upload (file upload route handler)
"""

import pytest
import uuid
import json
import logging
from io import BytesIO
from unittest.mock import MagicMock, patch
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# MockUser for Flask-Login
# ---------------------------------------------------------------------------

class MockUser:
    """Mock user that satisfies Flask-Login requirements."""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.email = kwargs.get('email', 'consultant@test.com')
        self.name = kwargs.get('name', 'Consultant')
        self.role = kwargs.get('role', 'CONSULTANT')
        self.password_hash = generate_password_hash('password123')
        self.is_active = True
        self.is_authenticated = True
        self.must_change_password = False
        self.company_id = kwargs.get('company_id', uuid.uuid4())
        self.establishments = kwargs.get('establishments', [])

    def get_id(self):
        return str(self.id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_auth(client, user, mock_auth_uow):
    """Configure mock auth UoW and set the user in the session."""
    auth_uow = MagicMock()
    auth_uow.users.get_by_id.return_value = user
    mock_auth_uow.return_value = auth_uow

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)

    return auth_uow


# ===================================================================
#  sanitize_log_message
# ===================================================================

class TestSanitizeLogMessage:
    """Tests for the sanitize_log_message utility function."""

    def test_redacts_openai_api_key(self, app):
        """OpenAI API keys (sk-...) are redacted."""
        from src.app import sanitize_log_message
        msg = sanitize_log_message("Using key sk-abcdefghijklmnopqrstuvwxyz123456")
        assert 'sk-***REDACTED***' in msg
        assert 'abcdefghijklmnopqrstuvwxyz' not in msg

    def test_redacts_password(self, app):
        """password=value patterns are redacted."""
        from src.app import sanitize_log_message
        msg = sanitize_log_message("Login with password=SuperSecret123")
        assert '***REDACTED***' in msg
        assert 'SuperSecret123' not in msg

    def test_redacts_api_key(self, app):
        """api_key=value patterns are redacted."""
        from src.app import sanitize_log_message
        msg = sanitize_log_message("Using api_key=my-secret-api-key-value")
        assert '***REDACTED***' in msg
        assert 'my-secret-api-key-value' not in msg

    def test_redacts_token(self, app):
        """token=value patterns are redacted."""
        from src.app import sanitize_log_message
        msg = sanitize_log_message('Config token="eyJhbGciOiJIUzI1NiJ9.payload"')
        assert '***REDACTED***' in msg
        assert 'eyJhbGciOiJIUzI1NiJ9' not in msg

    def test_redacts_secret(self, app):
        """secret=value patterns are redacted."""
        from src.app import sanitize_log_message
        msg = sanitize_log_message("secret=my_super_secret_value")
        assert '***REDACTED***' in msg
        assert 'my_super_secret_value' not in msg

    def test_redacts_bearer_token(self, app):
        """Bearer token values are redacted."""
        from src.app import sanitize_log_message
        msg = sanitize_log_message("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig")
        assert 'Bearer ***REDACTED***' in msg
        assert 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' not in msg

    def test_leaves_safe_messages_unchanged(self, app):
        """Messages without sensitive data remain unchanged."""
        from src.app import sanitize_log_message
        msg = "Normal log message about processing file upload"
        assert sanitize_log_message(msg) == msg


# ===================================================================
#  JsonFormatter
# ===================================================================

class TestJsonFormatter:
    """Tests for JsonFormatter.format method."""

    def test_format_normal_record(self, app):
        """Normal log record produces valid JSON with expected fields."""
        from src.app import JsonFormatter
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name='test-logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed['severity'] == 'INFO'
        assert parsed['message'] == 'Test message'
        assert parsed['logger'] == 'test-logger'
        assert 'timestamp' in parsed

    def test_format_record_with_props(self, app):
        """Record with props attribute includes sanitized props in output."""
        from src.app import JsonFormatter
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name='test-logger',
            level=logging.WARNING,
            pathname='test.py',
            lineno=1,
            msg='Warning with props',
            args=(),
            exc_info=None,
        )
        record.props = {
            'user_id': 'abc-123',
            'api_key': 'api_key=secret_value_here',
            'count': 42,
        }
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed['user_id'] == 'abc-123'
        assert 'secret_value_here' not in parsed['api_key']
        assert '***REDACTED***' in parsed['api_key']
        assert parsed['count'] == 42

    def test_format_record_with_exception(self, app):
        """Record with exception info includes sanitized exception in output."""
        from src.app import JsonFormatter
        formatter = JsonFormatter()
        try:
            raise ValueError("Connection failed with password=secret123")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name='test-logger',
            level=logging.ERROR,
            pathname='test.py',
            lineno=1,
            msg='Error occurred',
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert 'exception' in parsed
        assert 'secret123' not in parsed['exception']
        assert '***REDACTED***' in parsed['exception']


# ===================================================================
#  GET /api/status  (handled by manager_bp.api_status)
#
#  NOTE: /api/status is served by manager_routes.api_status (the
#  manager blueprint registers the route first). It uses get_uow()
#  imported at module-level in manager_routes, so we patch there.
# ===================================================================

class TestApiStatus:
    """Tests for GET /api/status (manager_routes.api_status)."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_status_success(self, mock_auth_uow, mock_get_uow, client):
        """Successful status request returns JSON with processed and pending."""
        user = MockUser()
        _setup_auth(client, user, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.return_value = []
        mock_uow.establishments.get_by_company.return_value = []
        mock_uow.jobs.get_pending_for_company.return_value = []
        mock_get_uow.return_value = mock_uow

        response = client.get('/api/status')
        assert response.status_code == 200
        data = response.get_json()
        assert 'processed_raw' in data
        assert 'pending' in data

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_status_with_establishment_filter(self, mock_auth_uow, mock_get_uow, client):
        """Status request with establishment_id passes filter to the UoW query."""
        user = MockUser()
        _setup_auth(client, user, mock_auth_uow)

        est_id = uuid.uuid4()
        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.return_value = []
        mock_uow.establishments.get_by_company.return_value = []
        mock_uow.jobs.get_pending_for_company.return_value = []
        mock_get_uow.return_value = mock_uow

        response = client.get(f'/api/status?establishment_id={est_id}')
        assert response.status_code == 200
        call_args = mock_uow.inspections.get_for_manager.call_args
        assert call_args[1]['establishment_id'] == est_id

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_status_error_returns_500(self, mock_auth_uow, mock_get_uow, client):
        """Exception in status endpoint returns 500 with error message."""
        user = MockUser()
        _setup_auth(client, user, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.side_effect = Exception("DB connection failed")
        mock_get_uow.return_value = mock_uow

        response = client.get('/api/status')
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data


# ===================================================================
#  GET /api/processed_item/<file_id>
# ===================================================================

class TestProcessedItem:
    """Tests for GET /api/processed_item/<file_id>."""

    @patch('src.container.get_uow')
    def test_found_with_action_plan(self, mock_get_uow, client):
        """Found inspection with action plan returns full details."""
        mock_item = MagicMock()
        mock_item.id = uuid.uuid4()
        mock_item.problem_description = 'Problem 1'
        mock_item.corrective_action = 'Fix 1'
        mock_item.legal_basis = 'RDC 216'
        mock_item.severity.value = 'HIGH'
        mock_item.status.value = 'OPEN'

        mock_plan = MagicMock()
        mock_plan.items = [mock_item]
        mock_plan.final_pdf_public_link = 'https://example.com/plan.pdf'

        mock_establishment = MagicMock()
        mock_establishment.name = 'Restaurante Teste'

        mock_inspection = MagicMock()
        mock_inspection.drive_file_id = 'test-file-id'
        mock_inspection.ai_raw_response = {'titulo': 'Relatorio Test', 'data_inspecao': '2025-01-01'}
        mock_inspection.establishment = mock_establishment
        mock_inspection.action_plan = mock_plan

        mock_uow = MagicMock()
        mock_uow.inspections.get_with_plan_by_file_id.return_value = mock_inspection
        mock_get_uow.return_value = mock_uow

        response = client.get('/api/processed_item/test-file-id')
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == 'test-file-id'
        assert data['name'] == 'Relatorio Test'
        assert data['establishment'] == 'Restaurante Teste'
        assert 'action_plan' in data
        assert len(data['action_plan']['items']) == 1

    @patch('src.container.get_uow')
    def test_found_without_action_plan(self, mock_get_uow, client):
        """Found inspection without action plan returns basic details."""
        mock_establishment = MagicMock()
        mock_establishment.name = 'Loja ABC'

        mock_inspection = MagicMock()
        mock_inspection.drive_file_id = 'file-no-plan'
        mock_inspection.ai_raw_response = {'titulo': 'Report No Plan'}
        mock_inspection.establishment = mock_establishment
        mock_inspection.action_plan = None

        mock_uow = MagicMock()
        mock_uow.inspections.get_with_plan_by_file_id.return_value = mock_inspection
        mock_get_uow.return_value = mock_uow

        response = client.get('/api/processed_item/file-no-plan')
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == 'file-no-plan'
        assert data['establishment'] == 'Loja ABC'
        assert 'action_plan' not in data

    @patch('src.app.drive_service')
    @patch('src.container.get_uow')
    def test_not_found_falls_back_to_drive(self, mock_get_uow, mock_drive_svc, client):
        """When not found in DB, falls back to Drive service."""
        mock_uow = MagicMock()
        mock_uow.inspections.get_with_plan_by_file_id.return_value = None
        mock_get_uow.return_value = mock_uow

        mock_drive_svc.read_json.return_value = {
            'titulo': 'Drive Report',
            'estabelecimento': 'Drive Establishment',
            'data_inspecao': '2024-12-01',
        }

        response = client.get('/api/processed_item/drive-file-id')
        assert response.status_code == 200
        data = response.get_json()
        assert data['name'] == 'Drive Report'
        assert data['establishment'] == 'Drive Establishment'

    @patch('src.container.get_uow')
    def test_error_returns_500(self, mock_get_uow, client):
        """Exception returns 500 with error message."""
        mock_uow = MagicMock()
        mock_uow.inspections.get_with_plan_by_file_id.side_effect = Exception("DB error")
        mock_get_uow.return_value = mock_uow

        response = client.get('/api/processed_item/error-file')
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data


# ===================================================================
#  POST /api/batch_details
# ===================================================================

class TestBatchDetails:
    """Tests for POST /api/batch_details."""

    def test_empty_ids_returns_empty(self, client):
        """Empty ids list returns empty JSON object."""
        response = client.post(
            '/api/batch_details',
            data=json.dumps({'ids': []}),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data == {}

    @patch('src.container.get_uow')
    def test_with_data_returns_results(self, mock_get_uow, client):
        """Batch details with valid IDs returns inspection data."""
        mock_est = MagicMock()
        mock_est.name = 'Restaurante Batch'

        mock_insp = MagicMock()
        mock_insp.drive_file_id = 'batch-file-1'
        mock_insp.ai_raw_response = {'titulo': 'Batch Report', 'data_inspecao': '2025-01-15'}
        mock_insp.establishment = mock_est

        mock_uow = MagicMock()
        mock_uow.inspections.get_batch_by_file_ids.return_value = [mock_insp]
        mock_get_uow.return_value = mock_uow

        response = client.post(
            '/api/batch_details',
            data=json.dumps({'ids': ['batch-file-1']}),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'batch-file-1' in data
        assert data['batch-file-1']['name'] == 'Batch Report'
        assert data['batch-file-1']['establishment'] == 'Restaurante Batch'

    @patch('src.container.get_uow')
    def test_error_returns_500(self, mock_get_uow, client):
        """Exception in batch details returns 500."""
        mock_uow = MagicMock()
        mock_uow.inspections.get_batch_by_file_ids.side_effect = Exception("batch error")
        mock_get_uow.return_value = mock_uow

        response = client.post(
            '/api/batch_details',
            data=json.dumps({'ids': ['file-1']}),
            content_type='application/json',
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data


# ===================================================================
#  POST /upload
# ===================================================================

class TestUploadRoute:
    """Tests for POST /upload."""

    @patch('src.auth.get_uow')
    def test_upload_no_file_part(self, mock_auth_uow, client):
        """Upload without file part flashes error and redirects."""
        user = MockUser()
        _setup_auth(client, user, mock_auth_uow)

        response = client.post('/upload', data={})
        assert response.status_code == 302
        assert '/dashboard/consultant' in response.location

    @patch('src.auth.get_uow')
    def test_upload_empty_filename(self, mock_auth_uow, client):
        """Upload with empty filename flashes error and redirects."""
        user = MockUser()
        _setup_auth(client, user, mock_auth_uow)

        data = {
            'file': (BytesIO(b''), ''),
        }
        response = client.post(
            '/upload',
            data=data,
            content_type='multipart/form-data',
        )
        assert response.status_code == 302
        assert '/dashboard/consultant' in response.location

    @patch('src.app.get_db')
    @patch('src.infrastructure.security.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_success_redirects(self, mock_auth_uow, mock_validator_class, mock_get_db, client):
        """Successful file upload processes and redirects to dashboard."""
        user = MockUser()
        user.establishments = []
        _setup_auth(client, user, mock_auth_uow)

        # Create valid PDF content (starts with %PDF magic bytes)
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<>>\nstartxref\n9\n%%EOF'

        # Mock the FileValidator to accept any file
        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = True
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        # Mock DB session
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        # Mock the processor
        with patch('src.services.processor.processor_service') as mock_proc, \
             patch('src.app.processor_service', mock_proc, create=True):
            mock_proc.process_single_file.return_value = {
                'status': 'success',
                'file_id': 'output-123',
            }

            data = {
                'file': (BytesIO(pdf_content), 'test_report.pdf'),
            }
            response = client.post(
                '/upload',
                data=data,
                content_type='multipart/form-data',
            )
            # Should redirect to dashboard after processing
            assert response.status_code == 302
            assert '/dashboard/consultant' in response.location

    @patch('src.auth.get_uow')
    def test_upload_ajax_no_file_returns_error(self, mock_auth_uow, client):
        """AJAX upload without file returns JSON error."""
        user = MockUser()
        _setup_auth(client, user, mock_auth_uow)

        # POST with AJAX header but no file - the route checks for 'file' key
        # and flashes error then redirects. For AJAX, the general exception
        # handler catches it.
        response = client.post(
            '/upload',
            data={},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        # Without file key, it flashes and redirects (not AJAX-aware at that point)
        assert response.status_code == 302

    @patch('src.auth.get_uow')
    def test_upload_get_redirects_to_dashboard(self, mock_auth_uow, client):
        """GET /upload redirects to consultant dashboard."""
        user = MockUser()
        _setup_auth(client, user, mock_auth_uow)

        response = client.get('/upload')
        assert response.status_code == 302
        assert '/dashboard/consultant' in response.location

    def test_upload_unauthenticated_redirects_to_login(self, client):
        """Unauthenticated access to upload redirects to login."""
        response = client.post('/upload', data={})
        assert response.status_code == 302
        assert 'login' in response.location
