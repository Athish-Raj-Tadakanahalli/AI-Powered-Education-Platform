# app/utils.py  (replace or merge with earlier utils)
import json
from collections import defaultdict
import os
from datetime import datetime
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

# Optional AI imports — guard so app can run without them installed
try:
    import google.generativeai as genai
    GEMINI_LIB_AVAILABLE = True
except Exception:
    genai = None
    GEMINI_LIB_AVAILABLE = False

try:
    from googleapiclient.discovery import build
    GOOGLEAPI_AVAILABLE = True
except Exception:
    build = None
    GOOGLEAPI_AVAILABLE = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
if GEMINI_API_KEY and GEMINI_LIB_AVAILABLE:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        pass
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
    if not GEMINI_API_KEY or not GEMINI_LIB_AVAILABLE:
        raise RuntimeError("Gemini not configured or library not available")

    prompt = (
        f"You are an assistant that creates concise YouTube search queries for educational videos.\n"
        f"Topic: {topic}\n"
        f"Example student questions (short): {sample_question_texts}\n\n"
        "Give 1 concise search query (3-6 words) that will return quality tutorial/video for a college-level engineering student.\n"
        "ONLY return the query on one line, nothing else."
    )
    
    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        resp = model.generate_content(prompt)
        text = resp.text.strip()
        query = text.splitlines()[0]
        return query
    except Exception as e:
        print("DEBUG: Gemini query generation error:", e)
        return topic

def youtube_search_top_video(query, max_results=3):
    """
    Use YouTube Data API to search; return top video URL or None.
    """
    if YOUTUBE_API_KEY is None or not GOOGLEAPI_AVAILABLE:
        raise RuntimeError("YouTube API client not configured or library missing")
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    req = youtube.search().list(part='snippet', q=query, type='video', maxResults=max_results, order='relevance')
    res = req.execute()
    items = res.get('items', [])
    if not items:
        return None
    # choose top item
    vid = items[0]['id']['videoId']
    return f"https://www.youtube.com/watch?v={vid}"

VIDEO_CACHE = {}

FAST_TOPIC_VIDEOS = {
    "stack": "https://www.youtube.com/watch?v=tqQ5fTamIN4",
    "stack data structure": "https://www.youtube.com/watch?v=tqQ5fTamIN4",
    "recursion": "https://www.youtube.com/watch?v=IJDJ0kBx2LM",
    "dbms": "https://www.youtube.com/watch?v=24MN6dC05Dk",
    "dbms acid properties": "https://www.youtube.com/watch?v=24MN6dC05Dk",
    "oops": "https://www.youtube.com/watch?v=pTB0EiLXUC8",
    "object oriented programming": "https://www.youtube.com/watch?v=pTB0EiLXUC8",
    "data structure algorithm": "https://www.youtube.com/watch?v=wjFgd8JJ8NM",
    "computer networks": "https://www.youtube.com/watch?v=F00VbX4kEog",
    "computer networks transport layer": "https://www.youtube.com/watch?v=F00VbX4kEog",
    "computer networks tcp protocol": "https://www.youtube.com/watch?v=vJNyY14q92U",
    "operating systems": "https://www.youtube.com/watch?v=26QPDBe-NB8",
    "operating systems deadlock": "https://www.youtube.com/watch?v=rLyYb7BFgQI",
    "graph algorithms shortest path": "https://www.youtube.com/watch?v=EFg3u_E6eHU",
    "queue": "https://www.youtube.com/watch?v=tqQ5fTamIN4",
    "linked list": "https://www.youtube.com/watch?v=njTh_OwMljA",
    "binary search tree": "https://www.youtube.com/watch?v=f5dU33C67w0",
    "sorting algorithms": "https://www.youtube.com/watch?v=Kg4qnEAjLYs",
    "python programming": "https://www.youtube.com/watch?v=rfscVs0vtbw",
    "sql queries": "https://www.youtube.com/watch?v=HXV3zeQKqGY"
}

def _persist_video_to_db(topic_name, youtube_url):
    """Helper to save newly discovered topic videos to TopicVideo table."""
    try:
        from app.models import TopicVideo, db
        tv = TopicVideo.query.filter(TopicVideo.topic.ilike(topic_name.strip())).first()
        if not tv:
            tv = TopicVideo(topic=topic_name.strip(), youtube_url=youtube_url)
            db.session.add(tv)
            db.session.commit()
    except Exception:
        pass

