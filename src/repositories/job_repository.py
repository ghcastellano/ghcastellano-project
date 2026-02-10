"""Repository for Job entities."""
from typing import Optional, List
import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from src.models_db import Job, JobStatus


class JobRepository:
    def __init__(self, session):
        self._session = session

    def get_by_id(self, id: uuid.UUID) -> Optional[Job]:
        return self._session.query(Job).get(id)

    def get_pending_for_company(
        self,
        company_id: uuid.UUID = None,
        establishment_ids: List[uuid.UUID] = None,
        allow_all: bool = False,
        limit: int = 20,
    ) -> List[Job]:
        """Get pending/processing jobs, filtered by company or establishments."""
        cutoff = datetime.utcnow() - timedelta(minutes=30)

        query = self._session.query(Job).filter(
            Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]),
            Job.created_at >= cutoff,
        )

        if not allow_all and not company_id and not establishment_ids:
            return []

        filters = []
        if company_id:
            filters.append(Job.company_id == company_id)
        if establishment_ids:
            ids_str = [str(uid) for uid in establishment_ids if uid]
            if ids_str:
                filters.append(Job.input_payload['establishment_id'].astext.in_(ids_str))
        if filters:
            query = query.filter(or_(*filters))

        return query.order_by(Job.created_at.desc()).limit(limit).all()

    def get_for_monitor(self, limit: int = 50) -> List[Job]:
        """Get recent jobs for admin monitoring."""
        return self._session.query(Job).options(
            joinedload(Job.company),
        ).order_by(Job.created_at.desc()).limit(limit).all()

    def get_failed_recent(
        self,
        company_id: uuid.UUID = None,
        minutes: int = 60,
        limit: int = 10,
    ) -> List[Job]:
        """Get recently failed jobs."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)

        query = self._session.query(Job).filter(
            Job.status == JobStatus.FAILED,
            Job.created_at >= cutoff,
        )
        if company_id:
            query = query.filter(Job.company_id == company_id)

        return query.order_by(Job.created_at.desc()).limit(limit).all()

    def get_job_info_map(self, file_ids: List[str]) -> dict:
        """Return {file_id: {filename, uploaded_by_name}} for a list of drive_file_ids."""
        if not file_ids:
            return {}
        from sqlalchemy import cast, String
        file_ids_set = set(file_ids)
        jobs = self._session.query(Job).filter(
            cast(Job.input_payload, String).like('%file_id%'),
        ).all()
        result = {}
        for job in jobs:
            payload = job.input_payload or {}
            fid = payload.get('file_id')
            if fid and fid in file_ids_set:
                result[fid] = {
                    'filename': payload.get('filename', ''),
                    'uploaded_by_name': payload.get('uploaded_by_name', ''),
                }
        return result

    def add(self, job: Job) -> Job:
        self._session.add(job)
        return job

    def delete(self, job: Job) -> None:
        self._session.delete(job)
