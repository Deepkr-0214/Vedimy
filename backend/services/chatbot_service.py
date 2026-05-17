import re
from models.chatbot import ChatHistory, SupportLog
from extensions import db

class ChatbotService:
    @staticmethod
    def process_message(user_type, message):
        """Processes an incoming message and generates an AI-like response."""
        msg_lower = message.lower()
        
        # Simple simulated AI responses based on keywords
        response = ChatbotService._generate_response(msg_lower)
        
        try:
            # Log to chat history
            history = ChatHistory(
                user_type=user_type,
                message=message,
                response=response
            )
            db.session.add(history)
            db.session.commit()
            history_id = history.id
        except Exception as e:
            db.session.rollback()
            print(f"Chat history logging failed: {e}")
            history_id = None
        
        return {
            'response': response,
            'history_id': history_id
        }

    @staticmethod
    def _generate_response(msg):
        # Greetings
        if any(word in msg for word in ['hello', 'hi', 'hey', 'नमस्ते', 'namaste']):
            if 'नमस्ते' in msg or 'namaste' in msg:
                return "नमस्ते! मैं आपका वेदांग एआई असिस्टेंट हूँ। मैं आपकी कैसे मदद कर सकता हूँ?"
            return "Hello! I am your Vedimy AI assistant. How can I help you today?"

        # Class / Meeting Join Help
        if 'join' in msg or 'class' in msg or 'conference' in msg:
            return "To join a class or conference, navigate to the Dashboard and click on 'Join Class'. If you have a room code, you can enter it on the join page. Ensure your camera and microphone permissions are granted."

        # Exams / Biometrics
        if 'exam' in msg or 'biometric' in msg or 'face' in msg:
            return "During exams, you must keep your face visible to the camera for biometric verification. If you experience technical issues, ensure your browser has camera access. Any suspicious activity will be logged."

        # Lecture Summaries
        if 'summary' in msg or 'summarize' in msg or 'notes' in msg:
            return "I can help generate quick revision notes! Please provide the topic or paste the lecture transcript you'd like me to summarize."
            
        # Support / Help
        if 'help' in msg or 'support' in msg or 'issue' in msg:
            return "I can assist you with platform navigation, exam rules, and technical issues. If you need live human support, please use the Tawk.to widget in the bottom corner of your screen."

        # Hindi Support
        if 'हिंदी' in msg or 'hindi' in msg:
            return "हाँ, मैं हिंदी में भी आपकी मदद कर सकता हूँ। कृपया अपना प्रश्न पूछें।"

        # Default fallback
        return "I'm an AI assistant designed to help you with the Vedimy platform. Could you please provide more details about your question? You can ask me about joining classes, exam instructions, or lecture summaries."

    @staticmethod
    def create_support_ticket(issue):
        """Creates a support ticket for technical help."""
        log = SupportLog(issue=issue, status='open')
        db.session.add(log)
        db.session.commit()
        return log.to_dict()

    @staticmethod
    def get_history(limit=50):
        """Fetches recent chat history."""
        records = ChatHistory.query.order_by(ChatHistory.timestamp.desc()).limit(limit).all()
        return [r.to_dict() for r in records][::-1]
