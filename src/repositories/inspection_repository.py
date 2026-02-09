"""Repository for Inspection entities."""
from typing import Optional, List
import uuid

from sqlalchemy.orm import joinedload

from src.models_db import (
    Inspection, InspectionStatus, ActionPlan, ActionPlanItem,
    Establishment, Company,
)


class InspectionRepository:
    def __init__(self, session):
        self._session = session

    def get_by_id(self, id: uuid.UUID) -> Optional[Inspection]:
        return self._session.query(Inspection).get(id)

    def get_by_drive_file_id(self, file_id: str) -> Optional[Inspection]:
        return self._session.query(Inspection).filter_by(
            drive_file_id=file_id
        ).first()

    def get_with_plan_by_file_id(self, file_id: str) -> Optional[Inspection]:
        """Load inspection with action plan and items eagerly."""
        return self._session.query(Inspection).options(
            joinedload(Inspection.action_plan).joinedload(ActionPlan.items),
            joinedload(Inspection.establishment),
        ).filter(Inspection.drive_file_id == file_id).first()

    def get_by_file_hash(self, file_hash: str, exclude_statuses: List[InspectionStatus] = None) -> Optional[Inspection]:
        """Find inspection by file hash, optionally excluding certain statuses."""
        query = self._session.query(Inspection).filter_by(file_hash=file_hash)
        if exclude_statuses:
            query = query.filter(~Inspection.status.in_(exclude_statuses))
        return query.first()

    def get_for_consultant(
        self,
        establishment_ids: List[uuid.UUID] = None,
        company_id: uuid.UUID = None,
        statuses: List[InspectionStatus] = None,
        limit: int = 50,
    ) -> List[Inspection]:
        """Get inspections visible to a consultant."""
        if statuses is None:
            statuses = [
                InspectionStatus.APPROVED,
                InspectionStatus.PENDING_CONSULTANT_VERIFICATION,
                InspectionStatus.COMPLETED,
                InspectionStatus.PENDING_MANAGER_REVIEW,
            ]

        query = self._session.query(Inspection).options(
            joinedload(Inspection.establishment),
        ).filter(Inspection.status.in_(statuses))

        if establishment_ids:
            query = query.filter(Inspection.establishment_id.in_(establishment_ids))
        elif company_id:
            query = query.join(Inspection.establishment).filter(
                Establishment.company_id == company_id
            )

        return query.order_by(Inspection.created_at.desc()).limit(limit).all()

    def get_for_manager(
        self,
        company_id: uuid.UUID = None,
        establishment_id: uuid.UUID = None,
        statuses: List[InspectionStatus] = None,
        limit: int = 50,
    ) -> List[Inspection]:
        """Get inspections visible to a manager."""
        if statuses is None:
            statuses = [
                InspectionStatus.PENDING_MANAGER_REVIEW,
                InspectionStatus.APPROVED,
                InspectionStatus.PENDING_CONSULTANT_VERIFICATION,
                InspectionStatus.COMPLETED,
            ]

        query = self._session.query(Inspection).options(
            joinedload(Inspection.establishment),
            joinedload(Inspection.action_plan),
        ).filter(Inspection.status.in_(statuses))

        if establishment_id:
            query = query.filter(Inspection.establishment_id == establishment_id)
        elif company_id:
            query = query.join(Inspection.establishment).filter(
                Establishment.company_id == company_id
            )

        return query.order_by(Inspection.created_at.desc()).limit(limit).all()

    def get_pending(
        self,
        company_id: uuid.UUID = None,
        establishment_ids: List[uuid.UUID] = None,
        limit: int = 10,
    ) -> List[Inspection]:
        """Get pending-review inspections."""
        from sqlalchemy import or_

        query = self._session.query(Inspection).filter(
            Inspection.status.in_([InspectionStatus.PENDING_MANAGER_REVIEW])
        )

        conditions = []
        if establishment_ids:
            conditions.append(Inspection.establishment_id.in_(establishment_ids))
        if company_id:
            query = query.outerjoin(Inspection.establishment)
            conditions.append(Establishment.company_id == company_id)
        if conditions:
            query = query.filter(or_(*conditions))

        return query.order_by(Inspection.created_at.desc()).limit(limit).all()

    def get_processing(self, limit: int = 10) -> List[Inspection]:
        """Get inspections currently being processed."""
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(hours=2)

        return self._session.query(Inspection).options(
            joinedload(Inspection.establishment),
        ).filter(
            Inspection.status == InspectionStatus.PROCESSING,
            Inspection.created_at >= cutoff,
        ).order_by(Inspection.created_at.desc()).limit(limit).all()

    def get_batch_by_file_ids(self, file_ids: List[str]) -> List[Inspection]:
        """Get multiple inspections by drive_file_id list."""
        if not file_ids:
            return []
        return self._session.query(Inspection).options(
            joinedload(Inspection.establishment),
            joinedload(Inspection.action_plan),
        ).filter(Inspection.drive_file_id.in_(file_ids)).all()

    def add(self, inspection: Inspection) -> Inspection:
        self._session.add(inspection)
        return inspection

    def delete(self, inspection: Inspection) -> None:
        self._session.delete(inspection)
