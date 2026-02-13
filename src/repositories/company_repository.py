"""Repository for Company entities."""
from typing import Optional, List
import uuid

from src.models_db import Company


class CompanyRepository:
    def __init__(self, session):
        self._session = session

    def get_by_id(self, id: uuid.UUID) -> Optional[Company]:
        return self._session.query(Company).get(id)

    def get_by_cnpj(self, cnpj: str) -> Optional[Company]:
        return self._session.query(Company).filter_by(cnpj=cnpj).first()

    def get_all(self) -> List[Company]:
        return self._session.query(Company).all()

    def add(self, company: Company) -> Company:
        self._session.add(company)
        return company

    def delete(self, company: Company) -> None:
        self._session.delete(company)
