from app.models import AuditLog
def log(db,user_id,entity_type,entity_id,action,details=None):
    db.add(AuditLog(user_id=user_id,entity_type=entity_type,entity_id=entity_id,action=action,details=details)); db.commit()
