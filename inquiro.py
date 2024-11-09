import os
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
import mysql.connector
import re
from datetime import datetime, date
import spacy
from spacy.matcher import Matcher, PhraseMatcher
from dotenv import load_dotenv
import google.generativeai as genai
from cachetools import TTLCache

# Set up logging configuration for file-only logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler("chatbot.log")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.propagate = False

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db = SQLAlchemy(app)
app.config['SESSION_SQLALCHEMY'] = db
Session(app)

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_md")
    logger.info("SpaCy model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load SpaCy model: {str(e)}")
    raise

# Create a connection pool
dbconfig = {
    "host": os.getenv('DB_HOST'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "database": os.getenv('DB_NAME')
}

try:
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=5,
        **dbconfig
    )
    logger.info("MySQL connection pool created successfully")
except mysql.connector.Error as err:
    logger.error(f"Error creating MySQL connection pool: {err}")
    raise

generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]
# Configure Gemini API
try:
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel(model_name="gemini-pro",
                              generation_config=generation_config,
                              safety_settings=safety_settings)

    logger.info("Gemini API configured successfully")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {str(e)}")
    raise

# Create a cache for static data
cache = TTLCache(maxsize=100, ttl=3600)  # Cache for 1 hour

# Define academic intents
ACADEMIC_INTENTS = {
    "greeting": ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening"],
    "farewell": ["bye", "goodbye", "see you later", "take care", "farewell"],
    "attendance": ["attendance", "class presence", "how many classes", "absent", "present", "attendance percentage", "attendance details", "my attendance", "check attendance", "show attendance", "give me my attendance", "what's my attendance"],
    "results": ["result", "results", "cgpa", "sgpa", "grades", "score", "academic performance", "my results", "show results", "give me my results", "what are my results"],
    "schedule": ["schedule", "timetable", "class timings", "when is my class", "lecture timings", "class schedule"],
    "exams": ["exam", "exams", "test", "tests", "when is the exam", "examination dates", "exam schedule", "next exam"],
    "assignments": ["assignment", "assignments", "homework", "project", "due date", "submission deadline"],
    "faculty": ["faculty", "professor", "teacher", "instructor", "who teaches", "faculty information"],
    "events": ["academic event", "seminar", "workshop", "conference", "upcoming events", "events", "event", "college activities"],
    "change_usn": ["change usn", "update usn", "set my usn", "usn", "student number"],
    "course_info": ["subjects", "course", "courses", "credits", "syllabus", "curriculum"]
}

# # Initialize matchers
# matcher = Matcher(nlp.vocab)
# phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")


# # Add patterns to the matchers
# for intent, patterns in ACADEMIC_INTENTS.items():
#     matcher.add(intent, [[{"LOWER": word} for word in pattern.split()] for pattern in patterns])
#     phrase_matcher.add(intent, [nlp.make_doc(pattern) for pattern in patterns])

# Create PhraseMatcher
matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
for intent, patterns in ACADEMIC_INTENTS.items():
    matcher.add(intent, [nlp(text) for text in patterns])

def get_intent(user_input):
    logger.debug(f"Analyzing intent for input: {user_input}")
    doc = nlp(user_input.lower())
    
    # Use PhraseMatcher for exact matches
    matches = matcher(doc)
    if matches:
        intent = nlp.vocab.strings[matches[0][0]]  # Convert match ID to string
        return intent # Perfect match
    
    max_similarity = 0
    best_intent = "unknown"
    
    for intent, patterns in ACADEMIC_INTENTS.items():
        for pattern in patterns:
            similarity = nlp(pattern).similarity(doc)
            if similarity > max_similarity:
                max_similarity = similarity
                best_intent = intent
    
    # Adjust the threshold for better accuracy
    if max_similarity > 0.6:
        logger.debug(f"Found intent: {best_intent} with similarity {max_similarity}")
        return best_intent
    
    logger.debug("No intent matched, returning 'unknown'")
    return "unknown"

def format_response(text, options=None, structured=False):
    # Assuming the text contains valid HTML and should be rendered as-is, no need for html.escape
    formatted_text = text.replace('\n', '<br>')
    
    response = {
        "type": "text",
        "content": formatted_text,  # This should now render the HTML properly
        "formatted": True
    }
    
    if options:
        response["options"] = options
    
    if structured:
        response["structured"] = True
    
    return response

