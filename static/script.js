// Theme toggle functionality
const themeToggle = document.getElementById('theme-toggle');
const body = document.body;

themeToggle.addEventListener('click', () => {
    body.classList.toggle('dark-mode');
    const isDarkMode = body.classList.contains('dark-mode');
    localStorage.setItem('darkMode', isDarkMode);
    updateThemeToggleButton(isDarkMode);
});

function updateThemeToggleButton(isDarkMode) {
    const icon = themeToggle.querySelector('i');
    const text = themeToggle.querySelector('span');
    
    if (isDarkMode) {
        icon.classList.replace('fa-moon', 'fa-sun');
        text.textContent = 'Light Mode';
    } else {
        icon.classList.replace('fa-sun', 'fa-moon');
        text.textContent = 'Dark Mode';
    }
}

// Check for saved theme preference
const savedTheme = localStorage.getItem('darkMode');
if (savedTheme === 'true') {
    body.classList.add('dark-mode');
    updateThemeToggleButton(true);
}

// Chatbot functionality
const chatbotContainer = document.getElementById('chatbot-container');
const chatbotHeader = document.getElementById('chatbot-header');
const chatbotToggle = document.getElementById('chatbot-toggle');
const chatbotMessages = document.getElementById('chatbot-messages');
const chatbotForm = document.getElementById('chatbot-form');
const userInput = document.getElementById('user-input');

let isDragging = false;
let currentX;
let currentY;
let initialX;
let initialY;
let xOffset = 0;
let yOffset = 0;

// Drag functionality
chatbotHeader.addEventListener('mousedown', dragStart);
document.addEventListener('mousemove', drag);
document.addEventListener('mouseup', dragEnd);

function dragStart(e) {
    if (e.target === chatbotHeader || e.target.parentElement === chatbotHeader) {
        isDragging = true;
        initialX = e.clientX - xOffset;
        initialY = e.clientY - yOffset;
    }
}

function drag(e) {
    if (isDragging) {
        e.preventDefault();
        currentX = e.clientX - initialX;
        currentY = e.clientY - initialY;

        // Boundary checking
        const rect = chatbotContainer.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        // Prevent dragging outside viewport
        if (rect.left + currentX < 0) currentX = -xOffset;
        if (rect.right + currentX - xOffset > viewportWidth) currentX = viewportWidth - rect.width + xOffset;
        if (rect.top + currentY < 0) currentY = -yOffset;
        if (rect.bottom + currentY - yOffset > viewportHeight) currentY = viewportHeight - rect.height + yOffset;

        xOffset = currentX;
        yOffset = currentY;
        
        setTranslate(currentX, currentY, chatbotContainer);
    }
}

function setTranslate(xPos, yPos, el) {
    el.style.transform = `translate3d(${xPos}px, ${yPos}px, 0)`;
}

function dragEnd() {
    isDragging = false;
}

// Chatbot toggle functionality
chatbotToggle.addEventListener('click', () => {
    chatbotContainer.classList.toggle('chatbot-minimized');
    const icon = chatbotToggle.querySelector('i');
    icon.classList.toggle('fa-chevron-down');
    icon.classList.toggle('fa-chevron-up');
});

// Message handling
chatbotForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (message) {
        addMessage('user', message);
        userInput.value = '';
        showTypingIndicator();
        try {
            const response = await sendMessageToInquiro(message);
            removeTypingIndicator();
            addMessage('bot', response.content);
        } catch (error) {
            removeTypingIndicator();
            addMessage('bot', 'Sorry, I encountered an error. Please try again later.');
        }
    }
});

function addMessage(sender, message) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('chat-message', `${sender}-message`);
    messageElement.innerHTML = message;
    chatbotMessages.appendChild(messageElement);
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

function showTypingIndicator() {
    const typingIndicator = document.createElement('div');
    typingIndicator.classList.add('typing-indicator');
    typingIndicator.innerHTML = '<span></span><span></span><span></span>';
    chatbotMessages.appendChild(typingIndicator);
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

function removeTypingIndicator() {
    const typingIndicator = chatbotMessages.querySelector('.typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

async function sendMessageToInquiro(message) {
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message }),
        });
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return await response.json();
    } catch (error) {
        console.error('Error sending message to Inquiro:', error);
        throw error;
    }
}

// Load events and faculty (keeping these functions as they were)
async function loadUpcomingEvents() {
    try {
        const response = await fetch('/api/events');
        const events = await response.json();
        const eventsList = document.getElementById('events-list');
        
        events.forEach((event, index) => {
            const eventCard = document.createElement('div');
            eventCard.className = 'col-md-4 mb-4';
            eventCard.innerHTML = `
                <div class="card animate__animated animate__fadeInUp" style="animation-delay: ${index * 0.1}s">
                    <div class="card-body">
                        <h5 class="card-title">${event.name}</h5>
                        <p class="card-text">${event.description}</p>
                        <p class="card-text"><small class="text-muted">Date: ${new Date(event.date).toLocaleDateString()}</small></p>
                    </div>
                </div>
            `;
            eventsList.appendChild(eventCard);
        });
    } catch (error) {
        console.error('Error loading upcoming events:', error);
    }
}

async function loadFacultyMembers() {
    try {
        const response = await fetch('/api/faculty');
        const faculty = await response.json();
        const facultyList = document.getElementById('faculty-list');
        
        faculty.forEach((member, index) => {
            const facultyCard = document.createElement('div');
            facultyCard.className = 'col-md-4 mb-4';
            facultyCard.innerHTML = `
                <div class="card animate__animated animate__fadeInUp" style="animation-delay: ${index * 0.1}s">
                    <img src="${member.image}" class="card-img-top" alt="${member.name}">
                    <div class="card-body">
                        <h5 class="card-title">${member.name}</h5>
                        <p class="card-text">${member.position}</p>
                        <p class="card-text"><small class="text-muted">${member.specialization}</small></p>
                    </div>
                </div>
            `;
            facultyList.appendChild(facultyCard);
        });
    } catch (error) {
        console.error('Error loading faculty members:', error);
    }
}

// Initialize page load events
window.addEventListener('load', () => {
    loadUpcomingEvents();
    loadFacultyMembers();
});

// Animation observer
const animateOnScroll = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('animate__animated', 'animate__fadeInUp');
        }
    });
}, { threshold: 0.1 });

document.querySelectorAll('.section, .card, .faculty-card').forEach(el => {
    animateOnScroll.observe(el);
});