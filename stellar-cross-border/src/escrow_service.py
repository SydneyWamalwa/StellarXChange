from models import db, Escrow
from datetime import datetime, timedelta

def create_escrow(sender_id, receiver_id, mediator_id, amount, duration_minutes=60):
    # Set deadline duration (e.g., 60 minutes from creation)
    deadline = datetime.utcnow() + timedelta(minutes=duration_minutes)

    escrow = Escrow(
        sender_id=sender_id,
        receiver_id=receiver_id,
        mediator_id=mediator_id,
        amount=amount,
        status='pending',
        deadline=deadline
    )
    db.session.add(escrow)
    db.session.commit()
    return escrow

def approve_escrow(escrow_id):
    escrow = Escrow.query.get(escrow_id)
    if not escrow:
        return None, "Escrow not found"

    # For simplicity, assume each approval increments the counter
    escrow.approvals += 1

    # Suppose we need 2 approvals (receiver and mediator) to release funds:
    if escrow.approvals >= 2:
        escrow.status = 'approved'

    db.session.commit()
    return escrow, None

def release_escrow(escrow_id):
    escrow = Escrow.query.get(escrow_id)
    if not escrow:
        return None, "Escrow not found"

    # Only release if approved and before deadline
    if escrow.status == 'approved' and not escrow.is_expired():
        escrow.status = 'released'
        db.session.commit()
        return escrow, None
    elif escrow.is_expired():
        escrow.status = 'locked'
        db.session.commit()
        return escrow, "Escrow has expired and is now locked"
    else:
        return escrow, "Escrow is not approved for release"

def check_and_lock_escrow(escrow_id):
    escrow = Escrow.query.get(escrow_id)
    if escrow and escrow.is_expired() and escrow.status == 'pending':
        escrow.status = 'locked'
        db.session.commit()
    return escrow
