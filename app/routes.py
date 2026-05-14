from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from . import db, login_manager
from .models import User, Subject, Assessment, Question, StudentAssessmentAttempt, TopicVideo
from .forms import LoginForm, CreateUserForm, AssessmentForm
from .utils import grade_attempt, find_weak_topics
from . import create_app
from . import models
from flask import current_app as app
import json
from .utils import recommend_video_for_topic_ai, award_xp_and_badges
from flask import render_template
from flask_login import login_required
from .models import User
import json
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import db, login_manager
from .models import User, Subject, Assessment, Question, StudentAssessmentAttempt
from .utils import grade_attempt, find_weak_topics, recommend_video_for_topic_ai, award_xp_and_badges
from flask import request, jsonify
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from . import db
from .models import Assessment, Question, StudentAssessmentAttempt, User, Subject
from .utils import grade_attempt, find_weak_topics, recommend_video_for_topic_ai, award_xp_and_badges
from app.utils import chatbot_answer

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        u = User.query.filter_by(username=form.username.data).first()
        if u and u.verify_password(form.password.data):
            login_user(u)
            if u.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif u.role == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        flash("Invalid credentials")
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ---------- Admin ----------
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role!='admin':
        return "Forbidden", 403
    teachers = User.query.filter_by(role='teacher').all()
    students = User.query.filter_by(role='student').all()
    return render_template('admin/admin_dashboard.html', teachers=teachers, students=students)

@app.route('/admin/create_user', methods=['POST'])
@login_required
def admin_create_user():
    if current_user.role != 'admin':
        return "Forbidden", 403

    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')
    full_name = request.form.get('full_name')
    class_year = request.form.get('class_year') or None
    semester = request.form.get('semester') or None

    if not username or not password or not role:
        flash("username, password and role required")
        return redirect(url_for('admin_dashboard'))

    if User.query.filter_by(username=username).first():
        flash("User already exists")
        return redirect(url_for('admin_dashboard'))

    new = User(
        username=username,
        password_hash=User.hash_password(password),
        role=role,
        full_name=full_name,
        class_year=class_year,
        semester=semester
    )
    db.session.add(new)
    db.session.commit()
    flash("User created")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/students')
@login_required
def admin_view_students():
    if current_user.role != 'admin':
        return "Forbidden", 403

    # read optional filters from query string
    class_year = request.args.get('class_year')
    semester = request.args.get('semester')
    subject_id = request.args.get('subject_id')

    q = User.query.filter_by(role='student')
    if class_year:
        q = q.filter(User.class_year==class_year)
    if semester:
        q = q.filter(User.semester==semester)

    students = q.all()

    # If subject_id filter requested: show only students who have attempts for that subject (simple approach)
    if subject_id:
        subject = Subject.query.get(subject_id)
        if subject:
            students = [
                s for s in students
                if (s.class_year == subject.class_year and
                    s.semester == subject.semester)
            ]


    # Also supply lists for filter dropdowns
    distinct_classes = [c[0] for c in db.session.query(User.class_year).filter(User.class_year!=None).distinct().all()]
    distinct_sem = [c[0] for c in db.session.query(User.semester).filter(User.semester!=None).distinct().all()]
    subjects = Subject.query.all()

    return render_template('admin/admin_students.html',
                           students=students,
                           distinct_classes=distinct_classes,
                           distinct_sem=distinct_sem,
                           subjects=subjects,
                           selected_class=class_year,
                           selected_sem=semester,
                           selected_subject=subject_id)


# Admin can add subjects (assign to teacher)
@app.route('/admin/create_subject', methods=['POST'])
@login_required
def admin_create_subject():
    if current_user.role != 'admin':
        return "Forbidden", 403

    name = request.form.get('name')
    teacher_id = request.form.get('teacher_id')
    class_year = request.form.get('class_year')
    semester = request.form.get('semester')

    s = Subject(
        name=name,
        teacher_id=teacher_id if teacher_id else None,
        class_year=class_year,
        semester=semester
    )

    db.session.add(s)
    db.session.commit()
    flash("Subject created")
    return redirect(url_for('admin_dashboard'))


# ---------- Teacher ----------
# Teacher dashboard: list subjects, assessments, and registered students for the teacher
@app.route('/teacher')
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher':
        return "Forbidden", 403

    subjects = Subject.query.filter_by(teacher_id=current_user.id).all()
    # For convenience show students (all students or filtered per subject on request)
    students = User.query.filter_by(role='student').all()
    return render_template('teacher/teacher_dashboard.html', subjects=subjects, students=students,hide_sidebar=True)

