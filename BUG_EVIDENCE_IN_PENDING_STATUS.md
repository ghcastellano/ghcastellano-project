# Bug: Evidence Images Showing in PENDING_CONSULTANT_VERIFICATION Status

## Problem Description

An inspection in status `PENDING_CONSULTANT_VERIFICATION` (awaiting consultant field visit) has items with:
- `evidence_image_url` populated
- `current_status: "Corrigido"`
- `status: RESOLVED`

This is incorrect because:
- Evidence should only be collected **during** the consultant's visit
- Items should only be marked as "Corrigido" **after** the consultant verifies the correction in person
- The inspection status should transition to `COMPLETED` **after** the consultant finishes the verification

## Root Cause

The inspection `upload:fd6a2a5c-645e-4a05-808f-453f6e542b3e` (Loja 1) shows:
- Status: `PENDING_CONSULTANT_VERIFICATION`
- Approved by: Gustavo Henrique Castellano (Manager)
- Approved at: 2026-02-14 15:12:29
- Has 1 item with evidence uploaded

The bug occurs because the `/api/save_review` endpoint allows:
1. Consultants to upload evidence
2. Mark items as resolved
3. **WITHOUT** transitioning the inspection status to `COMPLETED`

## Investigation

### Current Workflow
1. Manager approves plan → Status becomes `APPROVED`
2. Consultant starts verification → Status becomes `PENDING_CONSULTANT_VERIFICATION`
3. Consultant saves evidence → Evidence is saved but status **stays** `PENDING_CONSULTANT_VERIFICATION`
4. Consultant must explicitly mark inspection as complete → Status becomes `COMPLETED`

### The Issue
If the consultant:
- Uploads evidence
- Marks item as "Corrigido"
- But **doesn't** finish/submit the review

Then the inspection remains in `PENDING_CONSULTANT_VERIFICATION` with evidence visible.

## Expected Behavior

Evidence should **ONLY** be visible when:
- Inspection status is `COMPLETED` OR
- The current user is the consultant who's actively working on it

## Solution Options

### Option 1: Hide Evidence in Templates (Quick Fix)
Modify `review.html` and `pdf_template.html` to hide evidence if inspection status is not `COMPLETED`:

```html
{% if inspection.status == 'COMPLETED' and item.evidence_image_url %}
    <!-- Show evidence -->
{% endif %}
```

### Option 2: Prevent Evidence Save Until Completion (Strict)
Modify `/api/save_review` endpoint to reject evidence uploads if inspection is not ready for completion.

### Option 3: Auto-transition to COMPLETED (Recommended)
When consultant saves evidence for the first time, automatically transition the inspection to `COMPLETED`.

Code location: `src/app.py`, line ~1249 (`/api/save_review`)

## Recommended Fix

**AUTO-TRANSITION TO COMPLETED**

In `/api/save_review` endpoint, after saving evidence:
```python
# If consultant is adding evidence, transition to COMPLETED
if any(item.get('evidence_file') for item in data.get('items', [])):
    inspection.status = InspectionStatus.COMPLETED
    inspection.updated_at = datetime.now(timezone.utc)
```

This ensures:
- Evidence is only visible on completed inspections
- Status accurately reflects the consultant's work
- No orphaned "pending" inspections with evidence

## Data Cleanup

To fix existing data:
```python
from src.app import app
from src.database import get_db
from src.models_db import Inspection, InspectionStatus

with app.app_context():
    session = next(get_db())

    # Find inspections with evidence but still pending
    inspections = session.query(Inspection).filter(
        Inspection.status == InspectionStatus.PENDING_CONSULTANT_VERIFICATION
    ).all()

    for insp in inspections:
        if insp.action_plan:
            has_evidence = any(
                item.evidence_image_url for item in insp.action_plan.items
            )
            if has_evidence:
                print(f'Fixing {insp.drive_file_id}')
                insp.status = InspectionStatus.COMPLETED

    session.commit()
```

## Status

- [x] Bug identified
- [x] Root cause analyzed
- [ ] Fix implemented
- [ ] Data cleaned up
- [ ] Tests added
