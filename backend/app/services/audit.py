import json
from datetime import date, datetime
from app.models import AuditLog


def _ser(v):
    if v is None: return None
    def default(o):
        if isinstance(o, (datetime, date)): return o.isoformat()
        return str(o)
    return json.dumps(v, default=default, ensure_ascii=False)


def log(db, user_id, entity_type, entity_id, action, details=None, project_id=None, before=None, after=None, commit=False):
    """Add an audit row to the CURRENT transaction (SRS 11.1, NFR Integrity).

    The caller commits it together with the business change, so a workflow change and its audit
    record are saved or rolled back together. `commit=True` exists only for read-only actions
    (exports/downloads) that have no other change to commit.
    """
    db.add(AuditLog(user_id=user_id, entity_type=entity_type, entity_id=entity_id or 0, action=action,
                    details=details, project_id=project_id, before_json=_ser(before), after_json=_ser(after)))
    if commit:
        db.commit()
