"""DR-02: the deputy role is DRE everywhere. Stored legacy ARE / RE_ARE codes keep working as DRE."""
from sqlalchemy import select, update
from app.database import SessionLocal
from app.models import User, ProjectUser, AuditLog
from conftest import submitted_batch, assign, review


def test_legacy_are_account_is_presented_and_authorised_as_dre(world):
    me = world.are.get('/me').json()
    assert me['role'] == 'DRE'
    m = [x for x in me['memberships'] if x['project_id'] == world.A][0]
    assert (m['role'], m['role_label'], m['category'], m['deputy_label']) == ('DRE', 'Deputy Resident Engineer', '2.1', 'DRE')
    # the legacy account can take the final decision exactly like DRE
    _, (rid,) = submitted_batch(world.encoder, world.A)
    assert assign(world.are, rid, [world.surveyor]).status_code == 200
    assert review(world.surveyor, rid).status_code == 200
    r = world.are.post(f'/rfis/{rid}/decision', {'disposition_code': 'APPROVED_FURTHER_WORKS'})
    assert r.status_code == 200, r.text


def test_are_can_no_longer_be_assigned_and_is_not_offered(world, admin):
    codes = {r['code'] for g in admin.get('/projects/meta/roles').json() for r in g['roles']}
    assert 'DRE' in codes and not codes & {'ARE', 'RE_ARE'}
    assert admin.post(f'/projects/{world.A}/members', {'user_id': world.outsider.id, 'role': 'ARE'}).status_code == 400
    members = admin.get(f'/projects/{world.A}/members').json()
    assert [x['role'] for x in members if x['user_id'] == world.are.id] == ['DRE']
    assert admin.get(f'/projects/{world.A}/settings').json()['deputy_label'] == 'DRE'
    assert admin.put(f'/projects/{world.A}/settings', {'deputy_label': 'ARE'}).status_code == 400


def test_rename_script_dry_run_apply_idempotent(world):
    from scripts.migrate_dre_rename import main
    with SessionLocal() as db:
        assert db.scalar(select(ProjectUser.role).where(ProjectUser.user_id == world.are.id)) == 'ARE'
        pw_before = db.scalar(select(User.password_hash).where(User.id == world.are.id))
        audit_before = db.query(AuditLog).filter_by(action='ROLE_CODE_RENAME').count()
    try:
        assert main(apply=False) == 0
        with SessionLocal() as db:
            assert db.scalar(select(ProjectUser.role).where(ProjectUser.user_id == world.are.id)) == 'ARE'  # dry run wrote nothing
        assert main(apply=True) == 0
        with SessionLocal() as db:
            assert db.scalar(select(ProjectUser.role).where(ProjectUser.user_id == world.are.id)) == 'DRE'
            assert db.scalar(select(User.role).where(User.id == world.are.id)) == 'DRE'
            assert db.scalar(select(User.password_hash).where(User.id == world.are.id)) == pw_before  # nothing else touched
            assert db.query(AuditLog).filter_by(action='ROLE_CODE_RENAME').count() >= audit_before + 2
            n = db.query(AuditLog).filter_by(action='ROLE_CODE_RENAME').count()
        assert main(apply=True) == 0  # idempotent
        with SessionLocal() as db:
            assert db.query(AuditLog).filter_by(action='ROLE_CODE_RENAME').count() == n
        assert world.are.get('/me').json()['role'] == 'DRE'
    finally:
        # restore the legacy code so other tests keep covering the pre-rename case
        with SessionLocal() as db:
            db.execute(update(User).where(User.id == world.are.id).values(role='ARE'))
            db.execute(update(ProjectUser).where(ProjectUser.user_id == world.are.id).values(role='ARE'))
            db.commit()
