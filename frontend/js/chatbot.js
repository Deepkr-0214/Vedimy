// Chatbot JS
document.addEventListener('DOMContentLoaded', () => {
    fetch('/components/chatbot.html')
        .then(response => {
            if (!response.ok) throw new Error("Failed to load chatbot UI");
            return response.text();
        })
        .then(html => {
            document.body.insertAdjacentHTML('beforeend', html);
            initChatbot();
        })
        .catch(err => console.error('Chatbot load error:', err));
});

function initChatbot() {
    const floatingBtn = document.getElementById('chatbot-floating-btn');
    const container = document.getElementById('chatbot-container') || document.getElementById('vedimy-chatbot-container');
    const closeBtn = document.getElementById('chatbot-close-btn');
    const chatForm = document.getElementById('chatbot-form');
    const chatInput = document.getElementById('chatbot-input');
    const messagesContainer = document.getElementById('chatbot-messages');
    const typingIndicator = document.getElementById('chatbot-typing-indicator');
    const tawkBtn = document.getElementById('tawk-connect-btn');

    if (!floatingBtn || !container) return;

    floatingBtn.addEventListener('click', () => {
        container.classList.toggle('chatbot-hidden');
        if (!container.classList.contains('chatbot-hidden')) {
            chatInput.focus();
        }
    });

    closeBtn.addEventListener('click', () => {
        container.classList.add('chatbot-hidden');
    });

    if (tawkBtn) {
        tawkBtn.addEventListener('click', () => {
            if (window.Tawk_API && typeof window.Tawk_API.maximize === 'function') {
                window.Tawk_API.maximize();
                container.classList.add('chatbot-hidden');
            } else {
                addMessage("Live support is currently unavailable or still loading. Please ensure your adblocker isn't blocking it.", 'bot');
            }
        });
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (!message) return;

        addMessage(message, 'user');
        chatInput.value = '';
        
        typingIndicator.style.display = 'block';
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        try {
            const userType = localStorage.getItem('token') ? 'host' : 'guest';
            
            const response = await fetch('/api/chatbot/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, user_type: userType })
            });

            const data = await response.json();
            typingIndicator.style.display = 'none';
            
            if (!response.ok) {
                // Ignore DB logging errors if they happen and use fallback
                throw new Error(data.error || 'API Error');
            }
            
            addMessage(data.response, 'bot');
        } catch (error) {
            console.error('Chat error:', error);
            typingIndicator.style.display = 'none';
            // Fallback response if DB fails (which is why 500 happened)
            const fallbackMsg = "I'm experiencing database issues, but I'm here! I am your Vedimy AI Assistant. If you need live human support, click the Tawk.to button above.";
            addMessage(fallbackMsg, 'bot');
        }
    });

    function addMessage(text, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chatbot-message ${sender}-message`;
        msgDiv.style.display = 'flex';
        msgDiv.style.gap = '0.75rem';
        msgDiv.style.alignItems = 'flex-end';
        if (sender === 'user') msgDiv.style.flexDirection = 'row-reverse';
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.style.width = '32px';
        avatar.style.height = '32px';
        avatar.style.borderRadius = '50%';
        avatar.style.display = 'flex';
        avatar.style.alignItems = 'center';
        avatar.style.justifyContent = 'center';
        avatar.style.fontSize = '0.9rem';
        avatar.style.flexShrink = '0';
        
        if (sender === 'bot') {
            avatar.style.background = 'linear-gradient(135deg, #3b82f6, #8b5cf6)';
            avatar.innerHTML = '✨';
        } else {
            avatar.style.background = 'rgba(255,255,255,0.1)';
            avatar.innerHTML = '👤';
        }
        
        const content = document.createElement('div');
        content.className = 'message-content';
        content.style.padding = '0.75rem 1rem';
        content.style.fontSize = '0.9rem';
        content.style.lineHeight = '1.4';
        
        if (sender === 'user') {
            content.style.background = 'linear-gradient(135deg, #3b82f6, #6366f1)';
            content.style.color = 'white';
            content.style.borderRadius = '12px 12px 0 12px';
        } else {
            content.style.background = 'rgba(255,255,255,0.05)';
            content.style.color = '#e2e8f0';
            content.style.borderRadius = '12px 12px 12px 0';
        }
        
        content.innerHTML = `<p style="margin:0;">${text}</p>`;
        
        msgDiv.appendChild(avatar);
        msgDiv.appendChild(content);
        
        // Insert before typing indicator
        messagesContainer.appendChild(msgDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}