# Create assessment (GET shows form, POST processes JSON of questions)
@app.route('/teacher/create_assessment', methods=['GET', 'POST'])
@login_required
def create_assessment():
    if current_user.role != 'teacher':
        return "Forbidden", 403

    if request.method == 'POST':
        title = request.form.get('title')
        subject_id = request.form.get('subject_id')
        questions_json = request.form.get('questions_json')

        if not title or not subject_id:
            flash("Title and subject required")
            return redirect(url_for('create_assessment'))

        a = Assessment(title=title, subject_id=int(subject_id))
        db.session.add(a)
        db.session.commit()

        if questions_json:
            try:
                qlist = json.loads(questions_json)
                for q in qlist:
                    qobj = Question(
                        assessment_id=a.id,
                        text=q.get('text'),
                        options_json=json.dumps(q.get('options', [])),
                        correct_index=int(q.get('correct_index', 0)),
                        topic=q.get('topic','General')
                    )
                    db.session.add(qobj)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.exception("Failed to save questions: %s", e)
                flash("Failed to save questions. Check format.")
                return redirect(url_for('create_assessment'))

        flash("Assessment created")
        return redirect(url_for('teacher_dashboard'))

    # GET: show subjects for this teacher
    subjects = Subject.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher/create_assessment.html', subjects=subjects)

# View assessments for a subject & see results
@app.route('/teacher/subject/<int:subject_id>/assessments')
@login_required
def teacher_subject_assessments(subject_id):
    if current_user.role != 'teacher':
        return "Forbidden", 403
    subject = Subject.query.get_or_404(subject_id)
    if subject.teacher_id != current_user.id:
        return "Forbidden", 403
    assessments = Assessment.query.filter_by(subject_id=subject_id).order_by(Assessment.created_at.desc()).all()
    return render_template('teacher/subject_assessments.html', subject=subject, assessments=assessments)

# View results for an assessment
@app.route('/teacher/assessment/<int:assessment_id>/results')
@login_required
def teacher_assessment_results(assessment_id):
    if current_user.role != 'teacher':
        return "Forbidden", 403
    assessment = Assessment.query.get_or_404(assessment_id)
    # ensure teacher owns the subject
    if assessment.subject.teacher_id != current_user.id:
        return "Forbidden", 403
    attempts = StudentAssessmentAttempt.query.filter_by(assessment_id=assessment_id).all()

    # prepare per-topic aggregated stats for teacher (simple)
    topic_stats = {}
    for q in assessment.questions:
        topic_stats[q.topic] = topic_stats.get(q.topic, {'total':0,'correct':0})
    for att in attempts:
        if not att.answers_json:
            continue
        answers = json.loads(att.answers_json)
        for q in assessment.questions:
            chosen = answers.get(str(q.id))
            topic_stats[q.topic]['total'] += 1
            if chosen is not None and int(chosen) == int(q.correct_index):
                topic_stats[q.topic]['correct'] += 1

    # convert to percent
    topic_percent = {t: (s['correct'] / s['total'] * 100) if s['total']>0 else None for t, s in topic_stats.items()}

    return render_template('teacher/view_results.html', assessment=assessment, attempts=attempts, topic_percent=topic_percent)

# ---------- Student ----------
@app.route('/student')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return "Forbidden", 403

    # past attempts
    attempts = StudentAssessmentAttempt.query.filter_by(student_id=current_user.id).order_by(StudentAssessmentAttempt.created_at.desc()).all()

    # available assessments for student's class/semester
    # prefer subject mapping if available, otherwise show all
    # subjects matching student's class/semester
    subjects = Subject.query.filter_by(class_year=current_user.class_year, semester=current_user.semester).all()
    if subjects:
        subject_ids = [s.id for s in subjects]
        assessments = Assessment.query.filter(Assessment.subject_id.in_(subject_ids)).all()
    else:
        assessments = Assessment.query.all()

    # leaderboard preview (top 5)
    leaderboard_preview = User.query.filter_by(role='student').order_by(User.points.desc()).limit(5).all()

    # topic analytics for this student (aggregate across attempts)
    # produce mapping topic -> percent correct (0..100)
    topic_totals = {}
    for att in attempts:
        if not att.answers_json:
            continue
        answers = json.loads(att.answers_json)
        asmt = att.assessment
        if not asmt: continue
        for q in asmt.questions:
            t = q.topic or 'General'
            if t not in topic_totals:
                topic_totals[t] = {'total':0,'correct':0}
            topic_totals[t]['total'] += 1
            chosen = answers.get(str(q.id))
            if chosen is not None and int(chosen) == int(q.correct_index):
                topic_totals[t]['correct'] += 1

    topic_labels = []
    topic_values = []
    for t, s in topic_totals.items():
        topic_labels.append(t)
        pct = (s['correct'] / s['total'] * 100) if s['total']>0 else 0
        topic_values.append(round(pct,1))

    return render_template('student/student_dashboard.html',
                            attempts=attempts,
                            assessments=assessments,
                            leaderboard_preview=leaderboard_preview,
                            topic_labels=topic_labels,
                            topic_values=topic_values)