def get_response(user_input, session_id):
    logger.debug(f"Processing user input: {user_input}")
    intent = get_intent(user_input)
    logger.debug(f"Detected intent: {intent}")
    
    try:
        if intent == "greeting":
            return format_response(
                "Hello! I'm Inquiro, your academic assistant for the CSD Department. How can I assist you today?",
                [
                    "Check attendance",
                    "View academic results",
                    "See class schedule",
                    "Check exam dates",
                    "View pending assignments",
                    "Get faculty information",
                    "Learn about academic events"
                ],
                structured=True
            )
        
        if intent == "farewell":
            return format_response("Thank you for using Inquiro. If you have any more questions about your academics, feel free to ask anytime. Have a great day!")

        if intent == "change_usn":
            session['usn'] = None
            session['stage'] = "waiting_for_usn"
            return format_response("Let's update your USN. Please provide your new USN in the format 4PM__CG0__ (e.g., 4PM22CG042).")

        if session.get('usn') is None and intent in ["attendance", "results", "exams", "assignments"]:
            session['stage'] = "waiting_for_usn"
            session['pending_intent'] = intent
            return format_response("To assist you with that academic information, I'll need your USN. Could you please provide it in the format 4PM__CG0__ (e.g., 4PM22CG042)?")

        if session.get('stage') == "waiting_for_usn":
            if re.match(r'^4pm\d{2}[a-z]{2}\d{3}$', user_input, re.IGNORECASE):
                session['usn'] = user_input.upper()
                session['stage'] = "normal"
                pending_intent = session.get('pending_intent')
                if pending_intent:
                    response = handle_intent(pending_intent, session['usn'])
                    session['pending_intent'] = None
                    return response
                return format_response(f"Thank you! Your USN is now set to {session['usn']}. What academic information would you like to know about?")
            else:
                return format_response("I'm sorry, but that doesn't appear to be a valid USN format. Could you please provide your USN in the format 4PM__CG0__ (e.g., 4PM22CG042)?")

        if intent == "attendance":
            if session.get('usn'):
                return get_student_attendance(session['usn'])
            else:
                session['stage'] = "waiting_for_usn"
                session['pending_intent'] = "attendance"
                return format_response("To check your attendance, I'll need your USN. Please provide it in the format 4PM__CG0__ (e.g., 4PM22CG042).")

        if intent == "results":
            if session.get('usn'):
                return get_student_results(session['usn'])
            else:
                session['stage'] = "waiting_for_usn"
                session['pending_intent'] = "results"
                return format_response("To view your academic results, I'll need your USN. Please provide it in the format 4PM__CG0__ (e.g., 4PM22CG042).")

        if intent == "schedule":
            return get_class_schedule()

        if intent == "exams":
            if session.get('usn'):
                return get_exam_schedule(session['usn'])
            else:
                session['stage'] = "waiting_for_usn"
                session['pending_intent'] = "exams"
                return format_response("To check your exam schedule, I'll need your USN. Please provide it in the format 4PM__CG0__ (e.g., 4PM22CG042).")

        if intent == "assignments":
            if session.get('usn'):
                return get_assignments(session['usn'])
            else:
                session['stage'] = "waiting_for_usn"
                session['pending_intent'] = "assignments"
                return format_response("To view your pending assignments, I'll need your USN. Please provide it in the format 4PM__CG0__ (e.g., 4PM22CG042).")

        if intent == "faculty":
            return get_faculty_info()

        if intent == "events":
            return get_academic_events()

        if intent == "course_info":
            semester = extract_semester(user_input)
            if semester:
                return get_courses_by_semester(semester)
            else:
                session['stage'] = "waiting_for_semester"
                session['pending_intent'] = "course_info"
                return format_response("To provide you with course information, I need to know which semester you're interested in. Please specify the semester number (e.g., 1, 2, 3, etc.).")

        if session.get('stage') == "waiting_for_semester":
            semester = extract_semester(user_input)
            if semester:
                session['stage'] = "normal"
                return get_courses_by_semester(semester)
            else:
                return format_response("I'm sorry, but I couldn't understand the semester number. Please provide a valid semester number (e.g., 1, 2, 3, etc.).")

        if intent == "unknown":
            return get_chatbot_response(user_input)

        logger.warning(f"Unhandled intent: {intent}")
        return format_response("I'm sorry, but I don't have information on that topic. Is there anything else I can help you with regarding your academics?")

    except Exception as e:
        logger.error(f"Error in get_response: {str(e)}", exc_info=True)
        return format_response("I apologize, but an error occurred while processing your request. Please try again later.")