def recommend_video_for_topic_ai(topic, sample_questions=None):
    """
    Multi-tier video recommendation strategy optimized for 0ms - <1s execution:
    1. Check global VIDEO_CACHE in-memory (0ms).
    2. Check FAST_TOPIC_VIDEOS dictionary (0ms).
    3. Check TopicVideo table in DB (1ms).
    4. Fast query construction (avoids redundant Gemini calls if topic is descriptive).
    5. YouTube Data API (v3) or HTML search scraping with tight timeouts (1.5s).
    6. Fallback YouTube search results page URL.
    Auto-persists fetched video URLs to memory and DB.
    """
    if not topic:
        return None

    topic_clean = topic.strip().lower()

    # Step 0a: In-Memory Cache Lookup (0ms)
    if topic_clean in VIDEO_CACHE:
        return VIDEO_CACHE[topic_clean]

    # Step 0b: Fast in-memory dictionary lookup (0ms)
    if topic_clean in FAST_TOPIC_VIDEOS:
        VIDEO_CACHE[topic_clean] = FAST_TOPIC_VIDEOS[topic_clean]
        return FAST_TOPIC_VIDEOS[topic_clean]

    # Partial match in fast dictionary
    for k, v in FAST_TOPIC_VIDEOS.items():
        if k in topic_clean or topic_clean in k:
            VIDEO_CACHE[topic_clean] = v
            return v

    # Step 1: Check DB TopicVideo mapping
    try:
        from app.models import TopicVideo
        tv = TopicVideo.query.filter(TopicVideo.topic.ilike(topic.strip())).first()
        if tv and tv.youtube_url:
            VIDEO_CACHE[topic_clean] = tv.youtube_url
            return tv.youtube_url
    except Exception:
        pass

    # Step 2: Build search query cleanly (Skip Gemini unless topic is very short/vague)
    q = topic.strip()
    words = q.split()
    if len(words) < 2 and sample_questions:
        try:
            sample_texts = [sq for sq in (sample_questions[:2] or []) if sq]
            if sample_texts and GEMINI_API_KEY and GEMINI_API_KEY != "your-gemini-api-key-here" and GEMINI_LIB_AVAILABLE:
                q = gemini_generate_query(topic, sample_texts)
            elif sample_texts:
                q += " " + " ".join(sample_texts[0].split()[:4])
        except Exception:
            pass

    search_query = f"{q} tutorial educational"

    # Step 3: Try YouTube Data API v3 (if key is valid)
    found_url = None
    if YOUTUBE_API_KEY and YOUTUBE_API_KEY.strip() != "your-youtube-api-key-here":
        try:
            params = {
                "part": "snippet",
                "q": search_query,
                "type": "video",
                "maxResults": 3,
                "key": YOUTUBE_API_KEY,
                "safeSearch": "strict"
            }
            url = "https://www.googleapis.com/youtube/v3/search?" + urlencode(params)
            r = requests.get(url, timeout=1.5)
            if r.status_code == 200:
                data = r.json()
                items = data.get("items", [])
                if items:
                    vid = items[0].get("id", {}).get("videoId")
                    if vid:
                        found_url = f"https://www.youtube.com/watch?v={vid}"
        except Exception:
            pass

    # Step 4: Direct YouTube Search HTML scraping (tight 1.5s timeout)
    if not found_url:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            }
            from urllib.parse import quote_plus
            yt_search_url = f"https://www.youtube.com/results?search_query={quote_plus(search_query)}"
            r = requests.get(yt_search_url, headers=headers, timeout=1.5)
            if r.status_code == 200:
                import re
                vids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', r.text)
                if vids:
                    found_url = f"https://www.youtube.com/watch?v={vids[0]}"
        except Exception:
            pass

    # Step 5: Fallback to YouTube search URL if fetching failed
    if not found_url:
        from urllib.parse import quote_plus
        found_url = f"https://www.youtube.com/results?search_query={quote_plus(search_query)}"
    else:
        # Save valid fetched YouTube video URL to cache and database table
        VIDEO_CACHE[topic_clean] = found_url
        _persist_video_to_db(topic, found_url)

    return found_url


from concurrent.futures import ThreadPoolExecutor

