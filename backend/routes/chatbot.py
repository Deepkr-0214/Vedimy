from flask import Blueprint, request, jsonify
from services.chatbot_service import ChatbotService

chatbot_bp = Blueprint('chatbot', __name__)

@chatbot_bp.route('/message', methods=['POST'])
def send_message():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Message is required'}), 400
        
    message = data.get('message')
    user_type = data.get('user_type', 'guest')
    
    try:
        result = ChatbotService.process_message(user_type, message)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@chatbot_bp.route('/help', methods=['POST'])
def request_help():
    data = request.get_json()
    if not data or 'issue' not in data:
        return jsonify({'error': 'Issue description is required'}), 400
        
    issue = data.get('issue')
    
    try:
        ticket = ChatbotService.create_support_ticket(issue)
        return jsonify({'message': 'Support ticket created successfully', 'ticket': ticket}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@chatbot_bp.route('/history', methods=['GET'])
def get_history():
    try:
        limit = int(request.args.get('limit', 50))
        history = ChatbotService.get_history(limit)
        return jsonify({'history': history}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
