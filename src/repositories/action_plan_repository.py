"""Repository for ActionPlan and ActionPlanItem entities."""
from typing import Optional, List
import uuid

from sqlalchemy.orm import joinedload

from src.models_db import ActionPlan, ActionPlanItem


class ActionPlanRepository:
    def __init__(self, session):
        self._session = session

    def get_by_id(self, id: uuid.UUID) -> Optional[ActionPlan]:
        return self._session.query(ActionPlan).get(id)

    def get_by_inspection_id(self, inspection_id: uuid.UUID) -> Optional[ActionPlan]:
        return self._session.query(ActionPlan).filter_by(
            inspection_id=inspection_id,
        ).first()

    def get_with_items(self, plan_id: uuid.UUID) -> Optional[ActionPlan]:
        """Load plan with items eagerly."""
        return self._session.query(ActionPlan).options(
            joinedload(ActionPlan.items),
        ).filter_by(id=plan_id).first()

    def get_item_by_id(self, item_id: uuid.UUID) -> Optional[ActionPlanItem]:
        return self._session.query(ActionPlanItem).get(item_id)

    def get_items_by_plan_id(self, plan_id: uuid.UUID) -> List[ActionPlanItem]:
        return self._session.query(ActionPlanItem).filter_by(
            action_plan_id=plan_id,
        ).order_by(ActionPlanItem.order_index).all()

    def delete_items_for_plan(self, plan_id: uuid.UUID) -> int:
        """Delete all items for a plan. Returns count deleted."""
        return self._session.query(ActionPlanItem).filter_by(
            action_plan_id=plan_id,
        ).delete()

    def add(self, plan: ActionPlan) -> ActionPlan:
        self._session.add(plan)
        return plan

    def add_item(self, item: ActionPlanItem) -> ActionPlanItem:
        self._session.add(item)
        return item

    def delete(self, plan: ActionPlan) -> None:
        self._session.delete(plan)