def batch_recommend_videos(items, max_workers=5):
    """
    Fetch video recommendations in parallel using a ThreadPoolExecutor.
    'items' can be a list of dicts: [{'topic': ..., 'question_text': ...}, ...]
    Returns a list of video_url strings corresponding to each item.
    """
    if not items:
        return []

    def _fetch_single(item):
        if isinstance(item, dict):
            topic = item.get("topic", "")
            q_text = item.get("question_text", "")
            return recommend_video_for_topic_ai(topic, [q_text] if q_text else None)
        elif isinstance(item, (tuple, list)):
            topic = item[0]
            q_text = item[1] if len(item) > 1 else ""
            return recommend_video_for_topic_ai(topic, [q_text] if q_text else None)
        elif isinstance(item, str):
            return recommend_video_for_topic_ai(item)
        return None

    with ThreadPoolExecutor(max_workers=min(len(items), max_workers)) as executor:
        results = list(executor.map(_fetch_single, items))

    return results

def batch_generate_study_hub(weak_topics, max_workers=3):
    """
    Generate study hub content for multiple weak topics in parallel.
    'weak_topics' can be a list of (topic, rate) tuples or topic strings.
    Returns a dict mapping topic -> hub_data.
    """
    if not weak_topics:
        return {}

    topics = [wt[0] if isinstance(wt, (tuple, list)) else wt for wt in weak_topics]

    def _gen_single(topic):
        try:
            return topic, generate_study_hub_content(topic)
        except Exception as e:
            return topic, None

    study_hub = {}
    with ThreadPoolExecutor(max_workers=min(len(topics), max_workers)) as executor:
        results = executor.map(_gen_single, topics)
        for topic, hub_data in results:
            if hub_data:
                study_hub[topic] = hub_data

    return study_hub


# ---------------- Gamification helpers ----------------
def award_xp_and_badges(user, score, db_session):
    """
    Basic rules:
      - XP awarded = floor(score)
      - Bonus for high score
      - Level formula: level = int(xp / 500) + 1
      - Badges: thresholds (50, 75, 90, 99)
      - Level-up detection and rewards
    Mutates user object (points->xp, badges json).
    Returns: (xp_gain, new_badges, leveled_up, old_level, new_level)
    """
    xp_gain = int(score)
    old_level = user.level or 1

    # store xp in points (sync total XP)
    user.points = (user.points or 0) + xp_gain

    # badges handling
    try:
        badges = json.loads(user.badges or "[]")
    except Exception:
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
    new_level = int(user.xp / 500) + 1
    leveled_up = new_level > old_level
    user.level = new_level

    # Level-up bonus: award a streak freeze on level up!
    if leveled_up:
        user.streak_freeze = (user.streak_freeze or 0) + 1

    db_session.commit()
    return xp_gain, new_badges, leveled_up, old_level, new_level


def update_streak(user, db_session):
    """
    Updates the user's consecutive day streak with Streak Freeze shield protection.
    Called when a student logs in or completes an assessment.
    Returns:
      - (bool) True if streak was updated/incremented/protected/reset, False if same day
      - (int) bonus_xp awarded (if any)
      - (list) new_badges awarded (if any)
      - (bool) freeze_used True if a streak freeze saved the streak
    """
    now = datetime.utcnow().date()
    
    if not user.last_active:
        # First time active
        user.streak = 1
        user.last_active = datetime.utcnow()
        if not hasattr(user, 'streak_freeze') or user.streak_freeze is None:
            user.streak_freeze = 1
        db_session.commit()
        return True, 0, [], False
        
    last_active_date = user.last_active.date()
    delta = (now - last_active_date).days
    
    if delta == 0:
        # Already active today, no change to streak
        return False, 0, [], False
    elif delta == 1:
        # Consecutive day! Increment streak
        user.streak = (user.streak or 0) + 1
        user.last_active = datetime.utcnow()
        
        bonus_xp = 0
        new_badges = []
        
        # Streaks rewards:
        # 3-day streak: 50 XP
        # 7-day streak: 150 XP + "7-Day Streak" badge + 1 Streak Freeze
        # 15-day streak: 300 XP + "15-Day Streak" badge + 1 Streak Freeze
        # 30-day streak: 500 XP + "Streak Master" badge + 1 Streak Freeze
        if user.streak == 3:
            bonus_xp = 50
        elif user.streak == 7:
            bonus_xp = 150
            new_badges.append("7-Day Streak")
            user.streak_freeze = (user.streak_freeze or 0) + 1
        elif user.streak == 15:
            bonus_xp = 300
            new_badges.append("15-Day Streak")
            user.streak_freeze = (user.streak_freeze or 0) + 1
        elif user.streak >= 30 and user.streak % 30 == 0:
            bonus_xp = 500
            new_badges.append("Streak Master")
            user.streak_freeze = (user.streak_freeze or 0) + 1
            
        if bonus_xp:
            user.xp = (user.xp or 0) + bonus_xp
            user.points = (user.points or 0) + bonus_xp  # sync points (total XP)
            user.level = int(user.xp / 500) + 1
            
        if new_badges:
            try:
                badges = json.loads(user.badges or "[]")
            except Exception:
                badges = []
            badges.extend(new_badges)
            user.badges = json.dumps(list(set(badges)))
            
        db_session.commit()
        return True, bonus_xp, new_badges, False
    elif delta == 2 and getattr(user, 'streak_freeze', 0) > 0:
        # Missed 1 day, but saved by Streak Freeze!
        user.streak_freeze -= 1
        user.streak = (user.streak or 0) + 1
        user.last_active = datetime.utcnow()
        db_session.commit()
        return True, 0, [], True
    else:
        # Streak broken! Reset to 1
        user.streak = 1
        user.last_active = datetime.utcnow()
        db_session.commit()
        return True, 0, [], False


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


