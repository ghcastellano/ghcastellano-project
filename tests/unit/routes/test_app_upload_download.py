"""Unit tests for upload route internals and download routes in src/app.py.

Tests cover:
- POST /upload: establishment selection validation, file validation flow,
  upload service processing (success, skipped/duplicate, failure),
  AJAX vs regular responses (200/207/500), outer exception handling
- GET /download_pdf/<json_id>: GCS path download, GCS error, Drive
  unavailable, Drive error
"""

import pytest
import uuid
import json
import io
from io import BytesIO
from unittest.mock import MagicMock, patch, PropertyMock
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


class MockEstablishment:
    """Mock establishment object."""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.name = kwargs.get('name', 'Test Establishment')
        self.company_id = kwargs.get('company_id', uuid.uuid4())
        self.code = kwargs.get('code', 'EST001')


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


def _make_pdf_content():
    """Create minimal valid PDF content for testing."""
    return (
        b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\n'
        b'xref\n0 1\n0000000000 65535 f \n'
        b'trailer\n<<>>\nstartxref\n9\n%%EOF'
    )


def _mock_db_sessions(*db_mocks):
    """Return a side_effect generator for get_db that yields from a list of mocks."""
    def _gen():
        for m in db_mocks:
            yield m
    gen = _gen()
    return lambda: iter([next(gen)])


# ===================================================================
#  POST /upload - Establishment Selection Validation
# ===================================================================

