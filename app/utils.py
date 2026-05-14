# app/utils.py  (replace or merge with earlier utils)
import json
from collections import defaultdict
import os
import google.generativeai as genai
from googleapiclient.discovery import build
from datetime import datetime
import os
import requests
from urllib.parse import urlencode

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def grade_attempt(questions, answers_map):
    total = len(questions)
    correct = 0
    per_q = {}
    topic_stats = defaultdict(lambda: {'correct':0,'total':0})
    for q in questions:
        qid = q.id
        chosen = answers_map.get(str(qid))
        is_correct = False
        if chosen is not None:
            try:
                if int(chosen) == int(q.correct_index):
                    is_correct = True
            except:
                is_correct = False
        per_q[qid] = is_correct
        if is_correct:
            correct += 1
            topic_stats[q.topic]['correct'] += 1
        topic_stats[q.topic]['total'] += 1
    score = (correct/total)*100 if total>0 else 0
    return score, per_q, topic_stats

def find_weak_topics(topic_stats, threshold=0.6):
    weak = []
    for t, s in topic_stats.items():
        rate = s['correct']/s['total'] if s['total']>0 else 0
        if rate < threshold:
            weak.append((t, rate))
    weak.sort(key=lambda x: x[1])
    return weak

# ---------------- AI Driven video recommendation ----------------
def gemini_generate_query(topic, sample_question_texts):
    """
    Ask Gemini to produce a short YouTube search query for the topic + sample question context.
    Keep it short and focused.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    prompt = (
        f"You are an assistant that creates concise YouTube search queries for educational videos.\n"
        f"Topic: {topic}\n"
        f"Example student questions (short): {sample_question_texts}\n\n"
        "Give 1 concise search query (3-6 words) that will return quality tutorial/video for a college-level engineering student.\n"
        "ONLY return the query on one line, nothing else."
    )
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        resp = model.generate_content(prompt)
        text = resp.text.strip()
        # sanitize
        query = text.splitlines()[0]
        return query
    except Exception as e:
        print("DEBUG: Gemini query generation error:", e)
        return topic

def youtube_search_top_video(query, max_results=3):
    """
    Use YouTube Data API to search; return top video URL or None.
    """
    if YOUTUBE_API_KEY is None:
        raise RuntimeError("YOUTUBE_API_KEY not set")
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    req = youtube.search().list(part='snippet', q=query, type='video', maxResults=max_results, order='relevance')
    res = req.execute()
    items = res.get('items', [])
    if not items:
        return None
    # choose top item
    vid = items[0]['id']['videoId']
    return f"https://www.youtube.com/watch?v={vid}"

def recommend_video_for_topic_ai(topic, sample_questions=None):
    # DEBUG version: prints detailed info to Flask terminal
    from urllib.parse import urlencode
    import requests
    print("DEBUG: recommend_video_for_topic_ai called with topic:", repr(topic))
    print("DEBUG: YOUTUBE_API_KEY present?:", bool(YOUTUBE_API_KEY))
    if not YOUTUBE_API_KEY:
        print("DEBUG: Missing YOUTUBE_API_KEY -> returning None")
        return None

    # Build a helpful query string
    q = topic
    if sample_questions:
        try:
            # Let's use gemini to generate the query!
            sample_texts = [sq for sq in (sample_questions[:3] or [])]
            if GEMINI_API_KEY:
                q = gemini_generate_query(topic, sample_texts)
                print("DEBUG: Gemini generated query:", q)
            else:
                q += " " + " ".join([" ".join(sq.split()[:6]) for sq in (sample_texts)])
        except Exception as ex:
            print("DEBUG: sample_questions processing error:", ex)

    params = {
        "part": "snippet",
        "q": q,
        "type": "video",
        "maxResults": 5,
        "key": YOUTUBE_API_KEY,
        "safeSearch": "strict"
    }
    url = "https://www.googleapis.com/youtube/v3/search?" + urlencode(params)
    print("DEBUG: request URL (short):", url[:200] + ("..." if len(url)>200 else ""))

    try:
        r = requests.get(url, timeout=10)
        print("DEBUG: HTTP status:", r.status_code)
        data = r.json()
        print("DEBUG: response keys:", list(data.keys()))
        items = data.get("items", [])
        print("DEBUG: items count:", len(items))
        if not items:
            print("DEBUG: No items from YouTube -> returning None")
            return None
        first = items[0]
        print("DEBUG: first item keys:", list(first.keys()))
        vid = None
        # robust extraction
        idobj = first.get("id", {})
        vid = idobj.get("videoId") or idobj.get("playlistId")
        if not vid:
            print("DEBUG: couldn't find videoId in first item ->", idobj)
            return None
        yurl = f"https://www.youtube.com/watch?v={vid}"
        print("DEBUG: RETURNING URL:", yurl)
        return yurl
    except Exception as e:
        print("DEBUG: youtube search failed:", e)
        return None


# ---------------- Gamification helpers ----------------
def award_xp_and_badges(user, score, db_session):
    """
    Basic rules:
      - XP awarded = floor(score)
      - Bonus for high score
      - Level formula: level = int(xp / 500) + 1
      - Badges: thresholds (50, 75, 90, 99)
    Mutates user object (points->xp, badges json).
    """
    xp_gain = int(score)
    # store xp in points (we used points earlier); rename conceptually to xp
    user.points = (user.points or 0) + xp_gain

    # badges handling
    try:
        badges = json.loads(user.badges or "[]")
    except:
        badges = []

    new_badges = []
    if score >= 99 and "Perfectionist" not in badges:
        new_badges.append("Perfectionist")
    elif score >= 90 and "Ace" not in badges:
        new_badges.append("Ace")
    elif score >= 75 and "Proficient" not in badges:
        new_badges.append("Proficient")
    elif score >= 50 and "Learner" not in badges:
        new_badges.append("Learner")

    if new_badges:
        badges.extend(new_badges)
        user.badges = json.dumps(list(set(badges)))

    # level & xp -> simple derivation
    user.xp = getattr(user, 'xp', 0) + xp_gain
    user.level = int(user.xp / 500) + 1
    db_session.commit()
    return xp_gain, new_badges

# ---------------- CHATBOT KNOWLEDGE BASE ----------------

CHATBOT_QA = {
    # --- Assessment & attempt rules ---
    "how many attempts": "You can take each assessment only once. This helps ensure fairness and accurate evaluation of your understanding.",
    "can i retake the assessment": "Assessments are single-attempt only. If you need a reset, please contact your teacher.",
    "when is my next assessment": "Upcoming assessments are shown in your dashboard under the Assessments section.",
    "what is an assessment": "An assessment is a set of multiple-choice questions created by your teacher to evaluate your understanding of a topic.",
    "how does grading work": "Grading is automatic. The system checks your answers, calculates your score, and identifies weak topics instantly.",

    # --- Remediation & video help ---
    "what is remediation": "Remediation is a short learning video recommended based on your weak topic. Completing it helps you improve quickly.",
    "why is my video not playing": "Try refreshing the page or checking your internet connection. If the issue continues, inform your teacher.",
    "why do i have to watch the video": "The system recommends videos to strengthen your weak topics. Completing them unlocks remediation progress.",
    "video recommendation": "Videos are recommended automatically using topic detection and YouTube search for relevant tutorials.",

    # --- XP, leveling & badges ---
    "what is xp": "XP (experience points) are earned by completing assessments. More XP helps you level up.",
    "how do levels work": "Your level increases based on total XP. Each 500 XP adds a new level.",
    "how to earn badges": "Badges are awarded for achieving score milestones like 50%, 75%, 90%, and 99%.",
    "what is my level": "You can view your current level and XP on your dashboard.",
    "how to get more xp": "Complete assessments and remediation to earn more XP and level up.",

    # --- Leaderboard ---
    "what is the leaderboard": "The leaderboard shows the top students based on XP. It encourages healthy competition.",
    "how to reach top in leaderboard": "Earn more XP by scoring well, completing assessments, and finishing remediation videos.",
    "why am i not on leaderboard": "You may need more XP to appear in the top rankings.",

    # --- Login & accounts ---
    "i forgot my password": "Ask your teacher or admin to reset your password.",
    "i cannot login": "Check your username and password carefully. If the problem continues, contact your teacher.",
    "how to create account": "Only admins/teachers can create student accounts.",
    "why is login page empty": "If something looks off, refresh the page or clear cache.",

    # --- Subjects & teachers ---
    "who added the questions": "Your teacher adds and manages questions for each subject.",
    "which subjects do i have": "Your subjects appear automatically on your dashboard.",
    "how do i change subject": "Subjects are managed by teachers. You cannot change them manually.",

    # --- Camera proctoring ---
    "why is camera on": "Camera is used for proctoring to reduce malpractice and ensure fairness during assessments.",
    "can i disable the camera": "Camera cannot be disabled during assessments. It is required for monitoring.",
    "why did i get a warning": "Warnings appear if you look away from the screen. Stay focused to avoid alerts.",

    # --- General help ---
    "hello": "Hello! How can I assist you today?",
    "hi": "Hi! What would you like help with?",
    "who are you": "I’m your learning assistant. I help with queries about assessments, XP, videos, and platform features.",
    "thank you": "You're welcome! Let me know if you need anything else.",
    "bye": "Goodbye! Study well and all the best!",
}


def chatbot_answer(q: str):
    q_low = q.lower().strip()

    # Exact or partial matching
    for key in CHATBOT_QA:
        if key in q_low:
            return CHATBOT_QA[key]

    # Fallback checks
    if "assessment" in q_low:
        return "Assessments appear in your dashboard. You can attempt each one only once."

    if "video" in q_low:
        return "Videos are recommended based on your weak topics."

    if "xp" in q_low or "points" in q_low:
        return "XP helps you level up. Earn XP by completing assessments."

    if "teacher" in q_low:
        return "Your teacher manages subjects and assessments."

    # Final fallback
    return "I'm not sure about that yet. Try asking about assessments, XP, videos, or camera rules."
