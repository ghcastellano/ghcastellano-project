"""Tests for ActionPlanRepository."""
import pytest
import uuid

from src.repositories.action_plan_repository import ActionPlanRepository
from src.models_db import ActionPlan, ActionPlanItem, ActionPlanItemStatus, SeverityLevel


class TestActionPlanRepository:

    def test_get_by_id(self, db_session, action_plan_factory):
        plan = action_plan_factory.create(db_session)
        repo = ActionPlanRepository(db_session)

        result = repo.get_by_id(plan.id)
        assert result is not None
        assert result.id == plan.id

    def test_get_by_id_not_found(self, db_session):
        repo = ActionPlanRepository(db_session)
        assert repo.get_by_id(uuid.uuid4()) is None

    def test_get_by_inspection_id(self, db_session, inspection_factory, action_plan_factory):
        inspection = inspection_factory.create(db_session)
        plan = action_plan_factory.create(db_session, inspection=inspection)
        repo = ActionPlanRepository(db_session)

        result = repo.get_by_inspection_id(inspection.id)
        assert result is not None
        assert result.id == plan.id

    def test_get_by_inspection_id_not_found(self, db_session):
        repo = ActionPlanRepository(db_session)
        assert repo.get_by_inspection_id(uuid.uuid4()) is None

    def test_get_with_items(self, db_session, action_plan_factory, action_plan_item_factory):
        plan = action_plan_factory.create(db_session)
        item1 = action_plan_item_factory.create(db_session, action_plan=plan, order_index=0)
        item2 = action_plan_item_factory.create(db_session, action_plan=plan, order_index=1)
        repo = ActionPlanRepository(db_session)

        result = repo.get_with_items(plan.id)
        assert result is not None
        assert len(result.items) == 2

    def test_get_item_by_id(self, db_session, action_plan_item_factory):
        item = action_plan_item_factory.create(db_session)
        repo = ActionPlanRepository(db_session)

        result = repo.get_item_by_id(item.id)
        assert result is not None
        assert result.id == item.id

    def test_get_items_by_plan_id_ordered(self, db_session, action_plan_factory, action_plan_item_factory):
        plan = action_plan_factory.create(db_session)
        item_b = action_plan_item_factory.create(db_session, action_plan=plan, order_index=1, problem_description='B')
        item_a = action_plan_item_factory.create(db_session, action_plan=plan, order_index=0, problem_description='A')
        repo = ActionPlanRepository(db_session)

        results = repo.get_items_by_plan_id(plan.id)
        assert len(results) == 2
        assert results[0].order_index == 0
        assert results[1].order_index == 1

    def test_delete_items_for_plan(self, db_session, action_plan_factory, action_plan_item_factory):
        plan = action_plan_factory.create(db_session)
        action_plan_item_factory.create(db_session, action_plan=plan, order_index=0)
        action_plan_item_factory.create(db_session, action_plan=plan, order_index=1)
        repo = ActionPlanRepository(db_session)

        count = repo.delete_items_for_plan(plan.id)
        db_session.flush()

        assert count == 2
        assert len(repo.get_items_by_plan_id(plan.id)) == 0

    def test_add_plan(self, db_session, inspection_factory):
        inspection = inspection_factory.create(db_session)
        repo = ActionPlanRepository(db_session)

        plan = ActionPlan(
            id=uuid.uuid4(),
            inspection_id=inspection.id,
            summary_text='Test summary',
        )
        result = repo.add(plan)
        db_session.flush()

        assert repo.get_by_id(plan.id) is not None

    def test_add_item(self, db_session, action_plan_factory):
        plan = action_plan_factory.create(db_session)
        repo = ActionPlanRepository(db_session)

        item = ActionPlanItem(
            id=uuid.uuid4(),
            action_plan_id=plan.id,
            problem_description='New problem',
            corrective_action='Fix it',
            severity=SeverityLevel.HIGH,
            status=ActionPlanItemStatus.OPEN,
            order_index=0,
        )
        result = repo.add_item(item)
        db_session.flush()

        assert repo.get_item_by_id(item.id) is not None

    def test_delete_plan(self, db_session, action_plan_factory):
        plan = action_plan_factory.create(db_session)
        repo = ActionPlanRepository(db_session)

        repo.delete(plan)
        db_session.flush()

        assert repo.get_by_id(plan.id) is None
