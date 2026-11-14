"""Rename the stored deputy role code ARE (and legacy RE_ARE) to DRE.

Client decision DR-02 (Nov 2026): "DRE" is used everywhere instead of "ARE".
Since release 5.1 the application already treats ARE / RE_ARE as DRE when it reads them, so this
script is only a tidy-up of the stored codes. It is NOT required for the application to work.

SAFE BY DESIGN
  * Dry run by default: lists the rows that would change. Nothing is written.
  * `--apply` changes only users.role and project_users.role values equal to ARE / RE_ARE.
    It changes no password, e-mail, name, membership status, project or RFI data.
  * One audit row per changed record (before/after), in the same transaction.
  * Idempotent: a second run finds nothing to change.

Usage (inside the backend container, after a verified backup):
    python -m scripts.migrate_dre_rename            # dry run
    python -m scripts.migrate_dre_rename --apply    # execute
"""
import sys
from sqlalchemy import select
from app.database import SessionLocal
from app.models import User, ProjectUser
from app.authz import LEGACY_ROLE_ALIASES
from app.services.audit import log


def main(apply: bool) -> int:
    db = SessionLocal()
    try:
        old = list(LEGACY_ROLE_ALIASES)
        users = list(db.scalars(select(User).where(User.role.in_(old))))
        members = list(db.scalars(select(ProjectUser).where(ProjectUser.role.in_(old))))
        print(f'users.role to rename: {[(u.id, u.role) for u in users]}')
        print(f'project_users.role to rename: {[(m.id, m.project_id, m.user_id, m.role) for m in members]}')
        if not users and not members:
            print('Nothing to change.')
            return 0
        if not apply:
            print('DRY RUN - nothing written. Re-run with --apply to execute.')
            return 0
        actor = db.scalar(select(User.id).where(User.role == 'ADMIN').order_by(User.id))
        if actor is None:
            raise SystemExit('No ADMIN user found to attribute the audit rows to.')
        for u in users:
            before = u.role
            u.role = LEGACY_ROLE_ALIASES[before]
            log(db, actor, 'USER', u.id, 'ROLE_CODE_RENAME', 'DR-02: ARE -> DRE (migration script)', before={'role': before}, after={'role': u.role})
        for m in members:
            before = m.role
            m.role = LEGACY_ROLE_ALIASES[before]
            log(db, actor, 'MEMBERSHIP', m.id, 'ROLE_CODE_RENAME', 'DR-02: ARE -> DRE (migration script)', project_id=m.project_id,
                before={'role': before}, after={'role': m.role})
        db.commit()
        print(f'Applied: {len(users)} user(s), {len(members)} membership(s) renamed to DRE.')
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main('--apply' in sys.argv[1:]))
