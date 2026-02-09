"""Service for handling file uploads and processing."""
import os
import uuid
import tempfile
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from src.models_db import Inspection, InspectionStatus, Job, JobStatus


@dataclass
class UploadResult:
    """Result of a file upload operation."""
    success: bool
    message: str
    file_id: Optional[str] = None
    job_id: Optional[str] = None
    establishment_name: Optional[str] = None
    skipped: bool = False
    error: Optional[str] = None


class UploadService:
    """Handles file upload validation, smart matching, and processing."""

    def __init__(self, uow, processor, file_validator=None):
        self._uow = uow
        self._processor = processor
        self._validator = file_validator

    def process_upload(self, file_content, filename, establishment_id, user,
                       company_id=None):
        """
        Process a single file upload.

        Args:
            file_content: Raw bytes of the uploaded file.
            filename: Original filename.
            establishment_id: Target establishment UUID (string or UUID).
            user: Current user object.
            company_id: Company ID for job tracking.

        Returns:
            UploadResult with success/error details.
        """
        # 1. Validate file
        if self._validator:
            validation = self._validator.validate(file_content, filename)
            if not validation.is_valid:
                return UploadResult(
                    success=False,
                    message=validation.error_message or 'Arquivo inválido.',
                    error='VALIDATION_FAILED',
                )

        # 2. Resolve establishment
        est_id = str(establishment_id) if establishment_id else None
        est_name = None
        job_company_id = company_id

        if est_id:
            est = self._uow.establishments.get_by_id(uuid.UUID(est_id))
            if est:
                est_name = est.name
                if est.company_id and not job_company_id:
                    job_company_id = est.company_id

        # 3. Create inspection record
        upload_id = f'upload:{uuid.uuid4()}'
        new_insp = Inspection(
            drive_file_id=upload_id,
            status=InspectionStatus.PROCESSING,
            establishment_id=uuid.UUID(est_id) if est_id else None,
        )
        self._uow.inspections.add(new_insp)
        self._uow.flush()

        # 4. Create job
        job = Job(
            company_id=job_company_id,
            type='PROCESS_REPORT',
            status=JobStatus.PROCESSING,
            input_payload={
                'file_id': upload_id,
                'filename': filename,
                'establishment_id': est_id,
                'establishment_name': est_name,
            },
        )
        self._uow.jobs.add(job)
        self._uow.flush()
        job_id = job.id
        self._uow.commit()

        # 5. Process file
        try:
            file_meta = {'id': upload_id, 'name': filename}
            result = self._processor.process_single_file(
                file_meta,
                company_id=job_company_id,
                establishment_id=uuid.UUID(est_id) if est_id else None,
                job_id=job_id,
                file_content=file_content,
            )

            # Check for duplicates
            if result.get('status') == 'skipped' and result.get('reason') == 'duplicate':
                # Clean up orphan inspection
                orphan = self._uow.inspections.get_by_drive_file_id(upload_id)
                if orphan:
                    self._uow.inspections.delete(orphan)
                # Mark job as skipped
                job_record = self._uow.jobs.get_by_id(job_id)
                if job_record:
                    job_record.status = JobStatus.SKIPPED
                self._uow.commit()

                return UploadResult(
                    success=True,
                    message='Arquivo duplicado detectado.',
                    skipped=True,
                    file_id=upload_id,
                )

            # Mark job as completed
            job_record = self._uow.jobs.get_by_id(job_id)
            if job_record:
                job_record.status = JobStatus.COMPLETED
                job_record.finished_at = datetime.utcnow()
                job_record.attempts += 1
            self._uow.commit()

            return UploadResult(
                success=True,
                message='Arquivo processado com sucesso!',
                file_id=upload_id,
                job_id=str(job_id),
                establishment_name=est_name,
            )

        except Exception as e:
            # Update job to failed
            try:
                job_record = self._uow.jobs.get_by_id(job_id)
                if job_record:
                    job_record.status = JobStatus.FAILED
                    job_record.error_log = str(e)
                    job_record.finished_at = datetime.utcnow()

                # Delete orphan inspection
                orphan = self._uow.inspections.get_by_drive_file_id(upload_id)
                if orphan:
                    self._uow.inspections.delete(orphan)

                self._uow.commit()
            except Exception:
                self._uow.rollback()

            return UploadResult(
                success=False,
                message=f'Erro ao processar arquivo: {e}',
                error=str(e),
            )

    def smart_match_establishment(self, pdf_text, user_establishments):
        """
        Match establishment by checking if name appears in PDF text.

        Args:
            pdf_text: Extracted text from PDF (first 2 pages).
            user_establishments: List of establishments the user has access to.

        Returns:
            Matched Establishment or None.
        """
        if not pdf_text or not user_establishments:
            return None

        normalized_text = pdf_text.upper()

        # Sort by name length (longest first = most specific match)
        sorted_ests = sorted(
            user_establishments,
            key=lambda x: len(x.name),
            reverse=True,
        )

        for est in sorted_ests:
            if est.name.strip().upper() in normalized_text:
                return est

        return None
