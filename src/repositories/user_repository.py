"""Repository for User entities."""
from typing import Optional, List
import uuid

from sqlalchemy.orm import joinedload

from src.models_db import User, UserRole


class UserRepository:
    def __init__(self, session):
        self._session = session

    def get_by_id(self, id: uuid.UUID) -> Optional[User]:
        return self._session.query(User).get(id)

    def get_by_email(self, email: str) -> Optional[User]:
        return self._session.query(User).filter_by(email=email).first()

    def get_consultants_for_company(self, company_id: uuid.UUID) -> List[User]:
        return self._session.query(User).filter(
            User.company_id == company_id,
            User.role == UserRole.CONSULTANT,
            User.is_active == True,
        ).all()

    def get_managers_with_company(self) -> List[User]:
        """Get all managers with their company relationship loaded."""
        return self._session.query(User).filter(
            User.role == UserRole.MANAGER,
        ).options(joinedload(User.company)).all()

    def get_all_by_company(self, company_id: uuid.UUID) -> List[User]:
        return self._session.query(User).filter(
            User.company_id == company_id,
        ).all()

    def add(self, user: User) -> User:
        self._session.add(user)
        return user

    def delete(self, user: User) -> None:
        self._session.delete(user)