def chatbot_answer(q: str, context: str = None):
    # Try using Gemini first if configured
    if GEMINI_API_KEY and GEMINI_LIB_AVAILABLE:
        try:
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            system_prompt = (
                "You are an intelligent, supportive AI Student Assistant for an online education and assessment platform.\n"
                "Your goal is to help students understand academic concepts, generate study notes, explain questions, and guide them.\n\n"
                "Platform rules and info for reference:\n"
                "- Assessments are single-attempt only. Students cannot retake them unless reset by a teacher.\n"
                "- Remediation videos are recommended automatically based on weak topics (performance below 60%).\n"
                "- XP is earned from scoring on assessments. Each 500 XP increases the student's Level.\n"
                "- Badges are awarded for milestones: Learner (>=50%), Proficient (>=75%), Ace (>=90%), Perfectionist (>=99%).\n"
                "- Proctoring is active during tests to maintain fairness. Warnings are logged if they look away.\n\n"
            )
            if context:
                system_prompt += f"Current student context:\n{context}\n\n"
            
            prompt = f"{system_prompt}Student Question: {q}\n\nProvide a friendly, extremely concise, and direct response. Keep it brief (maximum of 2-3 short paragraphs or 3-4 bullet points, under 100 words). Use simple markdown for lists or bold text."
            resp = model.generate_content(prompt)
            return resp.text.strip()
        except Exception as e:
            print("Gemini chatbot error:", e)
            # fallback to rule-based below
    
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


def generate_study_hub_content(topic: str):
    """
    Generate study summary, key terms, and flashcards for a specific weak topic using Gemini.
    Returns a dictionary instantly if API key is not configured.
    """
    fallback_content = {
        "summary": f"<li>Review key concepts and core principles related to {topic}.</li><li>Focus on foundational formulas, step-by-step logic, and problem-solving techniques.</li><li>Practice past assessment questions for {topic} to improve retention.</li>",
        "key_terms": [
            {"term": topic, "definition": f"Core engineering and computer science topic evaluated in the assessment."},
            {"term": "Key Principles", "definition": "Fundamental rules, laws, and logical structures governing this subject area."}
        ],
        "flashcards": [
            {"front": f"What is the main focus of {topic}?", "back": f"Understanding foundational concepts, operations, and application of {topic}."},
            {"front": f"Why is {topic} important in engineering?", "back": f"It forms a core building block for problem solving and software architectural design."},
            {"front": f"How to master {topic}?", "back": "Consistently review definitions, practice problems, and study recommended tutorial videos."}
        ]
    }

    if not GEMINI_API_KEY or GEMINI_API_KEY == "your-gemini-api-key-here" or not GEMINI_LIB_AVAILABLE:
        return fallback_content
    
    prompt = (
        f"You are a college-level tutor specializing in engineering subjects.\n"
        f"Generate a study guide for the topic: '{topic}'\n\n"
        "Provide your response in JSON format matching the following structure:\n"
        "{\n"
        '  "summary": "A concise, high-quality bulleted summary (3-5 points, using HTML list items <li>...</li>) of the most important concepts for this topic.",\n'
        '  "key_terms": [\n'
        '    {"term": "Name of Term 1", "definition": "Clear, concise definition of Term 1"},\n'
        '    {"term": "Name of Term 2", "definition": "Clear, concise definition of Term 2"}\n'
        "  ],\n"
        '  "flashcards": [\n'
        '    {"front": "A conceptual question or key concept for front of flashcard 1", "back": "A concise, detailed answer or explanation for back of flashcard 1"},\n'
        '    {"front": "A conceptual question or key concept for front of flashcard 2", "back": "A concise, detailed answer or explanation for back of flashcard 2"},\n'
        '    {"front": "A conceptual question or key concept for front of flashcard 3", "back": "A concise, detailed answer or explanation for back of flashcard 3"}\n'
        "  ]\n"
        "}\n\n"
        "Make sure the response is valid JSON, strictly matches the schema, and does not contain any wrapping code blocks like ```json."
    )
    
    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        resp = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(resp.text.strip())
        return data
    except Exception as e:
        print(f"Error generating study hub content for topic '{topic}':", e)
        # return a default/fallback structure so it doesn't fail
        return {
            "summary": f"<li>Review key concepts related to {topic}.</li><li>Focus on core principles, formulas, and practice problems.</li>",
            "key_terms": [
                {"term": topic, "definition": f"Core engineering topic evaluated in the assessment."}
            ],
            "flashcards": [
                {"front": f"What is the main focus of {topic}?", "back": f"Study the foundational concepts and formulas of {topic}."}
            ]
        }