def extract_semester(user_input):
    semester_match = re.search(r'\b(\d+)(?:st|nd|rd|th)?\s*semester\b', user_input, re.IGNORECASE)
    if semester_match:
        return semester_match.group(1)
    return None

def get_chatbot_response(user_input):
    prompt = f"""
    You are Inquiro, an AI powered ChatBot for the Computer Science and Design department at our college . Your primary function is to assist students and faculty with Computer Science related and day to day academic queries like attendance, results, etc. Here are your guidelines:

    1. Focus exclusively on Computer Science topics, including but not limited to programming, algorithms, data structures, software engineering, databases, networking, and AI.
    2. If a query is not related to Computer Science, politely redirect the conversation back to the department's scope.
    3. Provide accurate and helpful information about the department's courses, research areas, and academic activities.
    4. For general greetings or farewells, respond in a friendly manner while maintaining a professional tone.
    5. Our department name is Computer Science and Design. part of PESITM college. If asked about college please refer https://pestrust.edu.in/pesitm/ and respond.
    6. On aksing who created, designed or similar question, inform them that this Chatbot "Inquiro" was developed by Shankar, Sourabh, Sinchana and Supritha, under the guidance of Mr. Manjunath G.
    Now, please respond to the following query:
    {user_input}
    """

    try:
        logger.info(f"Sending query to Gemini API: {user_input[:50]}...")  # Log truncated query for privacy
        response = model.generate_content(prompt)
        logger.info("Successfully received response from Gemini API")
        return format_response(response.text)
    except Exception as e:
        logger.error(f"Error using Gemini API: {e}")
        return format_response("I apologize, but I'm having trouble processing your request. Could you please rephrase your Computer Science related question?")

def handle_intent( intent, usn,semester=None):
    logger.debug(f"Handling intent: {intent} for USN: {usn}")
    try:
        if intent == "attendance":
            return get_student_attendance(usn)
        elif intent == "results":
            return get_student_results(usn)
        elif intent == "schedule":
            return get_class_schedule()
        elif intent == "exams":
            return get_exam_schedule(usn)
        elif intent == "assignments":
            return get_assignments(usn)
        elif intent == "faculty":
            return get_faculty_info()
        elif intent == "events":
            return get_academic_events()
        elif intent == "course_info":
            if semester is None:
                return format_response("Please specify a semester to get course information.")
            return get_courses_by_semester(semester)
        else:
            logger.warning(f"Unknown intent: {intent}")
            return format_response("I'm sorry, but I don't have information on that topic. Is there anything else I can help you with regarding your academics?")
    except Exception as e:
        logger.error(f"Error handling intent {intent}: {str(e)}", exc_info=True)
        return format_response("I apologize, but an error occurred while processing your request. Please try again later.")

def get_student_attendance(usn):
    logger.debug(f"Fetching attendance for USN: {usn}")
    if usn is None:
        return format_response("To fetch your attendance information, I'll need your USN. Please prompt 'set my USN' to set it.")

    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT name, percentage AS attendance FROM students WHERE usn = %s"
        cursor.execute(query, (usn,))
        result = cursor.fetchone()
    except mysql.connector.Error as err:
        logger.error(f"Database error in get_student_attendance: {err}")
        return format_response("I apologize, but I'm having trouble retrieving your attendance information. Please try again later or contact the admin.")
    finally:
        cursor.close()
        connection.close()

    if result:
        attendance = float(result['attendance'])
        if attendance >= 85:
            comment = "Excellent attendance! Keep up the great work!"
            status_class = "excellent"
        elif attendance >= 75:
            comment = "Good job on your attendance. Try to maintain or improve it further."
            status_class = "good"
        else:
            comment = "Your attendance could use some improvement. Consider attending more classes to enhance your learning experience."
            status_class = "needs-improvement"
        
        response_html = f"""
        <div class="attendance-info">
            <h3>Attendance Information</h3>
            <p><strong>Name:</strong> {result['name']}</p>
            <p><strong>USN:</strong> {usn}</p>
            <p><strong>Current Attendance:</strong> <span class="attendance-percentage {status_class}">{attendance:.2f}%</span></p>
            <p><strong>Status:</strong> <span class="attendance-comment">{comment}</span></p>
            <p class="attendance-note">Remember, regular attendance is crucial for academic success. If you have any concerns about your attendance, please speak with your faculty advisor.</p>
        </div>
        """
        
        return format_response(
            response_html,
            options=["Check results", "View class schedule"],
            structured=True
        )
    
    return format_response(f"I'm sorry, but I couldn't find any attendance data for USN {usn}. Please verify if your USN is correct or consult with the CSD office for assistance.")

