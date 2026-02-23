from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import (
    CourseMemberRepository,
    CourseOfferingRepository,
    CourseStudentMembershipRepository,
    UserRepository,
)
from .identity_service import normalize_text


def _is_student_member_active(member: Any) -> bool:
    return (
        normalize_text(getattr(member, "role", "")).lower() == "student"
        and normalize_text(getattr(member, "status", "")).lower() == "active"
    )


def _student_keys(student_row: Any, fallback: str = "") -> list[str]:
    values = [
        normalize_text(getattr(student_row, "student_id", "")),
        normalize_text(getattr(student_row, "username", "")),
        normalize_text(fallback),
    ]
    keys: list[str] = []
    for item in values:
        if item and item not in keys:
            keys.append(item)
    return keys


def _is_active_offering(offering: Any) -> bool:
    return normalize_text(getattr(offering, "status", "")).lower() == "active"


async def reconcile_membership_consistency(
    db: AsyncSession,
    *,
    course_id: str = "",
    target_student_ids: Sequence[str] | None = None,
) -> dict[str, int]:
    normalized_course_id = normalize_text(course_id)
    normalized_targets = {
        normalize_text(item)
        for item in (target_student_ids or [])
        if normalize_text(item)
    }

    now = datetime.now()
    user_repo = UserRepository(db)
    offering_repo = CourseOfferingRepository(db)
    member_repo = CourseMemberRepository(db)
    membership_repo = CourseStudentMembershipRepository(db)

    student_rows = await user_repo.list_by_role("student")
    student_by_key: dict[str, Any] = {}
    for row in student_rows:
        candidate_keys = _student_keys(row)
        if normalized_targets and not any(key in normalized_targets for key in candidate_keys):
            continue
        for key in candidate_keys:
            student_by_key[key] = row

    if normalized_course_id:
        offering_rows = await offering_repo.list_by_template_course(normalized_course_id)
    else:
        offering_rows = await offering_repo.list_all()
    active_offerings = [
        item
        for item in offering_rows
        if _is_active_offering(item) and normalize_text(item.class_name) and normalize_text(item.template_course_id)
    ]

    offerings_by_course_class: dict[tuple[str, str], list[Any]] = {}
    for offering in active_offerings:
        key = (normalize_text(offering.template_course_id), normalize_text(offering.class_name))
        offerings_by_course_class.setdefault(key, []).append(offering)

    members_by_offering: dict[str, list[Any]] = {}
    for offering in active_offerings:
        offering_id = normalize_text(offering.id)
        if not offering_id:
            continue
        members_by_offering[offering_id] = list(await member_repo.list_by_offering(offering_id))

    course_ids = {normalize_text(item.template_course_id) for item in active_offerings if normalize_text(item.template_course_id)}
    if normalized_course_id:
        course_ids.add(normalized_course_id)

    course_memberships = []
    for item_course_id in sorted(course_ids):
        course_memberships.extend(await membership_repo.list_by_course(item_course_id))

    membership_by_course_student: dict[tuple[str, str], Any] = {}
    for membership in course_memberships:
        key = (normalize_text(membership.course_id), normalize_text(membership.student_id))
        if key[0] and key[1]:
            membership_by_course_student[key] = membership

    created_offering_members = 0
    updated_offering_members = 0
    created_course_memberships = 0
    updated_course_memberships = 0
    synced_course_to_offering_links = 0

    async def ensure_active_offering_member(offering: Any, student_row: Any, fallback_key: str = "") -> None:
        nonlocal created_offering_members, updated_offering_members

        offering_id = normalize_text(getattr(offering, "id", ""))
        if not offering_id:
            return

        keys = _student_keys(student_row, fallback=fallback_key)
        if not keys:
            return
        canonical_student_id = keys[0]

        rows = members_by_offering.setdefault(offering_id, [])
        canonical_row = next((item for item in rows if normalize_text(item.user_key) == canonical_student_id), None)
        alias_row = next((item for item in rows if normalize_text(item.user_key) in keys), None)
        target_row = canonical_row or alias_row
        if target_row is None:
            created = await member_repo.create(
                {
                    "id": str(uuid.uuid4()),
                    "offering_id": offering_id,
                    "user_key": canonical_student_id,
                    "role": "student",
                    "status": "active",
                    "join_at": now,
                    "leave_at": None,
                }
            )
            rows.append(created)
            created_offering_members += 1
            return

        changed = False
        if normalize_text(target_row.user_key) != canonical_student_id and canonical_row is None:
            target_row.user_key = canonical_student_id
            changed = True
        if normalize_text(target_row.role).lower() != "student":
            target_row.role = "student"
            changed = True

        previous_status = normalize_text(target_row.status).lower()
        if previous_status != "active":
            target_row.status = "active"
            target_row.join_at = now
            changed = True
        if target_row.leave_at is not None:
            target_row.leave_at = None
            changed = True
        if changed:
            updated_offering_members += 1

    async def ensure_course_membership(course_key: str, student_row: Any, fallback_key: str = "") -> None:
        nonlocal created_course_memberships, updated_course_memberships

        normalized_course_key = normalize_text(course_key)
        if not normalized_course_key:
            return
        keys = _student_keys(student_row, fallback=fallback_key)
        if not keys:
            return
        canonical_student_id = keys[0]

        canonical_pair = (normalized_course_key, canonical_student_id)
        canonical_row = membership_by_course_student.get(canonical_pair)
        alias_row = None
        for key in keys:
            alias_row = membership_by_course_student.get((normalized_course_key, key))
            if alias_row is not None:
                break

        if canonical_row is None and alias_row is None:
            created = await membership_repo.create(
                {
                    "id": str(uuid.uuid4()),
                    "course_id": normalized_course_key,
                    "student_id": canonical_student_id,
                    "added_by": "",
                    "created_at": now,
                    "updated_at": now,
                }
            )
            membership_by_course_student[canonical_pair] = created
            created_course_memberships += 1
            return

        if canonical_row is None and alias_row is not None:
            alias_key = (normalized_course_key, normalize_text(alias_row.student_id))
            if alias_key != canonical_pair and canonical_pair not in membership_by_course_student:
                membership_by_course_student.pop(alias_key, None)
                alias_row.student_id = canonical_student_id
                alias_row.updated_at = now
                membership_by_course_student[canonical_pair] = alias_row
                updated_course_memberships += 1

    for membership in course_memberships:
        membership_course_id = normalize_text(membership.course_id)
        membership_student_key = normalize_text(membership.student_id)
        if not membership_course_id or not membership_student_key:
            continue
        student_row = student_by_key.get(membership_student_key)
        if student_row is None:
            continue
        class_name = normalize_text(getattr(student_row, "class_name", ""))
        if not class_name:
            continue
        offerings = offerings_by_course_class.get((membership_course_id, class_name), [])
        for offering in offerings:
            await ensure_active_offering_member(offering, student_row, fallback_key=membership_student_key)
            synced_course_to_offering_links += 1

    for offering in active_offerings:
        offering_id = normalize_text(offering.id)
        offering_course_id = normalize_text(offering.template_course_id)
        if not offering_id or not offering_course_id:
            continue
        for member in members_by_offering.get(offering_id, []):
            if not _is_student_member_active(member):
                continue
            member_key = normalize_text(member.user_key)
            student_row = student_by_key.get(member_key)
            if student_row is None:
                continue
            await ensure_course_membership(offering_course_id, student_row, fallback_key=member_key)

    changed_total = (
        created_offering_members
        + updated_offering_members
        + created_course_memberships
        + updated_course_memberships
    )
    return {
        "scanned_students": len(student_by_key),
        "scanned_active_offerings": len(active_offerings),
        "scanned_course_memberships": len(course_memberships),
        "synced_course_to_offering_links": synced_course_to_offering_links,
        "created_offering_members": created_offering_members,
        "updated_offering_members": updated_offering_members,
        "created_course_memberships": created_course_memberships,
        "updated_course_memberships": updated_course_memberships,
        "changed_total": changed_total,
    }