def generate_question_explanation(question_text: str, student_answer: str, correct_answer: str):
    """
    Generate a step-by-step breakdown of why a question was answered incorrectly,
    and why the correct choice is correct.
    """
    # High-quality local explanations for the existing questions in the database
    local_explanations = {
        "string are mutable or not?": "Strings are immutable because their characters cannot be modified after they are created.",
        "string index starts from?": "Python strings use zero-based indexing, meaning the first character starts at index 0.",
        "what is the maximum number of children a node can have in a binary tree?": "Binary trees restrict each node to a maximum of two children, left and right.",
        "which data structure follows the last in, first out (lifo) rule?": "A stack follows LIFO, where the last added item is the first removed.",
        "which data structure is best suited for implementing recursion?": "Recursion uses a call stack to keep track of active function calls in LIFO order.",
        "in dbms what d stands for?": "In DBMS, D stands for Database, which stores and manages structured digital information.",
        "which dataset follows fifo": "A queue follows First-In-First-Out, processing items in the exact order they arrive."
    }

    q_clean = question_text.strip().lower()
    
    # Check if we have a pre-defined local explanation
    fallback_exp = None
    if q_clean in local_explanations:
        fallback_exp = local_explanations[q_clean]
    else:
        # Generate a generic 12-word fallback
        fallback_exp = f"Correct answer is {correct_answer}, while choice {student_answer} is incorrect. Please study this."
        words = fallback_exp.split()
        if len(words) > 15:
            fallback_exp = f"Correct answer is {correct_answer}, while student's choice {student_answer} was incorrect."

    # If the user has a valid API key configured, we still try Gemini first
    if GEMINI_API_KEY and GEMINI_API_KEY != "your-gemini-api-key-here" and GEMINI_LIB_AVAILABLE:
        prompt = (
            f"You are a college engineering professor explaining an exam question to a student.\n\n"
            f"Question: {question_text}\n"
            f"Student's Answer: {student_answer}\n"
            f"Correct Answer: {correct_answer}\n\n"
            "In a friendly and educational tone, explain why the correct answer is correct and why the student's answer is incorrect.\n"
            "You MUST keep the entire explanation strictly between 10 to 15 words. Do not use any headings, bullet points, or introductory phrases."
        )
        try:
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            resp = model.generate_content(prompt)
            explanation = resp.text.strip()
            if explanation:
                return explanation
        except Exception as e:
            print("Error generating question explanation with Gemini:", e)
            
    # Return the fallback explanation
    return fallback_exp


# ============================================================================
# 5-DOMAIN KNOWLEDGE RADAR CHART & COURSE SKILL TREE ENGINE
# ============================================================================

RADAR_DOMAINS = [
    "Syntax & Fundamentals",
    "Problem Solving & Logic",
    "Data Structures & Storage",
    "Networking & Systems",
    "Software Theory & OOP"
]

DOMAIN_KEYWORDS = {
    "Syntax & Fundamentals": ["syntax", "basics", "datatype", "variable", "string", "operator", "fundamentals", "input", "output", "function"],
    "Problem Solving & Logic": ["loop", "control flow", "logic", "recursion", "algorithm", "problem solving", "condition", "binary search", "math"],
    "Data Structures & Storage": ["array", "data structures", "stack", "queue", "linked list", "tree", "database", "dbms", "sql", "storage", "hash", "normalization"],
    "Networking & Systems": ["networking", "network", "protocol", "tcp", "http", "os", "operating system", "system", "security", "socket"],
    "Software Theory & OOP": ["oop", "class", "object", "inheritance", "polymorphism", "encapsulation", "theory", "software engineering", "design pattern", "architecture"]
}