# Full take_assessment (GET shows questions; POST grades & recommends AI video)
@app.route('/student/assessment/<int:assessment_id>/take', methods=['GET','POST'])
@login_required
def take_assessment(assessment_id):
    if current_user.role != 'student':
        return "Forbidden", 403

    assessment = Assessment.query.get_or_404(assessment_id)
    # load questions
    questions = Question.query.filter_by(assessment_id=assessment_id).all()

    # check if student already attempted
    existing = StudentAssessmentAttempt.query.filter_by(student_id=current_user.id, assessment_id=assessment_id).first()
    if request.method == 'GET':
        if existing:
            # If already attempted, show the result view or a message
            flash("You have already attempted this assessment. You cannot retake it.", "warning")
            # redirect to student dashboard (or you could show attempt details page)
            return redirect(url_for('student_dashboard'))

        # build question list for rendering (same as before)
        qlist = []
        for q in questions:
            try:
                options = json.loads(q.options_json)
            except Exception:
                options = []
            qlist.append({
                'id': q.id,
                'text': q.text,
                'options': options,
                'topic': q.topic
            })
        return render_template('student/take_assessment.html', assessment=assessment, questions=qlist)

    # POST -> submitting answers
    if existing:
        # double-check on server side: prevent duplicate POSTs
        flash("Duplicate submission prevented. You have already attempted this assessment.", "warning")
        return redirect(url_for('student_dashboard'))

    answers_json = request.form.get('answers_json') or (request.json and request.json.get('answers_json'))
    if not answers_json:
        flash("No answers submitted.", "danger")
        return redirect(url_for('take_assessment', assessment_id=assessment_id))
    try:
        answers_map = json.loads(answers_json)
    except Exception:
        flash("Invalid answers format.", "danger")
        return redirect(url_for('take_assessment', assessment_id=assessment_id))

    score, per_q, topic_stats = grade_attempt(questions, answers_map)

    attempt = StudentAssessmentAttempt(
        student_id=current_user.id,
        assessment_id=assessment_id,
        answers_json=json.dumps(answers_map),
        score=score,
        completed=True,
        watched_video_for_weak_topic=False
    )

    weak = find_weak_topics(topic_stats, threshold=0.65)
    weak_topic_name = weak[0][0] if weak else None

    video_url = None
    if weak_topic_name:
        sample_q_texts = [q.text for q in questions[:6]]
        try:
            video_url = recommend_video_for_topic_ai(weak_topic_name, sample_q_texts)
        except Exception as e:
            current_app.logger.exception("AI recommendation failed: %s", e)
            video_url = None

    attempt.video_url = video_url

    try:
        db.session.add(attempt)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Failed to save attempt: %s", e)
        flash("Server error saving attempt.", "danger")
        return redirect(url_for('student_dashboard'))

    # award xp and badges (commits inside)
    try:
        xp_gain, new_badges = award_xp_and_badges(current_user, score, db.session)
    except Exception as e:
        current_app.logger.exception("Award XP failed: %s", e)
        xp_gain = 0
        new_badges = []

    attempt = StudentAssessmentAttempt.query.get(attempt.id)

    return render_template('student/result.html',
                           score=score,
                           attempt=attempt,
                           weak_topic=weak_topic_name,
                           video_url=video_url,
                           new_badges=new_badges,
                           xp_gain=xp_gain)
# @app.route('/student/assessment/<int:assessment_id>/take', methods=['GET','POST'])
# @login_required
# def take_assessment(assessment_id):
#     if current_user.role != 'student':
#         return "Forbidden", 403

#     assessment = Assessment.query.get_or_404(assessment_id)
#     questions = Question.query.filter_by(assessment_id=assessment_id).all()