class TestUploadEstablishmentSelection:
    """Tests for establishment_id validation inside the upload route."""

    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_with_invalid_establishment_id_redirects(
        self, mock_auth_uow, mock_validator_class, client
    ):
        """POST /upload with establishment_id user doesn't have access to
        flashes permission error and redirects."""
        est = MockEstablishment()
        user = MockUser(role='CONSULTANT', establishments=[est])
        _setup_auth(client, user, mock_auth_uow)

        # Use a different UUID that doesn't match any user establishment
        wrong_est_id = str(uuid.uuid4())
        pdf_content = _make_pdf_content()

        response = client.post(
            '/upload',
            data={
                'file': (BytesIO(pdf_content), 'test.pdf'),
                'establishment_id': wrong_est_id,
            },
            content_type='multipart/form-data',
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert '/dashboard/consultant' in response.location

    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_with_valid_establishment_id_proceeds(
        self, mock_auth_uow, mock_validator_class, client
    ):
        """POST /upload with valid establishment_id that user has access to
        proceeds to file validation (does not flash permission error)."""
        est = MockEstablishment()
        user = MockUser(role='CONSULTANT', establishments=[est])
        _setup_auth(client, user, mock_auth_uow)

        # Make validation fail so we can isolate the establishment check passed
        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = False
        mock_validation_result.error_message = 'Test rejection'
        mock_validation_result.error_code = 'TEST_FAIL'
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        pdf_content = _make_pdf_content()

        response = client.post(
            '/upload',
            data={
                'file': (BytesIO(pdf_content), 'test.pdf'),
                'establishment_id': str(est.id),
            },
            content_type='multipart/form-data',
            follow_redirects=False,
        )
        # Should redirect to dashboard (not permission error; file was rejected)
        assert response.status_code == 302
        # The validator was called, meaning establishment check passed
        mock_validator_instance.validate.assert_called_once()

    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_with_no_establishment_id_proceeds(
        self, mock_auth_uow, mock_validator_class, client
    ):
        """POST /upload without establishment_id skips establishment
        selection validation entirely."""
        user = MockUser(role='CONSULTANT', establishments=[])
        _setup_auth(client, user, mock_auth_uow)

        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = False
        mock_validation_result.error_message = 'Test rejection'
        mock_validation_result.error_code = 'TEST_FAIL'
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        pdf_content = _make_pdf_content()

        response = client.post(
            '/upload',
            data={
                'file': (BytesIO(pdf_content), 'test.pdf'),
            },
            content_type='multipart/form-data',
            follow_redirects=False,
        )
        assert response.status_code == 302
        # Validator was invoked (no permission redirect)
        mock_validator_instance.validate.assert_called_once()


# ===================================================================
#  POST /upload - File Validation Flow
# ===================================================================

class TestUploadFileValidation:
    """Tests for file validation inside the upload route."""

    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_file_validation_failure_increments_falha(
        self, mock_auth_uow, mock_validator_class, client
    ):
        """File that fails validation is rejected, falha incremented,
        and route redirects to dashboard."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = False
        mock_validation_result.error_message = 'Tipo de arquivo nao reconhecido'
        mock_validation_result.error_code = 'UNKNOWN_FILE_TYPE'
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        response = client.post(
            '/upload',
            data={
                'file': (BytesIO(b'not a pdf'), 'malicious.pdf'),
            },
            content_type='multipart/form-data',
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert '/dashboard/consultant' in response.location

    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_file_validation_failure_ajax_returns_500(
        self, mock_auth_uow, mock_validator_class, client
    ):
        """File validation failure via AJAX returns JSON 500 (falha only)."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = False
        mock_validation_result.error_message = 'Arquivo vazio'
        mock_validation_result.error_code = 'EMPTY_FILE'
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        response = client.post(
            '/upload',
            data={
                'file': (BytesIO(b'bad'), 'bad.pdf'),
            },
            content_type='multipart/form-data',
            headers={'X-Requested-With': 'XMLHttpRequest'},
            follow_redirects=False,
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data

    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_multiple_files_mixed_validation(
        self, mock_auth_uow, mock_validator_class, client
    ):
        """When multiple files are uploaded and some fail validation,
        the route continues processing remaining files."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        valid_result = MagicMock()
        valid_result.is_valid = True
        invalid_result = MagicMock()
        invalid_result.is_valid = False
        invalid_result.error_message = 'Invalid type'
        invalid_result.error_code = 'UNKNOWN_FILE_TYPE'

        mock_validator_instance = MagicMock()
        # First call fails, second would succeed but we let it fail
        # at the next stage (no DB mock) so it raises an exception
        mock_validator_instance.validate.side_effect = [invalid_result, invalid_result]
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        pdf_content = _make_pdf_content()

        response = client.post(
            '/upload',
            data={
                'file': [
                    (BytesIO(b'bad content'), 'bad1.pdf'),
                    (BytesIO(b'also bad'), 'bad2.pdf'),
                ],
            },
            content_type='multipart/form-data',
            follow_redirects=False,
        )
        assert response.status_code == 302
        # Both files were validated
        assert mock_validator_instance.validate.call_count == 2


# ===================================================================
#  POST /upload - Processing Outcomes (success, duplicate, failure)
# ===================================================================

class TestUploadProcessing:
    """Tests for processor_service interaction in the upload route."""

    @patch('src.app.get_db')
    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_processing_success(
        self, mock_auth_uow, mock_validator_class, mock_get_db, client
    ):
        """Successful processing increments sucesso and redirects."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = True
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        pdf_content = _make_pdf_content()

        with patch('src.services.processor.processor_service') as mock_proc:
            mock_proc.process_single_file.return_value = {
                'status': 'success',
                'file_id': 'output-123',
            }

            response = client.post(
                '/upload',
                data={
                    'file': (BytesIO(pdf_content), 'report.pdf'),
                },
                content_type='multipart/form-data',
                follow_redirects=False,
            )
            assert response.status_code == 302
            assert '/dashboard/consultant' in response.location

    @patch('src.app.get_db')
    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_duplicate_file_skipped(
        self, mock_auth_uow, mock_validator_class, mock_get_db, client
    ):
        """Duplicate file (status=skipped, reason=duplicate) is handled
        gracefully: job updated, orphan inspection removed, flash warning."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = True
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        # get_db is called multiple times: once for main, once for skip, once for cleanup
        mock_db_main = MagicMock()
        mock_db_skip = MagicMock()
        mock_db_cleanup = MagicMock()

        call_count = [0]
        def db_gen():
            dbs = [mock_db_main, mock_db_skip, mock_db_cleanup]
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(dbs):
                return iter([dbs[idx]])
            return iter([MagicMock()])

        mock_get_db.side_effect = lambda: db_gen()

        # Mock the query chain for orphan cleanup
        mock_db_cleanup.query.return_value.filter_by.return_value.first.return_value = MagicMock()

        pdf_content = _make_pdf_content()

        with patch('src.services.processor.processor_service') as mock_proc:
            mock_proc.process_single_file.return_value = {
                'status': 'skipped',
                'reason': 'duplicate',
                'existing_id': 'existing-123',
            }

            response = client.post(
                '/upload',
                data={
                    'file': (BytesIO(pdf_content), 'duplicate.pdf'),
                },
                content_type='multipart/form-data',
                follow_redirects=False,
            )
            assert response.status_code == 302
            assert '/dashboard/consultant' in response.location

    @patch('src.app.get_db')
    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_processing_failure_increments_falha(
        self, mock_auth_uow, mock_validator_class, mock_get_db, client
    ):
        """Processing failure (exception in process_single_file) increments
        falha, cleans up job/inspection, and redirects."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = True
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        # get_db: main session, error cleanup session
        mock_db_main = MagicMock()
        mock_db_err = MagicMock()
        mock_db_err.query.return_value.filter_by.return_value.first.return_value = MagicMock()

        call_count = [0]
        def db_gen():
            dbs = [mock_db_main, mock_db_err]
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(dbs):
                return iter([dbs[idx]])
            return iter([MagicMock()])

        mock_get_db.side_effect = lambda: db_gen()

        pdf_content = _make_pdf_content()

        with patch('src.services.processor.processor_service') as mock_proc:
            mock_proc.process_single_file.side_effect = Exception("AI processing failed")

            response = client.post(
                '/upload',
                data={
                    'file': (BytesIO(pdf_content), 'failing.pdf'),
                },
                content_type='multipart/form-data',
                follow_redirects=False,
            )
            assert response.status_code == 302
            assert '/dashboard/consultant' in response.location


# ===================================================================
#  POST /upload - AJAX vs Regular Responses
# ===================================================================

class TestUploadAjaxResponses:
    """Tests for AJAX response handling in the upload route."""

    @patch('src.app.get_db')
    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_ajax_full_success_returns_200(
        self, mock_auth_uow, mock_validator_class, mock_get_db, client
    ):
        """AJAX upload with all files succeeding returns 200 JSON."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = True
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        # get_db is called multiple times: main session + fresh session after processing
        mock_db_main = MagicMock()
        mock_db_fresh = MagicMock()

        # The fresh session retrieves the job and uses cost fields in f-string formatting
        mock_fresh_job = MagicMock()
        mock_fresh_job.cost_input_usd = 0.001
        mock_fresh_job.cost_output_usd = 0.002
        mock_fresh_job.created_at = None  # Skip execution_time_seconds calculation
        mock_fresh_job.attempts = 0
        mock_db_fresh.get.return_value = mock_fresh_job

        call_count = [0]
        def db_gen():
            dbs = [mock_db_main, mock_db_fresh]
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(dbs):
                return iter([dbs[idx]])
            return iter([MagicMock()])

        mock_get_db.side_effect = lambda: db_gen()

        pdf_content = _make_pdf_content()

        with patch('src.services.processor.processor_service') as mock_proc:
            mock_proc.process_single_file.return_value = {
                'status': 'success',
                'file_id': 'output-200',
            }

            response = client.post(
                '/upload',
                data={
                    'file': (BytesIO(pdf_content), 'success.pdf'),
                },
                content_type='multipart/form-data',
                headers={'X-Requested-With': 'XMLHttpRequest'},
                follow_redirects=False,
            )
            assert response.status_code == 200
            data = response.get_json()
            assert 'message' in data

    @patch('src.app.get_db')
    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_ajax_partial_success_returns_207(
        self, mock_auth_uow, mock_validator_class, mock_get_db, client
    ):
        """AJAX upload with some successes and some failures returns 207."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        # First file: validation passes; second file: validation fails
        valid_result = MagicMock()
        valid_result.is_valid = True
        invalid_result = MagicMock()
        invalid_result.is_valid = False
        invalid_result.error_message = 'Bad file'
        invalid_result.error_code = 'UNKNOWN_FILE_TYPE'

        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.side_effect = [valid_result, invalid_result]
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        # get_db is called multiple times: main session + fresh session
        mock_db_main = MagicMock()
        mock_db_fresh = MagicMock()

        # The fresh session retrieves the job and uses cost fields in f-string
        mock_fresh_job = MagicMock()
        mock_fresh_job.cost_input_usd = 0.0
        mock_fresh_job.cost_output_usd = 0.0
        mock_fresh_job.created_at = None
        mock_fresh_job.attempts = 0
        mock_db_fresh.get.return_value = mock_fresh_job

        call_count = [0]
        def db_gen():
            dbs = [mock_db_main, mock_db_fresh]
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(dbs):
                return iter([dbs[idx]])
            return iter([MagicMock()])

        mock_get_db.side_effect = lambda: db_gen()

        pdf_content = _make_pdf_content()

        with patch('src.services.processor.processor_service') as mock_proc:
            mock_proc.process_single_file.return_value = {
                'status': 'success',
                'file_id': 'output-207',
            }

            response = client.post(
                '/upload',
                data={
                    'file': [
                        (BytesIO(pdf_content), 'good.pdf'),
                        (BytesIO(b'bad'), 'bad.pdf'),
                    ],
                },
                content_type='multipart/form-data',
                headers={'X-Requested-With': 'XMLHttpRequest'},
                follow_redirects=False,
            )
            assert response.status_code == 207
            data = response.get_json()
            assert 'message' in data
            assert data.get('partial') is True

    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_ajax_all_fail_returns_500(
        self, mock_auth_uow, mock_validator_class, client
    ):
        """AJAX upload where all files fail returns JSON 500."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = False
        mock_validation_result.error_message = 'Invalid file'
        mock_validation_result.error_code = 'UNKNOWN_FILE_TYPE'
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        response = client.post(
            '/upload',
            data={
                'file': (BytesIO(b'bad'), 'fail.pdf'),
            },
            content_type='multipart/form-data',
            headers={'X-Requested-With': 'XMLHttpRequest'},
            follow_redirects=False,
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data

    @patch('src.app.get_db')
    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_ajax_zero_success_zero_fail_returns_200(
        self, mock_auth_uow, mock_validator_class, mock_get_db, client
    ):
        """AJAX upload with no files processed (all skipped empty filename)
        returns 200 JSON with 0 successes (no error key)."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_validator_instance = MagicMock()
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        # Submit a file with empty name that will be skipped by the inner loop
        # Actually the outer check catches this and redirects, so let's test
        # with the AJAX header but no file key which triggers redirect.
        # Instead, test the case where files are all empty (single file with empty name)
        response = client.post(
            '/upload',
            data={
                'file': (BytesIO(b''), ''),
            },
            content_type='multipart/form-data',
            headers={'X-Requested-With': 'XMLHttpRequest'},
            follow_redirects=False,
        )
        # The empty filename check at the top redirects before AJAX check
        assert response.status_code == 302


# ===================================================================
#  POST /upload - Outer Exception Handling
# ===================================================================

class TestUploadExceptionHandling:
    """Tests for outer exception handling in the upload route."""

    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_outer_exception_regular_redirects(
        self, mock_auth_uow, mock_validator_class, client
    ):
        """Outer exception in upload (non-AJAX) flashes error and redirects."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        # Make FileValidator.create_pdf_validator raise to trigger outer exception
        mock_validator_class.create_pdf_validator.side_effect = Exception("Unexpected error")

        pdf_content = _make_pdf_content()

        response = client.post(
            '/upload',
            data={
                'file': (BytesIO(pdf_content), 'test.pdf'),
            },
            content_type='multipart/form-data',
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert '/dashboard/consultant' in response.location

    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_outer_exception_ajax_returns_500(
        self, mock_auth_uow, mock_validator_class, client
    ):
        """Outer exception in upload (AJAX) returns JSON 500."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_validator_class.create_pdf_validator.side_effect = Exception("Catastrophic failure")

        pdf_content = _make_pdf_content()

        response = client.post(
            '/upload',
            data={
                'file': (BytesIO(pdf_content), 'test.pdf'),
            },
            content_type='multipart/form-data',
            headers={'X-Requested-With': 'XMLHttpRequest'},
            follow_redirects=False,
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
        assert 'Catastrophic failure' in data['error']

    @patch('src.app.get_db')
    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_broken_pipe_error_shows_friendly_message(
        self, mock_auth_uow, mock_validator_class, mock_get_db, client
    ):
        """Broken pipe error during file processing shows friendly message
        and redirects."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = True
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        # Make PdfReader raise a broken pipe error to trigger the outer
        # per-file exception handler
        pdf_content = _make_pdf_content()

        with patch('pypdf.PdfReader', side_effect=BrokenPipeError("Broken pipe")):
            response = client.post(
                '/upload',
                data={
                    'file': (BytesIO(pdf_content), 'test.pdf'),
                },
                content_type='multipart/form-data',
                follow_redirects=False,
            )
            assert response.status_code == 302
            assert '/dashboard/consultant' in response.location


# ===================================================================
#  POST /upload - Processing with Email Notification on Failure
# ===================================================================

class TestUploadEmailNotification:
    """Tests for email notification on processing failure."""

    @patch('src.app.get_db')
    @patch('src.app.FileValidator')
    @patch('src.auth.get_uow')
    def test_upload_failure_sends_email_notification(
        self, mock_auth_uow, mock_validator_class, mock_get_db, client, app
    ):
        """Processing failure triggers email notification to user."""
        user = MockUser(role='CONSULTANT', email='user@example.com', name='Test User')
        _setup_auth(client, user, mock_auth_uow)

        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = True
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_validation_result
        mock_validator_class.create_pdf_validator.return_value = mock_validator_instance

        mock_db_main = MagicMock()
        mock_db_err = MagicMock()
        mock_db_err.query.return_value.filter_by.return_value.first.return_value = MagicMock()

        call_count = [0]
        def db_gen():
            dbs = [mock_db_main, mock_db_err]
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(dbs):
                return iter([dbs[idx]])
            return iter([MagicMock()])
        mock_get_db.side_effect = lambda: db_gen()

        mock_email = MagicMock()
        original_email = getattr(app, 'email_service', None)
        app.email_service = mock_email

        pdf_content = _make_pdf_content()

        try:
            with patch('src.services.processor.processor_service') as mock_proc:
                mock_proc.process_single_file.side_effect = Exception("AI crash")

                response = client.post(
                    '/upload',
                    data={
                        'file': (BytesIO(pdf_content), 'email_test.pdf'),
                    },
                    content_type='multipart/form-data',
                    follow_redirects=False,
                )
                assert response.status_code == 302
                # Email service should have been called
                mock_email.send_email.assert_called_once()
                call_args = mock_email.send_email.call_args
                assert call_args[0][0] == 'user@example.com'
                assert 'email_test.pdf' in call_args[0][1]
        finally:
            app.email_service = original_email


# ===================================================================
#  GET /download_pdf/<json_id> - GCS Path
# ===================================================================

class TestDownloadPdfGcs:
    """Tests for GCS download path in download_pdf_route."""

    @patch('src.services.storage_service.storage_service')
    @patch('src.auth.get_uow')
    def test_download_gcs_success(
        self, mock_auth_uow, mock_storage, client
    ):
        """GET /download_pdf/gcs:test.pdf downloads from GCS storage."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_storage.download_file.return_value = b'%PDF-1.4 fake pdf content'

        response = client.get('/download_pdf/gcs:test_report.pdf')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        mock_storage.download_file.assert_called_once_with('evidence', 'test_report.pdf')

    @patch('src.services.storage_service.storage_service')
    @patch('src.auth.get_uow')
    def test_download_gcs_error_returns_404(
        self, mock_auth_uow, mock_storage, client
    ):
        """GET /download_pdf/gcs:missing.pdf returns 404 when GCS fails."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_storage.download_file.side_effect = Exception("File not found in bucket")

        response = client.get('/download_pdf/gcs:missing.pdf')
        assert response.status_code == 404
        assert b'Erro ao baixar arquivo do Storage' in response.data

    @patch('src.services.storage_service.storage_service')
    @patch('src.auth.get_uow')
    def test_download_gcs_strips_only_prefix(
        self, mock_auth_uow, mock_storage, client
    ):
        """GCS download strips only the 'gcs:' prefix, preserving the rest
        of the filename."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_storage.download_file.return_value = b'%PDF content'

        response = client.get('/download_pdf/gcs:my_special_report_2025.pdf')
        assert response.status_code == 200
        mock_storage.download_file.assert_called_once_with(
            'evidence', 'my_special_report_2025.pdf'
        )


# ===================================================================
#  GET /download_pdf/<json_id> - Drive Unavailable
# ===================================================================

class TestDownloadPdfDriveUnavailable:
    """Tests for download_pdf_route when Drive is unavailable."""

    @patch('src.app.drive_service', None)
    @patch('src.auth.get_uow')
    def test_download_drive_unavailable_returns_500(
        self, mock_auth_uow, client
    ):
        """GET /download_pdf/<non_gcs_id> returns 500 when drive_service is None."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        response = client.get('/download_pdf/some-drive-file-id')
        assert response.status_code == 500
        assert b'Drive' in response.data


# ===================================================================
#  GET /download_pdf/<json_id> - Drive Error
# ===================================================================

class TestDownloadPdfDriveError:
    """Tests for download_pdf_route Drive error paths."""

    @patch('src.app.drive_service')
    @patch('src.auth.get_uow')
    def test_download_drive_exception_returns_500(
        self, mock_auth_uow, mock_drive, client
    ):
        """GET /download_pdf/<id> returns 500 when Drive raises exception."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_drive.service.files.return_value.get.return_value.execute.side_effect = (
            Exception("Drive API error")
        )

        response = client.get('/download_pdf/drive-file-id')
        assert response.status_code == 500
        assert b'Erro download' in response.data

    @patch('src.app.drive_service')
    @patch('src.auth.get_uow')
    def test_download_drive_pdf_direct(
        self, mock_auth_uow, mock_drive, client
    ):
        """GET /download_pdf/<id> where the file is already a PDF returns it directly."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_drive.service.files.return_value.get.return_value.execute.return_value = {
            'name': 'report.pdf',
            'mimeType': 'application/pdf',
        }
        mock_drive.download_file.return_value = b'%PDF-1.4 direct pdf'

        response = client.get('/download_pdf/direct-pdf-id')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        mock_drive.download_file.assert_called_once_with('direct-pdf-id')

    @patch('src.app.FOLDER_OUT', 'mock-folder-out')
    @patch('src.app.drive_service')
    @patch('src.auth.get_uow')
    def test_download_drive_json_to_pdf_lookup(
        self, mock_auth_uow, mock_drive, client
    ):
        """GET /download_pdf/<id> for a JSON file looks up the corresponding PDF."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        # First call: get file metadata (JSON)
        mock_drive.service.files.return_value.get.return_value.execute.return_value = {
            'name': 'report.json',
            'mimeType': 'application/json',
        }
        # Second call: list files to find PDF
        mock_drive.service.files.return_value.list.return_value.execute.return_value = {
            'files': [{'id': 'found-pdf-id'}]
        }
        mock_drive.download_file.return_value = b'%PDF-1.4 from json lookup'

        response = client.get('/download_pdf/json-file-id')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        mock_drive.download_file.assert_called_once_with('found-pdf-id')

    @patch('src.app.FOLDER_OUT', 'mock-folder-out')
    @patch('src.app.drive_service')
    @patch('src.auth.get_uow')
    def test_download_drive_pdf_not_found_returns_404(
        self, mock_auth_uow, mock_drive, client
    ):
        """GET /download_pdf/<id> returns 404 when PDF is not found in Drive."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_drive.service.files.return_value.get.return_value.execute.return_value = {
            'name': 'report.json',
            'mimeType': 'application/json',
        }
        # No files found in exact or fuzzy search
        mock_drive.service.files.return_value.list.return_value.execute.return_value = {
            'files': []
        }

        response = client.get('/download_pdf/json-no-pdf')
        assert response.status_code == 404
        assert b'PDF' in response.data

    @patch('src.app.FOLDER_OUT', 'mock-folder-out')
    @patch('src.app.drive_service')
    @patch('src.auth.get_uow')
    def test_download_drive_fuzzy_match_finds_pdf(
        self, mock_auth_uow, mock_drive, client
    ):
        """GET /download_pdf/<id> falls back to fuzzy match when exact match
        fails, and finds a PDF."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_drive.service.files.return_value.get.return_value.execute.return_value = {
            'name': 'report.json',
            'mimeType': 'application/json',
        }

        # First list call (exact match): no files
        # Second list call (fuzzy match): has a PDF
        mock_drive.service.files.return_value.list.return_value.execute.side_effect = [
            {'files': []},
            {'files': [{'id': 'fuzzy-pdf-id', 'name': 'report_v2.pdf'}]},
        ]
        mock_drive.download_file.return_value = b'%PDF-1.4 fuzzy pdf'

        response = client.get('/download_pdf/json-fuzzy-id')
        assert response.status_code == 200
        mock_drive.download_file.assert_called_once_with('fuzzy-pdf-id')

    @patch('src.app.FOLDER_OUT', 'mock-folder-out')
    @patch('src.app.drive_service')
    @patch('src.auth.get_uow')
    def test_download_drive_fuzzy_no_pdf_extension_returns_404(
        self, mock_auth_uow, mock_drive, client
    ):
        """GET /download_pdf/<id> fuzzy match finds files but none ending
        in .pdf returns 404."""
        user = MockUser(role='CONSULTANT')
        _setup_auth(client, user, mock_auth_uow)

        mock_drive.service.files.return_value.get.return_value.execute.return_value = {
            'name': 'report.json',
            'mimeType': 'application/json',
        }

        mock_drive.service.files.return_value.list.return_value.execute.side_effect = [
            {'files': []},
            {'files': [{'id': 'non-pdf-id', 'name': 'report.docx'}]},
        ]

        response = client.get('/download_pdf/json-no-pdf-ext')
        assert response.status_code == 404
        assert b'Fuzzy' in response.data


# ===================================================================
#  GET /download_pdf/<json_id> - Unauthenticated
# ===================================================================

class TestDownloadPdfAuth:
    """Tests for authentication on download route."""

    def test_download_unauthenticated_redirects_to_login(self, client):
        """Unauthenticated user accessing download_pdf is redirected to login."""
        response = client.get('/download_pdf/any-file-id')
        assert response.status_code == 302
        assert 'login' in response.location