def calculate_radar_skills(user, db_session=None):
    """
    Computes a student's proficiency percentage (0-100%) across the 5 core domains
    by evaluating their completed assessment attempts and question topics.
    """
    from .models import StudentAssessmentAttempt, Question

    domain_stats = {d: {"correct": 0, "total": 0} for d in RADAR_DOMAINS}

    attempts = StudentAssessmentAttempt.query.filter_by(student_id=user.id, completed=True).all()
    for att in attempts:
        if not att.answers_json or not att.assessment:
            continue
        try:
            answers = json.loads(att.answers_json)
        except Exception:
            continue

        for q in att.assessment.questions:
            topic_str = (q.topic or "General").lower()
            text_str = (q.text or "").lower()

            # Find matching domain
            matched_domain = None
            for domain, kw_list in DOMAIN_KEYWORDS.items():
                if any(kw in topic_str or kw in text_str for kw in kw_list):
                    matched_domain = domain
                    break

            if not matched_domain:
                matched_domain = "Software Theory & OOP" if "oop" in topic_str else "Syntax & Fundamentals"

            domain_stats[matched_domain]["total"] += 1
            chosen = answers.get(str(q.id))
            if chosen is not None and int(chosen) == int(q.correct_index):
                domain_stats[matched_domain]["correct"] += 1

    labels = []
    values = []
    badges = []

    for domain in RADAR_DOMAINS:
        stats = domain_stats[domain]
        labels.append(domain)
        if stats["total"] > 0:
            pct = round((stats["correct"] / stats["total"]) * 100)
            values.append(pct)
            if pct >= 80:
                badge = "Master"
            elif pct >= 60:
                badge = "Proficient"
            else:
                badge = "Developing"
        else:
            # Baseline placeholder with guidance
            values.append(25)
            badge = "Untested"
        badges.append(badge)

    avg_proficiency = round(sum(values) / len(values)) if values else 0

    return {
        "labels": labels,
        "values": values,
        "scores": values,
        "badges": badges,
        "average": avg_proficiency,
        "has_data": any(domain_stats[d]["total"] > 0 for d in RADAR_DOMAINS)
    }


# Course Skill Tree Definition (Ordered Progression Track)
SKILL_TREE_SPEC = [
    {
        "id": "basics_syntax",
        "title": "Basics & Syntax",
        "level_label": "Level 1",
        "category": "Syntax & Core",
        "icon": "code",
        "description": "Core syntax, data types, variables, arithmetic operators, and basic I/O operations.",
        "prereq_id": None,
        "required_score": 60,
        "keywords": ["basics & syntax", "syntax", "basics"]
    },
    {
        "id": "control_loops",
        "title": "Control Flow & Loops",
        "level_label": "Level 2",
        "category": "Logic & Flow",
        "icon": "repeat",
        "description": "If-else conditional branching, while & for iterations, break, and nested logic.",
        "prereq_id": "basics_syntax",
        "required_score": 60,
        "keywords": ["control flow & loops", "loops", "control flow"]
    },
    {
        "id": "arrays_ds",
        "title": "Arrays & Data Structures",
        "level_label": "Level 3",
        "category": "Structures",
        "icon": "layers",
        "description": "Linear arrays, LIFO Stacks, FIFO Queues, and basic memory management concepts.",
        "prereq_id": "control_loops",
        "required_score": 60,
        "keywords": ["arrays & data structures", "arrays", "data structures"]
    },
    {
        "id": "oop_concepts",
        "title": "Object-Oriented Programming",
        "level_label": "Level 4",
        "category": "Architecture",
        "icon": "box",
        "description": "Classes, object instantiation, encapsulation, inheritance, and method overriding.",
        "prereq_id": "arrays_ds",
        "required_score": 60,
        "keywords": ["object-oriented programming", "oop", "classes"]
    },
    {
        "id": "dbms_sql",
        "title": "Database & SQL Mastery",
        "level_label": "Level 5",
        "category": "Storage & Data",
        "icon": "database",
        "description": "Relational schemas, SQL queries, primary/foreign keys, and 1NF/2NF normalization.",
        "prereq_id": "oop_concepts",
        "required_score": 60,
        "keywords": ["database & sql mastery", "database", "sql", "dbms"]
    },
    {
        "id": "algorithms_design",
        "title": "Algorithms & System Design",
        "level_label": "Level 6",
        "category": "Grandmaster",
        "icon": "cpu",
        "description": "Asymptotic time complexity (O(n)), binary search trees, and dynamic programming.",
        "prereq_id": "dbms_sql",
        "required_score": 60,
        "keywords": ["algorithms & system design", "algorithms", "system design"]
    }
]


