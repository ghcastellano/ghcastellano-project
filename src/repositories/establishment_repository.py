"""Repository for Establishment entities."""
from typing import Optional, List
import uuid

from src.models_db import Establishment


class EstablishmentRepository:
    def __init__(self, session):
        self._session = session

    def get_by_id(self, id: uuid.UUID) -> Optional[Establishment]:
        return self._session.query(Establishment).get(id)

    def get_by_company(self, company_id: uuid.UUID) -> List[Establishment]:
        return self._session.query(Establishment).filter(
            Establishment.company_id == company_id,
        ).all()

    def get_by_name_and_company(self, name: str, company_id: uuid.UUID) -> Optional[Establishment]:
        return self._session.query(Establishment).filter(
            Establishment.name == name,
            Establishment.company_id == company_id,
        ).first()

    def add(self, establishment: Establishment) -> Establishment:
        self._session.add(establishment)
        return establishment

    def delete(self, establishment: Establishment) -> None:
        self._session.delete(establishment)