def get_student_results(usn):
    logger.debug(f"Fetching results for USN: {usn}")
    if usn is None:
        return format_response("To fetch your academic results, I'll need your USN. Please prompt 'set my USN' to set it.")

    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT cgpa, sgpa FROM results WHERE usn = %s"
        cursor.execute(query, (usn,))
        result = cursor.fetchone()
        logger.debug(f"Results query result: fetched")
    except mysql.connector.Error as err:
        logger.error(f"Database error in get_student_results: {err}")
        return format_response("I apologize, but I'm having trouble retrieving your results. Please try again later or contact the admin.")
    finally:
        cursor.close()
        connection.close()

    if result:
        cgpa = float(result['cgpa'])
        sgpa = float(result['sgpa'])
        
        if cgpa >= 9.0:
            comment = "Outstanding performance! Your hard work is truly paying off."
            status_class = "excellent"
        elif cgpa >= 8.0:
            comment = "Excellent work! You're performing very well academically."
            status_class = "very-good"
        elif cgpa >= 7.0:
            comment = "Good job! There's always room for improvement, but you're on the right track."
            status_class = "good"
        else:
            comment = "There's potential for improvement. Consider seeking additional support or tutoring to boost your performance."
            status_class = "needs-improvement"
        
        response_html = f"""
        <div class="results-info">
            <h3>Academic Results</h3>
            <p><strong>USN:</strong> {usn}</p>
            <p><strong>CGPA:</strong> <span class="result-cgpa {status_class}">{cgpa:.2f}</span></p>
            <p><strong>SGPA:</strong> <span class="result-sgpa {status_class}">{sgpa:.2f}</span></p>
            <p><strong>Performance:</strong> <span class="result-comment">{comment}</span></p>
            <p class="result-note">Remember, these scores are just one measure of your academic journey. Keep focusing on learning and growth!</p>
        </div>
        """
        
        return format_response(
            response_html,
            options=["Check attendance", "View class schedule"],
            structured=True
        )
    
    logger.warning(f"No results found for USN: {usn}")
    return format_response(f"I'm sorry, but I couldn't find any academic results for USN {usn}. Please verify if your USN is correct or consult with the examination department for assistance.")

def get_class_schedule():
    logger.debug("Fetching class schedule")
    today = date.today().strftime('%A')
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor(dictionary=True)
        query = ("SELECT time_slot, subject, faculty_name, room_number FROM class_schedule "
                 "WHERE day = %s ORDER BY time_slot")
        cursor.execute(query, (today,))
        results = cursor.fetchall()
        logger.debug(f"Today's class schedule query results: fetched")
    except mysql.connector.Error as err:
        logger.error(f"Database error in get_class_schedule: {err}")
        return format_response("I apologize, but I'm having trouble retrieving today's class schedule. Please try again later or check the official timetable.")
    finally:
        cursor.close()
        connection.close()

    if results:
        response = f"<h3>Today's Class Schedule ({today})</h3>"
        response += "<table class='schedule-table'>"
        response += "<tr><th>Time</th><th>Subject</th><th>Faculty</th><th>Room</th></tr>"
        for class_info in results:
            response += f"<tr>"
            response += f"<td>{class_info['time_slot']}</td>"
            response += f"<td>{class_info['subject']}</td>"
            response += f"<td>{class_info['faculty_name']}</td>"
            response += f"<td>{class_info['room_number']}</td>"
            response += "</tr>"
        response += "</table>"
        
        response += "<p>Note: This schedule is for today only. Always verify with the latest official timetable for any changes.</p>"
        return format_response(response, structured=True)

    logger.info("No classes found for today")
    return format_response(
        f"<h3>Today's Class Schedule ({today})</h3>"
        "<p>There are no classes scheduled for today. Enjoy your free time!</p>",
        structured=True
    )