def get_course_skill_tree(user, db_session=None):
    """
    Evaluates the student's mastery across the Course Skill Tree.
    Nodes are locked until their prerequisite node is completed with >= 60% score.
    Returns the enriched nodes, connector statuses, and overall tree progress.
    """
    from .models import Assessment, StudentAssessmentAttempt

    attempts = StudentAssessmentAttempt.query.filter_by(student_id=user.id, completed=True).all()
    all_assessments = Assessment.query.all()

    # Map assessment_id -> highest score
    attempt_map = {}
    for att in attempts:
        if att.score is not None:
            if att.assessment_id not in attempt_map or att.score > attempt_map[att.assessment_id]:
                attempt_map[att.assessment_id] = round(att.score, 1)

    node_states = {}
    enriched_nodes = []

    for spec in SKILL_TREE_SPEC:
        node_id = spec["id"]
        # Find matching assessment
        matched_asmt = None
        for a in all_assessments:
            t_low = a.title.lower()
            if any(kw in t_low for kw in spec["keywords"]):
                matched_asmt = a
                break

        asmt_id = matched_asmt.id if matched_asmt else None
        asmt_title = matched_asmt.title if matched_asmt else spec["title"]

        score = attempt_map.get(asmt_id, None) if asmt_id else None
        is_passed = (score is not None and score >= spec["required_score"])

        prereq_id = spec["prereq_id"]
        if prereq_id is None:
            is_unlocked = True
        else:
            is_unlocked = node_states.get(prereq_id, {}).get("is_passed", False)

        if is_passed:
            status = "mastered"
        elif is_unlocked:
            status = "available"
        else:
            status = "locked"

        node_info = {
            **spec,
            "assessment_id": asmt_id,
            "assessment_title": asmt_title,
            "score": score,
            "is_passed": is_passed,
            "is_unlocked": is_unlocked,
            "status": status,  # 'mastered' | 'available' | 'locked'
            "status_text": "Mastered" if is_passed else ("Available" if is_unlocked else "Locked")
        }

        node_states[node_id] = node_info
        enriched_nodes.append(node_info)

    mastered_count = sum(1 for n in enriched_nodes if n["status"] == "mastered")
    total_nodes = len(enriched_nodes)
    tree_progress_pct = round((mastered_count / total_nodes) * 100) if total_nodes > 0 else 0

    return {
        "nodes": enriched_nodes,
        "mastered_count": mastered_count,
        "total_nodes": total_nodes,
        "progress_pct": tree_progress_pct
    }


