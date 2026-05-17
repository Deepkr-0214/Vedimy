from .face_service import FaceService
from .proctoring_service import ProctoringService
from .ai_teaching_service import clean_transcript, generate_summary, translate_summary, generate_questions, extract_pdf_text, SUPPORTED_LANGUAGES

face_service = FaceService()
proctoring_service = ProctoringService()