def get_exam_schedule(usn):
    logger.debug(f"Fetching exam schedule for USN: {usn}")
    if usn is None:
        return format_response("To provide you with exam schedule information, I'll need your USN. Please prompt 'set my USN' to set it.")

    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor(dictionary=True)
        query = ("SELECT subject, exam_date, start_time, end_time, room FROM exams "
                 "WHERE usn = %s AND exam_date >= CURDATE() ORDER BY exam_date, start_time")
        cursor.execute(query, (usn,))
        results = cursor.fetchall()
        logger.debug(f"Exam schedule query results: fetched")
    except mysql.connector.Error as err:
        logger.error(f"Database error in get_exam_schedule: {err}")
        return format_response("I apologize, but I'm having trouble retrieving the exam schedule. Please try again later or check the official examination portal.")
    finally:
        cursor.close()
        connection.close()

    if results:
        response = "<h3>Upcoming Exam Schedule</h3>"
        for exam in results:
            days_until = (exam['exam_date'] - datetime.now().date()).days
            response += f"<div class='exam-info'>"
            response += f"<h4>{exam['subject']}</h4>"
            response += f"<p><strong>Date:</strong> {exam['exam_date'].strftime('%B %d, %Y')} ({days_until} days away)</p>"
            response += f"<p><strong>Time:</strong> {exam['start_time'].strftime('%I:%M %p')} - {exam['end_time'].strftime('%I:%M %p')}</p>"
            response += f"<p><strong>Room:</strong> {exam['room']}</p>"
            response += "</div>"
        response += "<p>Make sure to check the official VTU Examination Portal for any updates: <a href='https://vtu.ac.in/examination/' target='_blank'>VTU Examination Portal</a></p>"
        return format_response(response, structured=True)

    logger.info(f"No upcoming exams found for USN: {usn}")
    return format_response(
        "<h3>Exam Schedule</h3>"
        "<p>Good news! There are no upcoming exams scheduled for you at this time. "
        "However, it's always a good idea to stay prepared.</p>"
        "<p>Keep an eye on the VTU Examination Portal for the most up-to-date information: "
        "<a href='https://vtu.ac.in/examination/' target='_blank'>VTU Examination Portal</a></p>",
        structured=True
    )

def get_assignments(usn):
    logger.debug(f"Fetching assignments for USN: {usn}")
    if usn is None:
        return format_response("To provide you with assignment information, I'll need your USN. Please prompt 'set my USN' to set it.")

    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor(dictionary=True)
        query = ("SELECT subject, due_date, submission_status FROM assignments "
                 "WHERE usn = %s AND due_date >= CURDATE() ORDER BY due_date")
        cursor.execute(query, (usn,))
        results = cursor.fetchall()
        logger.debug(f"Assignments query results: fetched")
    except mysql.connector.Error as err:
        logger.error(f"Database error in get_assignments: {err}")
        return format_response("I apologize, but I'm having trouble retrieving your assignment information. Please try again later or check with your course instructors.")
    finally:
        cursor.close()
        connection.close()

    if results:
        response = "<h3>Current Assignments</h3>"
        for assignment in results:
            days_until = (assignment['due_date'] - datetime.now().date()).days
            response += f"<div class='assignment-info'>"
            response += f"<h4>{assignment['subject']}</h4>"
            response += f"<p><strong>Due Date:</strong> {assignment['due_date'].strftime('%B %d, %Y')} ({days_until} days left)</p>"
            response += f"<p><strong>Status:</strong> {assignment['submission_status']}</p>"
            response += "</div>"
        response += "<p>Remember to submit your assignments on time. If you need any clarification, don't hesitate to ask your instructors!</p>"
        return format_response(response, structured=True)

    logger.info(f"No pending assignments found for USN: {usn}")
    return format_response(
        "<h3>Assignments</h3>"
        "<p>Great news! You don't have any pending assignments at the moment. "
        "This might be a good time to get ahead on your studies or work on personal projects.</p>"
        "<p>Keep checking regularly for new assignments, and stay proactive in your learning!</p>",
        structured=True
    )

def get_faculty_info():
    logger.debug("Fetching faculty information")
    if 'faculty_info' not in cache:
        try:
            connection = connection_pool.get_connection()
            cursor = connection.cursor(dictionary=True)
            query = ("SELECT faculty_name, subject, email, phone FROM faculty")
            cursor.execute(query)
            results = cursor.fetchall()
            cache['faculty_info'] = results
            logger.debug("Faculty information cached")
        except mysql.connector.Error as err:
            logger.error(f"Database error in get_faculty_info: {err}")
            return format_response("I apologize, but I'm having trouble retrieving the faculty information. Please try again later or check the department website.")
        finally:
            cursor.close()
            connection.close()

    faculty_info = cache['faculty_info']
    if faculty_info:
        response = "<h3>CSD Department Faculty Information</h3>"
        for faculty in faculty_info:
            response += f"<div class='faculty-info'>"
            response += f"<h4>{faculty['faculty_name']}</h4>"
            response += f"<p><strong>Subject:</strong> {faculty['subject']}</p>"
            response += f"<p><strong>Email:</strong> {faculty['email']}</p>"
            response += f"<p><strong>Phone:</strong> {faculty['phone']}</p>"
            response += "</div>"
        response += "<p>For more detailed information about our faculty members, including their research interests and publications, "
        response += "please visit our department's Faculty Page: <a href='https://pestrust.edu.in/pesitm/branch/Computer-Science-and-Design' target='_blank'>CSD Faculty Page</a></p>"
        return format_response(response, structured=True)

    logger.warning("No faculty information found")
    return format_response(
        "<h3>Faculty Information</h3>"
        "<p>I apologize, but I couldn't retrieve the faculty information at this moment. "
        "Please check with the department office or visit our Faculty Page for the most up-to-date information: "
        "<a href='https://pestrust.edu.in/pesitm/branch/Computer-Science-and-Design' target='_blank'>CSD Faculty Page</a></p>",
        structured=True
    )