def ensure_skill_tree_assessments(db_session):
    """
    Ensures default Skill Tree assessments and questions exist in the database,
    providing ready-to-play quizzes for each node of the skill tree.
    """
    from .models import Subject, Assessment, Question, User

    # Check if subject exists
    subj = Subject.query.filter_by(name="Computer Science Mastery Track").first()
    if not subj:
        # Link to admin or teacher
        teacher = User.query.filter_by(role='teacher').first() or User.query.filter_by(role='admin').first()
        subj = Subject(
            name="Computer Science Mastery Track",
            teacher_id=teacher.id if teacher else None,
            class_year="All",
            semester="All"
        )
        db_session.add(subj)
        db_session.commit()

    sample_quizzes = [
        {
            "title": "Basics & Syntax Quiz",
            "topic": "Syntax",
            "questions": [
                {
                    "text": "Which of the following is a valid variable name in Python?",
                    "options": ["2my_var", "my-var", "_my_var", "my var"],
                    "correct_index": 2,
                    "topic": "Syntax"
                },
                {
                    "text": "What is the data type of the result of 10 / 2 in Python 3?",
                    "options": ["int", "float", "double", "string"],
                    "correct_index": 1,
                    "topic": "Datatypes"
                },
                {
                    "text": "What does len('Hello World') evaluate to?",
                    "options": ["10", "11", "12", "None"],
                    "correct_index": 1,
                    "topic": "Strings"
                }
            ]
        },
        {
            "title": "Control Flow & Loops Quiz",
            "topic": "Control Flow",
            "questions": [
                {
                    "text": "Which keyword immediately exits the current enclosing loop?",
                    "options": ["pass", "continue", "break", "return"],
                    "correct_index": 2,
                    "topic": "Control Flow"
                },
                {
                    "text": "How many times does 'for i in range(1, 5):' execute its block?",
                    "options": ["4 times", "5 times", "6 times", "0 times"],
                    "correct_index": 0,
                    "topic": "Loops"
                },
                {
                    "text": "What is the outcome of: x = 5; if x > 3: x += 2 else: x -= 2?",
                    "options": ["3", "5", "7", "9"],
                    "correct_index": 2,
                    "topic": "Logic"
                }
            ]
        },
        {
            "title": "Arrays & Data Structures Quiz",
            "topic": "Data Structures",
            "questions": [
                {
                    "text": "Which data structure follows the Last-In-First-Out (LIFO) principle?",
                    "options": ["Queue", "Stack", "Binary Tree", "Linked List"],
                    "correct_index": 1,
                    "topic": "Data Structures"
                },
                {
                    "text": "What is the typical time complexity of accessing an element in an array by index?",
                    "options": ["O(1)", "O(n)", "O(log n)", "O(n^2)"],
                    "correct_index": 0,
                    "topic": "Arrays"
                },
                {
                    "text": "Which structure processes items in the exact order they arrive (FIFO)?",
                    "options": ["Stack", "Queue", "Heap", "Hash Table"],
                    "correct_index": 1,
                    "topic": "Queues"
                }
            ]
        },
        {
            "title": "Object-Oriented Programming Quiz",
            "topic": "OOP",
            "questions": [
                {
                    "text": "Which OOP concept wraps data and functions together into a single unit?",
                    "options": ["Polymorphism", "Encapsulation", "Inheritance", "Abstraction"],
                    "correct_index": 1,
                    "topic": "OOP"
                },
                {
                    "text": "What enables a child class to override a method defined in its parent class?",
                    "options": ["Method Overriding", "Method Overloading", "Encapsulation", "Compilation"],
                    "correct_index": 0,
                    "topic": "Inheritance"
                },
                {
                    "text": "In Python, what is the special constructor method called inside a class?",
                    "options": ["__main__", "__init__", "__new__", "__construct__"],
                    "correct_index": 1,
                    "topic": "Classes"
                }
            ]
        },
        {
            "title": "Database & SQL Mastery Quiz",
            "topic": "Database",
            "questions": [
                {
                    "text": "Which SQL clause is used to filter records based on specific criteria?",
                    "options": ["ORDER BY", "WHERE", "GROUP BY", "HAVING"],
                    "correct_index": 1,
                    "topic": "SQL"
                },
                {
                    "text": "What is the primary key in a relational database table?",
                    "options": ["A key that allows nulls", "A unique identifier for each row", "A reference to another table", "A column for passwords"],
                    "correct_index": 1,
                    "topic": "Database"
                },
                {
                    "text": "Which normal form removes partial dependencies on composite candidate keys?",
                    "options": ["1NF", "2NF", "3NF", "BCNF"],
                    "correct_index": 1,
                    "topic": "Normalization"
                }
            ]
        },
        {
            "title": "Algorithms & System Design Quiz",
            "topic": "Algorithms",
            "questions": [
                {
                    "text": "What is the time complexity of searching in a sorted array using Binary Search?",
                    "options": ["O(1)", "O(log n)", "O(n)", "O(n log n)"],
                    "correct_index": 1,
                    "topic": "Algorithms"
                },
                {
                    "text": "Which technique solves overlapping subproblems once and stores their results?",
                    "options": ["Dynamic Programming", "Greedy Method", "Divide & Conquer", "Random Walk"],
                    "correct_index": 0,
                    "topic": "Algorithms"
                },
                {
                    "text": "In a Binary Search Tree (BST), what holds true for the left child of any node?",
                    "options": ["Greater than parent", "Strictly less than parent", "Equal to parent", "No order guarantee"],
                    "correct_index": 1,
                    "topic": "Trees"
                }
            ]
        }
    ]

    for quiz in sample_quizzes:
        existing = Assessment.query.filter_by(title=quiz["title"]).first()
        if not existing:
            asmt = Assessment(title=quiz["title"], subject_id=subj.id)
            db_session.add(asmt)
            db_session.commit()
            for q in quiz["questions"]:
                q_obj = Question(
                    assessment_id=asmt.id,
                    text=q["text"],
                    options_json=json.dumps(q["options"]),
                    correct_index=q["correct_index"],
                    topic=q["topic"]
                )
                db_session.add(q_obj)
            db_session.commit()