#     if request.method == 'POST':
#         answers_json = request.form.get('answers_json') or (request.json and request.json.get('answers_json'))
#         if not answers_json:
#             flash("No answers submitted.")
#             return redirect(url_for('take_assessment', assessment_id=assessment_id))
#         try:
#             answers_map = json.loads(answers_json)
#         except Exception:
#             flash("Invalid answers format.")
#             return redirect(url_for('take_assessment', assessment_id=assessment_id))

#         score, per_q, topic_stats = grade_attempt(questions, answers_map)

#         attempt = StudentAssessmentAttempt(
#             student_id=current_user.id,
#             assessment_id=assessment_id,
#             answers_json=json.dumps(answers_map),
#             score=score,
#             completed=True,
#             watched_video_for_weak_topic=False
#         )

#         weak = find_weak_topics(topic_stats, threshold=0.65)
#         weak_topic_name = weak[0][0] if weak else None

#         video_url = None
#         if weak_topic_name:
#             sample_q_texts = [q.text for q in questions[:6]]
#             try:
#                 video_url = recommend_video_for_topic_ai(weak_topic_name, sample_q_texts)
#             except Exception as e:
#                 current_app.logger.exception("AI recommendation failed: %s", e)
#                 video_url = None

#         attempt.video_url = video_url

#         try:
#             db.session.add(attempt)
#             db.session.commit()
#         except Exception as e:
#             db.session.rollback()
#             current_app.logger.exception("Failed to save attempt: %s", e)
#             flash("Server error saving attempt.")
#             return redirect(url_for('student_dashboard'))

#         # award xp and badges (commits inside)
#         try:
#             xp_gain, new_badges = award_xp_and_badges(current_user, score, db.session)
#         except Exception as e:
#             current_app.logger.exception("Award XP failed: %s", e)
#             xp_gain = 0
#             new_badges = []

#         attempt = StudentAssessmentAttempt.query.get(attempt.id)

#         return render_template('student/result.html',
#                                score=score,
#                                attempt=attempt,
#                                weak_topic=weak_topic_name,
#                                video_url=video_url,
#                                new_badges=new_badges,
#                                xp_gain=xp_gain)

#     # GET -> render question list
#     qlist = []
#     for q in questions:
#         try:
#             options = json.loads(q.options_json)
#         except Exception:
#             options = []
#         qlist.append({
#             'id': q.id,
#             'text': q.text,
#             'options': options,
#             'topic': q.topic
#         })

#     return render_template('student/take_assessment.html', assessment=assessment, questions=qlist)

# mark video watched (AJAX)
@app.route('/student/attempt/<int:attempt_id>/mark_video_watched', methods=['POST'])
@login_required
def mark_video_watched(attempt_id):
    att = StudentAssessmentAttempt.query.get_or_404(attempt_id)
    if att.student_id != current_user.id:
        return jsonify({"error":"forbidden"}), 403
    att.watched_video_for_weak_topic = True
    db.session.commit()
    return jsonify({"status":"ok"})

# simple in-app chatbot (rule-based). POST JSON: { "q": "text" }
@app.route('/student/chat', methods=['POST'])
@login_required
def student_chat():
    if current_user.role != 'student':
        return jsonify({"error":"forbidden"}), 403
    data = request.get_json()
    question = data.get("q", "")
    answer = chatbot_answer(question)
    return jsonify({"answer": answer})

@app.route('/student/cheating_alert', methods=['POST'])
@login_required
def student_cheating_alert():
    # only allow students to report their own camera events
    if current_user.role != 'student':
        return jsonify({"error":"forbidden"}), 403
    data = request.get_json() or {}
    reason = data.get('reason')
    details = data.get('details')
    assessment_id = data.get('assessment_id')
    ts = data.get('ts') or datetime.utcnow().isoformat()

    # simple server log; optionally persist into DB
    current_app.logger.info(f"CHEAT_ALERT student={current_user.id} assessment={assessment_id} reason={reason} details={details} ts={ts}")

    # If you want to persist, insert into a table here
    # Example: db.session.add(CheatingEvent(...)); db.session.commit()

    return jsonify({"status":"ok"})

# Leaderboard
# alias /leaderboard -> student leaderboard (keeps templates unchanged)
@app.route('/leaderboard')
@login_required
def leaderboard():
    # if you later want different leaderboards for admin/teacher, expand logic here
    if current_user.role == 'student':
        return leaderboard()
    # For admin/teacher, you can show same view or redirect to admin/teacher leaderboard
    # e.g. return redirect(url_for('admin_leaderboard')) if you implement it
    return leaderboard()