def get_academic_events():
    logger.debug("Fetching academic events")
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor(dictionary=True)
        query = ("SELECT event_name, event_date, description FROM events "
                 "WHERE event_date >= CURDATE() ORDER BY event_date LIMIT 5")
        cursor.execute(query)
        results = cursor.fetchall()
        logger.debug(f"Academic events query results: fetched")
    except mysql.connector.Error as err:
        logger.error(f"Database error in get_academic_events: {err}")
        return format_response("I apologize, but I'm having trouble retrieving the academic events. Please try again later or check the department notice board.")
    finally:
        cursor.close()
        connection.close()

    if results:
        response = "<h3>Upcoming Academic Events</h3>"
        for event in results:
            days_until = (event['event_date'] - datetime.now().date()).days
            response += f"<div class='event-info'>"
            response += f"<h4>{event['event_name']}</h4>"
            response += f"<p><strong>Date:</strong> {event['event_date'].strftime('%B %d, %Y')} ({days_until} days away)</p>"
            response += f"<p><strong>Description:</strong> {event['description']}</p>"
            response += "</div>"
        response += "<p>Stay tuned for more exciting events! For full details and registration information, "
        response += "check our Events Page: <a href='https://pestrust.edu.in/pesitm/branch/Computer-Science-and-Design#fifth' target='_blank'>CSD Events Page</a></p>"
        return format_response(response, structured=True)

    logger.info("No upcoming academic events found")
    return format_response(
        "<h3>Academic Events</h3>"
        "<p>There are no upcoming academic events scheduled at this time. "
        "We regularly update our event calendar, so check back soon for exciting opportunities!</p>"
        "<p>You can always visit our Events Page for the latest updates: "
        "<a href='https://pestrust.edu.in/pesitm/branch/Computer-Science-and-Design#fifth' target='_blank'>CSD Events Page</a></p>",
        structured=True
    )

def get_courses_by_semester(semester):
    logger.debug(f"Fetching courses for semester: {semester}")
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT subject_name, subject_code, credits FROM courses WHERE semester = %s"
        cursor.execute(query, (semester,))
        results = cursor.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Database error in get_courses_by_semester: {err}")
        return format_response("I apologize, but I'm having trouble retrieving the course information. Please try again later.")
    finally:
        cursor.close()
        connection.close()

    if results:
        response = f"<h3>Courses for Semester {semester}</h3>"
        for course in results:
            response += f"<p><strong>{course['subject_code']}</strong> - {course['subject_name']} ({course['credits']} Credits)</p>"
        return format_response(response, structured=True)
    
    return format_response(f"No courses found for semester {semester}.")

@app.route('/ping')
def ping():
    return "pong"

@app.route('/timetable')
def timetable():
    return send_from_directory('.', 'timetable.html')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    logger.debug("Received chat request")
    user_input = request.json.get('message')
    
    logger.debug(f"User input: {user_input}")
    
    if not user_input or not isinstance(user_input, str):
        logger.warning("Invalid input received")
        return jsonify(format_response('I apologize, but I received an invalid input. Could you please try again?'))

    try:
        response = get_response(user_input, session.sid)
        logger.debug(f"Generated response: {response}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        return jsonify(format_response('I apologize, but an error occurred while processing your request. Please try again later.'))

@app.route('/test_db')
def test_db():
    try:
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        return jsonify({"status": "success", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    
@app.route('/test_intent/<intent>')
def test_intent(intent):
    try:
        response = handle_intent(intent, "sample_usn")
        return jsonify({"status": "success", "response": response})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)