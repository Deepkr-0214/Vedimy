from models import Exam, User, Violation
from extensions import db
from datetime import datetime

class ProctoringService:
    def process_frame(self, frame_base64: str, exam_id: str, user_id: str) -> dict:
        # Abstracted logic to detect face and log violations if needed
        # Since face_service does the heavy lifting, we evaluate the results here
        # Return {"status": "ok"} or {"status": "violation", "type": "..."}
        
        # Stub implementation
        return {"status": "ok"}
        
    def log_violation(self, user_id, exam_id, room_id, violation_type, severity="warning"):
        violation = Violation(
            user_id=user_id,
            exam_id=exam_id,
            room_id=room_id,
            violation_type=violation_type,
            severity=severity
        )
        db.session.add(violation)
        db.session.commit()
        return violation
