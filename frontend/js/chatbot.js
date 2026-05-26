// Chatbot JS

// Initialize Tawk_API centrally and configure it to stay hidden to avoid overlapping the float button
window.Tawk_API = window.Tawk_API || {};
window.Tawk_API.onLoad = function() {
    if (typeof window.Tawk_API.hideWidget === 'function') {
        window.Tawk_API.hideWidget();
    }
};
window.Tawk_API.onChatMaximized = function() {
    const floatingBtn = document.getElementById('chatbot-floating-btn');
    if (floatingBtn) {
        floatingBtn.style.display = 'none';
    }
};
window.Tawk_API.onChatMinimized = function() {
    if (typeof window.Tawk_API.hideWidget === 'function') {
        window.Tawk_API.hideWidget();
    }
    const floatingBtn = document.getElementById('chatbot-floating-btn');
    if (floatingBtn) {
        floatingBtn.style.display = 'flex';
    }
};
window.Tawk_API.onChatClosed = function() {
    if (typeof window.Tawk_API.hideWidget === 'function') {
        window.Tawk_API.hideWidget();
    }
    const floatingBtn = document.getElementById('chatbot-floating-btn');
    if (floatingBtn) {
        floatingBtn.style.display = 'flex';
    }
};

// Immediate hide fallback if Tawk.to has already initialized
if (window.Tawk_API && typeof window.Tawk_API.hideWidget === 'function') {
    window.Tawk_API.hideWidget();
}

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

    // Make Floating Button Draggable & Handle Click Safely
    let isBtnDragging = false;
    let btnStartX = 0, btnStartY = 0;
    let btnStartLeft = 0, btnStartTop = 0;

    floatingBtn.style.cursor = 'grab';

    // Desktop mouse events
    floatingBtn.addEventListener('mousedown', dragBtnStart);
    // Mobile touch events
    floatingBtn.addEventListener('touchstart', dragBtnStart, { passive: false });

    function dragBtnStart(e) {
        if (e.type === 'mousedown' && e.button !== 0) return;
        
        // Prevent default browser behavior (text selection, native drag ghosting)
        e.preventDefault();

        const clientX = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX;
        const clientY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY;

        btnStartX = clientX;
        btnStartY = clientY;
        isBtnDragging = false;

        const rect = floatingBtn.getBoundingClientRect();
        btnStartLeft = rect.left;
        btnStartTop = rect.top;

        floatingBtn.classList.add('dragging');

        if (e.type === 'mousedown') {
            document.addEventListener('mouseup', dragBtnEnd);
            document.addEventListener('mousemove', dragBtnMove);
        } else {
            document.addEventListener('touchend', dragBtnEnd);
            document.addEventListener('touchmove', dragBtnMove, { passive: false });
        }
    }

    function dragBtnMove(e) {
        e.preventDefault();

        const clientX = e.type === 'touchmove' ? e.touches[0].clientX : e.clientX;
        const clientY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY;

        const deltaX = clientX - btnStartX;
        const deltaY = clientY - btnStartY;

        // Differentiate drag from click
        if (Math.abs(deltaX) > 5 || Math.abs(deltaY) > 5) {
            isBtnDragging = true;
        }

        let newLeft = btnStartLeft + deltaX;
        let newTop = btnStartTop + deltaY;

        // Bounding collision with screen boundaries
        const rect = floatingBtn.getBoundingClientRect();
        const width = rect.width;
        const height = rect.height;
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;

        if (newLeft < 10) newLeft = 10;
        if (newTop < 10) newTop = 10;
        if (newLeft + width > windowWidth - 10) newLeft = windowWidth - width - 10;
        if (newTop + height > windowHeight - 10) newTop = windowHeight - height - 10;

        floatingBtn.style.top = newTop + "px";
        floatingBtn.style.left = newLeft + "px";
        floatingBtn.style.bottom = "auto";
        floatingBtn.style.right = "auto";

        // Align the chatbot window relative to the new button position
        if (container && !container.classList.contains('chatbot-hidden')) {
            alignChatbotWindow(newLeft, newTop);
        }
    }

    function dragBtnEnd(e) {
        floatingBtn.classList.remove('dragging');
        if (e.type === 'mouseup') {
            document.removeEventListener('mouseup', dragBtnEnd);
            document.removeEventListener('mousemove', dragBtnMove);
        } else {
            document.removeEventListener('touchend', dragBtnEnd);
            document.removeEventListener('touchmove', dragBtnMove);
        }

        // Prevent standard click from firing if we dragged
        if (isBtnDragging) {
            floatingBtn.dataset.dragged = "true";
            setTimeout(() => {
                delete floatingBtn.dataset.dragged;
            }, 50);
        } else {
            floatingBtn.dataset.dragged = "false";
        }
    }

    floatingBtn.addEventListener('click', (e) => {
        if (floatingBtn.dataset.dragged === "true") {
            e.preventDefault();
            e.stopPropagation();
            return;
        }
        container.classList.toggle('chatbot-hidden');
        if (!container.classList.contains('chatbot-hidden')) {
            chatInput.focus();
            const btnRect = floatingBtn.getBoundingClientRect();
            alignChatbotWindow(btnRect.left, btnRect.top);
        }
    });

    // Helper to align chatbot window right above/next to floating button
    function alignChatbotWindow(btnLeft, btnTop) {
        if (!container) return;
        const rect = container.getBoundingClientRect();
        const btnRect = floatingBtn.getBoundingClientRect();
        
        let newTop;
        // If button is in the top half of viewport, show window below it
        if (btnTop < window.innerHeight / 2) {
            newTop = btnTop + btnRect.height + 15;
        } else {
            // Otherwise, show window above it
            newTop = btnTop - rect.height - 15;
        }
        
        let newLeft = btnLeft - rect.width + btnRect.width; // align right edges

        // Screen collision boundaries for chatbot window
        if (newLeft < 10) newLeft = 10;
        if (newTop < 10) newTop = 10;
        if (newLeft + rect.width > window.innerWidth - 10) newLeft = window.innerWidth - rect.width - 10;
        if (newTop + rect.height > window.innerHeight - 10) newTop = window.innerHeight - rect.height - 10;

        container.style.top = newTop + "px";
        container.style.left = newLeft + "px";
        container.style.bottom = "auto";
        container.style.right = "auto";
    }

    closeBtn.addEventListener('click', () => {
        container.classList.add('chatbot-hidden');
    });

    if (tawkBtn) {
        tawkBtn.addEventListener('click', () => {
            if (window.Tawk_API && typeof window.Tawk_API.maximize === 'function') {
                if (typeof window.Tawk_API.showWidget === 'function') {
                    window.Tawk_API.showWidget();
                }
                window.Tawk_API.maximize();
                container.classList.add('chatbot-hidden');
                if (floatingBtn) {
                    floatingBtn.style.display = 'none';
                }
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

    // Make Chatbot Draggable by its Header
    const header = container.querySelector('.chatbot-header');
    if (header) {
        header.style.cursor = 'grab';
        let winStartX = 0, winStartY = 0;
        let winStartLeft = 0, winStartTop = 0;

        header.addEventListener('mousedown', dragWinStart);
        header.addEventListener('touchstart', dragWinStart, { passive: false });

        function dragWinStart(e) {
            if (e.type === 'mousedown' && e.button !== 0) return;
            
            // Do not drag if close button or other interactive element in header was clicked
            if (e.target.closest('#chatbot-close-btn') || e.target.closest('button')) return;

            e.preventDefault();

            const clientX = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX;
            const clientY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY;

            winStartX = clientX;
            winStartY = clientY;

            const rect = container.getBoundingClientRect();
            winStartLeft = rect.left;
            winStartTop = rect.top;

            container.classList.add('dragging');
            header.style.cursor = 'grabbing';

            if (e.type === 'mousedown') {
                document.addEventListener('mouseup', dragWinEnd);
                document.addEventListener('mousemove', dragWinMove);
            } else {
                document.addEventListener('touchend', dragWinEnd);
                document.addEventListener('touchmove', dragWinMove, { passive: false });
            }
        }

        function dragWinMove(e) {
            e.preventDefault();

            const clientX = e.type === 'touchmove' ? e.touches[0].clientX : e.clientX;
            const clientY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY;

            const deltaX = clientX - winStartX;
            const deltaY = clientY - winStartY;

            let newLeft = winStartLeft + deltaX;
            let newTop = winStartTop + deltaY;

            // Bounding collision with screen edges
            const rect = container.getBoundingClientRect();
            const width = rect.width;
            const height = rect.height;
            const windowWidth = window.innerWidth;
            const windowHeight = window.innerHeight;

            if (newLeft < 0) newLeft = 0;
            if (newTop < 0) newTop = 0;
            if (newLeft + width > windowWidth) newLeft = windowWidth - width;
            if (newTop + height > windowHeight) newTop = windowHeight - height;

            container.style.top = newTop + "px";
            container.style.left = newLeft + "px";
            container.style.bottom = "auto";
            container.style.right = "auto";
        }

        function dragWinEnd(e) {
            container.classList.remove('dragging');
            header.style.cursor = 'grab';

            if (e.type === 'mouseup') {
                document.removeEventListener('mouseup', dragWinEnd);
                document.removeEventListener('mousemove', dragWinMove);
            } else {
                document.removeEventListener('touchend', dragWinEnd);
                document.removeEventListener('touchmove', dragWinMove);
            }
        }
    }
}
