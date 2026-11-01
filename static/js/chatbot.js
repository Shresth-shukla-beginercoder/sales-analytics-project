// Chatbot Widget State
let chatbotOpen = false;
let conversationHistory = []; // Preserve messages during toggles

// Initialize chatbot widget
document.addEventListener('DOMContentLoaded', function() {
    const toggleBtn = document.getElementById('chatbotToggle');
    const closeBtn = document.getElementById('chatbotClose');
    const panel = document.getElementById('chatbotPanel');

    // Toggle chatbot panel
    toggleBtn.addEventListener('click', function() {
        toggleChatbot();
    });

    // Close button
    closeBtn.addEventListener('click', function() {
        toggleChatbot();
    });

    // Close on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && chatbotOpen) {
            toggleChatbot();
        }
    });

    // Restore conversation history if exists
    restoreConversation();
});

function toggleChatbot() {
    const panel = document.getElementById('chatbotPanel');
    const toggleBtn = document.getElementById('chatbotToggle');

    chatbotOpen = !chatbotOpen;

    if (chatbotOpen) {
        panel.classList.add('open');
        // First time the panel is opened on this page: greet the user with hints
        if (conversationHistory.length === 0) {
            showWelcomeMessage();
        }
        // Focus input when opened
        setTimeout(() => {
            document.getElementById('chatInput').focus();
        }, 300);
    } else {
        panel.classList.remove('open');
    }
}

// Friendly first-open message with example questions to try
function showWelcomeMessage() {
    const chatHistory = document.getElementById('chatHistory');

    const welcomeHtml = `
    <div class="message bot-message welcome">
        <p><strong>Hi! How can I help you explore your sales data?</strong></p>
        <p>I can answer questions about totals, top products, city and category breakdowns, or monthly trends. Try asking me something like:</p>
        <div class="chat-suggest">
            <button type="button" onclick="useSuggestion(this)">What is my total sales revenue?</button>
            <button type="button" onclick="useSuggestion(this)">Which product sells the most?</button>
            <button type="button" onclick="useSuggestion(this)">Which city has the best sales?</button>
            <button type="button" onclick="useSuggestion(this)">Show the monthly sales trend</button>
        </div>
    </div>`;

    chatHistory.innerHTML += welcomeHtml;
    conversationHistory.push(welcomeHtml);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Fill the input box with a suggested question (user still presses Send)
function useSuggestion(btn) {
    const input = document.getElementById('chatInput');
    input.value = btn.textContent;
    input.focus();
}

function restoreConversation() {
    const chatHistory = document.getElementById('chatHistory');

    // Restore messages from memory
    conversationHistory.forEach(msg => {
        chatHistory.innerHTML += msg;
    });

    // Scroll to bottom
    if (conversationHistory.length > 0) {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
}

function sendMessage() {
    const input = document.getElementById("chatInput");
    const chatHistory = document.getElementById("chatHistory");
    const message = input.value.trim();

    if (!message) return;

    // Display user message
    const userMessageHtml = `<div class="message user-message">${escapeHtml(message)}</div>`;
    chatHistory.innerHTML += userMessageHtml;
    conversationHistory.push(userMessageHtml); // Save to history

    input.value = "";
    chatHistory.scrollTop = chatHistory.scrollHeight;

    // Loading indicator
    const loadingId = "loading-" + Date.now();
    const loadingHtml = `<div id="${loadingId}" class="message bot-message loading">Thinking...</div>`;
    chatHistory.innerHTML += loadingHtml;
    chatHistory.scrollTop = chatHistory.scrollHeight;

    fetch("/api/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').getAttribute("content")
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById(loadingId).remove();

        let botMessageHtml;
        if (data.success) {
            // Success: render the answer as sanitized markdown - no error bubble
            botMessageHtml = `<div class="message bot-message markdown">${renderBotHtml(data.answer)}</div>`;
        } else {
            // Only a final failure gets an error bubble: short, friendly text.
            // Technical details stay in the server logs (data.error is not shown).
            botMessageHtml = `<div class="message bot-message error">Sorry, I could not answer that just now. Please try again in a moment.</div>`;
        }

        chatHistory.innerHTML += botMessageHtml;
        conversationHistory.push(botMessageHtml); // Save to history
        chatHistory.scrollTop = chatHistory.scrollHeight;
    })
    .catch(error => {
        document.getElementById(loadingId).remove();
        const errorHtml = `<div class="message bot-message error">Connection issue - please check your internet and try again.</div>`;
        chatHistory.innerHTML += errorHtml;
        conversationHistory.push(errorHtml); // Save to history
        chatHistory.scrollTop = chatHistory.scrollHeight;
    });
}

// ----- Safe markdown rendering for bot answers -----
// marked turns markdown into HTML; DOMPurify then strips anything unsafe
// (script tags, event handlers, javascript: links, ...). The sanitized HTML
// is the only model-controlled markup ever placed into innerHTML.
const MD_ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'del', 'ul', 'ol', 'li', 'code', 'pre', 'blockquote', 'h1', 'h2', 'h3', 'a'];
const MD_ALLOWED_ATTR = ['href', 'target', 'rel'];

if (typeof marked !== 'undefined') {
    marked.use({ breaks: true }); // single newlines render as <br>
}

function renderBotHtml(text) {
    text = String(text == null ? '' : text);
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
        let html = '';
        try {
            html = marked.parse(text);
        } catch (e) {
            html = ''; // never let a parse problem break the widget
        }
        if (html) {
            return DOMPurify.sanitize(html, { ALLOWED_TAGS: MD_ALLOWED_TAGS, ALLOWED_ATTR: MD_ALLOWED_ATTR });
        }
    }
    // Fallback (library missing): escaped plain text, never raw markup
    return escapeHtml(text);
}

// Helper function to escape HTML and prevent XSS
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}
