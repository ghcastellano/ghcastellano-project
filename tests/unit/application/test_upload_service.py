"""Tests for UploadService."""
import pytest
import uuid
from unittest.mock import MagicMock

from src.application.upload_service import UploadService, UploadResult
from src.repositories.unit_of_work import UnitOfWork
from src.models_db import InspectionStatus, JobStatus


class TestUploadService:

    @pytest.fixture
    def upload_env(self, db_session, establishment_factory):
        est = establishment_factory.create(db_session)
        uow = UnitOfWork(db_session)

        mock_processor = MagicMock()
        mock_processor.process_single_file.return_value = {
            'status': 'success',
            'file_id': 'mock-out-id',
        }

        mock_validator = MagicMock()
        valid_result = MagicMock()
        valid_result.is_valid = True
        mock_validator.validate.return_value = valid_result

        svc = UploadService(uow, mock_processor, mock_validator)

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.company_id = est.company_id
        mock_user.establishments = [est]

        return {
            'service': svc,
            'uow': uow,
            'establishment': est,
            'processor': mock_processor,
            'validator': mock_validator,
            'user': mock_user,
        }

    def test_successful_upload(self, upload_env):
        svc = upload_env['service']
        est = upload_env['establishment']

        result = svc.process_upload(
            file_content=b'%PDF-1.4 test content',
            filename='test.pdf',
            establishment_id=est.id,
            user=upload_env['user'],
            company_id=est.company_id,
        )

        assert result.success is True
        assert result.file_id is not None
        assert result.job_id is not None
        upload_env['processor'].process_single_file.assert_called_once()

    def test_validation_failure(self, upload_env):
        invalid_result = MagicMock()
        invalid_result.is_valid = False
        invalid_result.error_message = 'Tipo de arquivo inválido'
        upload_env['validator'].validate.return_value = invalid_result

        svc = upload_env['service']
        result = svc.process_upload(
            file_content=b'not-a-pdf',
            filename='test.exe',
            establishment_id=upload_env['establishment'].id,
            user=upload_env['user'],
        )

        assert result.success is False
        assert result.error == 'VALIDATION_FAILED'

    def test_duplicate_detection(self, upload_env):
        upload_env['processor'].process_single_file.return_value = {
            'status': 'skipped',
            'reason': 'duplicate',
        }

        svc = upload_env['service']
        result = svc.process_upload(
            file_content=b'%PDF-1.4 dup',
            filename='dup.pdf',
            establishment_id=upload_env['establishment'].id,
            user=upload_env['user'],
            company_id=upload_env['establishment'].company_id,
        )

        assert result.success is True
        assert result.skipped is True

    def test_processing_error(self, upload_env):
        upload_env['processor'].process_single_file.side_effect = Exception('AI error')

        svc = upload_env['service']
        result = svc.process_upload(
            file_content=b'%PDF-1.4 error',
            filename='error.pdf',
            establishment_id=upload_env['establishment'].id,
            user=upload_env['user'],
            company_id=upload_env['establishment'].company_id,
        )

        assert result.success is False
        assert 'AI error' in result.error

    def test_smart_match_establishment_by_name(self, upload_env):
        est = upload_env['establishment']
        svc = upload_env['service']

        matched = svc.smart_match_establishment(
            f'Relatório de {est.name.upper()} - Inspeção Sanitária',
            [est],
        )

        assert matched is not None
        assert matched.id == est.id

    def test_smart_match_no_match(self, upload_env):
        est = upload_env['establishment']
        svc = upload_env['service']

        matched = svc.smart_match_establishment(
            'Relatório genérico sem nome de estabelecimento',
            [est],
        )

        assert matched is None

    def test_smart_match_longest_first(self, upload_env):
        """Longest name should match first (most specific)."""
        est1 = MagicMock()
        est1.name = 'Restaurante'
        est1.id = uuid.uuid4()

        est2 = MagicMock()
        est2.name = 'Restaurante Silva'
        est2.id = uuid.uuid4()

        svc = upload_env['service']
        matched = svc.smart_match_establishment(
            'Inspeção do RESTAURANTE SILVA - Janeiro 2025',
            [est1, est2],
        )

        assert matched is not None
        assert matched.id == est2.id
