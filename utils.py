from extensions import db
from models import ActivityLog

def log_activity(Actor_id, action, target_type=None, target_id=None, details=None):
    """Write onne row to the audit trail. Called after every state-changing action"""
    entry=ActivityLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id, 
        details=details,
    )
    db.session.add(entry)
    db.session.commit()
    