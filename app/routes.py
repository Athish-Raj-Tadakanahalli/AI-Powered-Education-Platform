import json
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory
from flask import current_app as app
from flask_login import login_user, logout_user, login_required, current_user
from . import db, login_manager
from .models import User, Subject, Assessment, Question, StudentAssessmentAttempt, TopicVideo, Attendance, LearningMaterial
from .forms import LoginForm, CreateUserForm, AssessmentForm
from .utils import (
    grade_attempt,
    find_weak_topics,
    recommend_video_for_topic_ai,
    batch_recommend_videos,
    batch_generate_study_hub,
    award_xp_and_badges,
    chatbot_answer,
    generate_study_hub_content,
    generate_question_explanation,
    update_streak,
    calculate_radar_skills,
    get_course_skill_tree,
    ensure_skill_tree_assessments
)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        return redirect(url_for('student_dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        u = User.query.filter_by(username=form.username.data).first()
        if u and u.verify_password(form.password.data):
            if u.role == 'student' and not u.is_approved:
                if u.approval_status == 'rejected':
                    flash("Your account registration request was rejected by the administrator.", "danger")
                else:
                    flash("Your account is awaiting administrator approval. Please check back once approved.", "warning")
                return render_template('login.html', form=form)

            login_user(u)
            if u.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif u.role == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            else:
                if u.role == 'student':
                    try:
                        from app.utils import update_streak
                        updated, streak_bonus, streak_badges, freeze_used = update_streak(u, db.session)
                        if freeze_used:
                            flash("🛡️ Your Streak Freeze was activated and saved your daily streak!", "info")
                    except Exception as e:
                        current_app.logger.exception("Failed to update streak on login: %s", e)
                return redirect(url_for('student_dashboard'))
        flash("Invalid credentials", "danger")
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip() or None
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        class_year = request.form.get('class_year', '').strip() or None
        semester = request.form.get('semester', '').strip() or None

        if not username or not password or not full_name:
            flash("Username, Full Name, and Password are required.", "danger")
            return render_template('register.html')

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash("Username already exists. Please choose a different username or student ID.", "warning")
            return render_template('register.html')

        new_student = User(
            username=username,
            full_name=full_name,
            email=email,
            password_hash=User.hash_password(password),
            role='student',
            class_year=class_year,
            semester=semester,
            is_approved=False,
            approval_status='pending'
        )
        db.session.add(new_student)
        db.session.commit()
        flash("Your account request has been submitted successfully! An administrator will review and approve your account soon.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ---------- Admin ----------
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return "Forbidden", 403
    teachers = User.query.filter_by(role='teacher').all()
    students = User.query.filter_by(role='student', is_approved=True).all()
    pending_students = User.query.filter_by(role='student', is_approved=False).order_by(User.created_at.desc()).all()
    return render_template('admin/admin_dashboard.html', teachers=teachers, students=students, pending_students=pending_students)

@app.route('/admin/pending_requests')
@login_required
def admin_pending_requests():
    if current_user.role != 'admin':
        return "Forbidden", 403

    query = request.args.get('q', '').strip()
    class_year = request.args.get('class_year', '').strip()
    semester = request.args.get('semester', '').strip()

    q = User.query.filter_by(role='student', is_approved=False)
    if query:
        q = q.filter(
            db.or_(
                User.username.ilike(f'%{query}%'),
                User.full_name.ilike(f'%{query}%'),
                User.email.ilike(f'%{query}%')
            )
        )
    if class_year:
        q = q.filter(User.class_year == class_year)
    if semester:
        q = q.filter(User.semester == semester)

    pending_students = q.order_by(User.created_at.desc()).all()

    distinct_classes = [c[0] for c in db.session.query(User.class_year).filter(User.role == 'student', User.is_approved == False, User.class_year != None).distinct().all()]
    distinct_sem = [c[0] for c in db.session.query(User.semester).filter(User.role == 'student', User.is_approved == False, User.semester != None).distinct().all()]

    return render_template(
        'admin/admin_pending_requests.html',
        pending_students=pending_students,
        distinct_classes=distinct_classes,
        distinct_sem=distinct_sem,
        search_query=query,
        selected_class=class_year,
        selected_sem=semester
    )

@app.route('/admin/approve_student/<int:user_id>', methods=['POST'])
@login_required
def admin_approve_student(user_id):
    if current_user.role != 'admin':
        return "Forbidden", 403

    student = User.query.get_or_404(user_id)
    if student.role != 'student':
        flash("Only student accounts can be approved here.", "warning")
        return redirect(request.referrer or url_for('admin_pending_requests'))

    student.is_approved = True
    student.approval_status = 'approved'
    db.session.commit()
    flash(f"Student '{student.full_name or student.username}' ({student.username}) has been approved successfully!", "success")
    return redirect(request.referrer or url_for('admin_pending_requests'))

@app.route('/admin/reject_student/<int:user_id>', methods=['POST'])
@login_required
def admin_reject_student(user_id):
    if current_user.role != 'admin':
        return "Forbidden", 403

    student = User.query.get_or_404(user_id)
    if student.role != 'student':
        flash("Only student accounts can be rejected.", "warning")
        return redirect(request.referrer or url_for('admin_pending_requests'))

    username = student.username
    db.session.delete(student)
    db.session.commit()
    flash(f"Registration request for '{username}' was rejected and removed.", "info")
    return redirect(request.referrer or url_for('admin_pending_requests'))

@app.route('/admin/approve_all_students', methods=['POST'])
@login_required
def admin_approve_all_students():
    if current_user.role != 'admin':
        return "Forbidden", 403

    pending_students = User.query.filter_by(role='student', is_approved=False).all()
    count = len(pending_students)
    for s in pending_students:
        s.is_approved = True
        s.approval_status = 'approved'

    db.session.commit()
    flash(f"Successfully approved all {count} pending student request(s).", "success")
    return redirect(request.referrer or url_for('admin_pending_requests'))

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
        semester=semester,
        is_approved=True,
        approval_status='approved'
    )
    db.session.add(new)
    db.session.commit()
    flash("User created")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin':
        return "Forbidden", 403

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own admin account.", "danger")
        return redirect(url_for('admin_dashboard'))

    try:
        if user.role == 'student':
            # Delete attempts
            StudentAssessmentAttempt.query.filter_by(student_id=user.id).delete()
        elif user.role == 'teacher':
            # Nullify teacher_id in subjects
            subjects = Subject.query.filter_by(teacher_id=user.id).all()
            for s in subjects:
                s.teacher_id = None

        db.session.delete(user)
        db.session.commit()
        flash(f"User '{user.username}' has been deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Failed to delete user: %s", e)
        flash("Failed to delete user.", "danger")

    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/edit_user/<int:user_id>', methods=['POST'])
@login_required
def admin_edit_user(user_id):
    if current_user.role != 'admin':
        return "Forbidden", 403

    user = User.query.get_or_404(user_id)
    full_name = request.form.get('full_name')

    if not full_name:
        flash("Name cannot be empty.", "warning")
        return redirect(request.referrer or url_for('admin_dashboard'))

    try:
        user.full_name = full_name
        db.session.commit()
        flash(f"User '{user.username}' name updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Failed to edit user: %s", e)
        flash("Failed to update user name.", "danger")

    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/students')
@login_required
def admin_view_students():
    if current_user.role != 'admin':
        return "Forbidden", 403

    # read optional filters from query string
    class_year = request.args.get('class_year')
    semester = request.args.get('semester')
    subject_id = request.args.get('subject_id')

    q = User.query.filter_by(role='student', is_approved=True)
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
    subject_ids = [s.id for s in subjects]

    # Assessments
    assessments = Assessment.query.filter(Assessment.subject_id.in_(subject_ids)).all() if subject_ids else []
    assessment_ids = [a.id for a in assessments]

    # Attempts & Average Score
    attempts = StudentAssessmentAttempt.query.filter(StudentAssessmentAttempt.assessment_id.in_(assessment_ids)).all() if assessment_ids else []
    completed_attempts = [att for att in attempts if att.completed and att.score is not None]
    avg_score = round(sum(att.score for att in completed_attempts) / len(completed_attempts), 1) if completed_attempts else 0.0

    # Attendance Rate
    attendance_records = Attendance.query.filter_by(teacher_id=current_user.id).all()
    present_count = sum(1 for att in attendance_records if att.status and att.status.lower() == 'present')
    attendance_rate = round((present_count / len(attendance_records)) * 100, 1) if attendance_records else 0.0

    # Learning Materials Count
    total_materials = LearningMaterial.query.filter_by(teacher_id=current_user.id).count()

    # Enrolled Students
    students = User.query.filter_by(role='student').all()

    # Top Performing Students
    student_scores = {}
    for att in completed_attempts:
        if att.student_id not in student_scores:
            student_scores[att.student_id] = []
        student_scores[att.student_id].append(att.score)

    top_performers = []
    if student_scores:
        sorted_students = sorted(student_scores.items(), key=lambda x: sum(x[1]) / len(x[1]), reverse=True)[:5]
        for sid, scores in sorted_students:
            u = User.query.get(sid)
            if u:
                top_performers.append({
                    'user': u,
                    'avg': round(sum(scores) / len(scores), 1),
                    'attempts_count': len(scores)
                })
    elif students:
        top_by_xp = sorted(students, key=lambda s: s.xp or 0, reverse=True)[:5]
        for u in top_by_xp:
            top_performers.append({
                'user': u,
                'avg': u.xp or 0,
                'attempts_count': len(u.attempts) if u.attempts else 0
            })

    return render_template(
        'teacher/teacher_dashboard.html',
        subjects=subjects,
        students=students,
        total_assessments=len(assessments),
        avg_score=avg_score,
        attendance_rate=attendance_rate,
        total_materials=total_materials,
        top_performers=top_performers,
        hide_sidebar=True
    )

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
@app.route('/student/dashboard')
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
    completed_attempts = [att for att in attempts if att.completed and att.score is not None]
    student_avg_score = round(sum(att.score for att in completed_attempts) / len(completed_attempts), 1) if completed_attempts else 0.0

    # Ensure skill tree sample assessments exist
    try:
        ensure_skill_tree_assessments(db.session)
    except Exception as e:
        current_app.logger.warning("Failed to auto-seed skill tree: %s", e)

    # Calculate 5-domain radar data & skill tree progress
    radar_data = calculate_radar_skills(current_user, db.session)
    skill_tree = get_course_skill_tree(current_user, db.session)

    return render_template('student/student_dashboard.html',
                            attempts=attempts,
                            assessments=assessments,
                            leaderboard_preview=leaderboard_preview,
                            topic_labels=radar_data["labels"],
                            topic_values=radar_data["values"],
                            radar_data=radar_data,
                            skill_tree=skill_tree,
                            student_avg_score=student_avg_score,
                            completed_count=len(completed_attempts))

@app.route('/student/skill-tree')
@login_required
def student_skill_tree():
    if current_user.role != 'student':
        return "Forbidden", 403

    try:
        ensure_skill_tree_assessments(db.session)
    except Exception as e:
        current_app.logger.warning("Failed to auto-seed skill tree: %s", e)

    radar_data = calculate_radar_skills(current_user, db.session)
    skill_tree = get_course_skill_tree(current_user, db.session)

    return render_template('student/skill_tree.html',
                            radar_data=radar_data,
                            skill_tree=skill_tree)

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
    can_retake = (request.args.get('retake') == '1') or (existing and (existing.score is None or existing.score < 60))

    if request.method == 'GET':
        if existing and not can_retake:
            flash(f"You have already completed this assessment with a score of {existing.score}%.", "info")
            return redirect(url_for('student_dashboard'))

        # build question list for rendering
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
        return render_template('student/take_assessment.html', assessment=assessment, questions=qlist, hide_chatbot=True)

    # POST -> submitting answers
    if existing and not can_retake:
        flash("Duplicate submission prevented. You have already completed this assessment.", "warning")
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

    # Recommending targeted videos for all incorrect questions in parallel
    incorrect_questions_list = []
    fetch_items = []
    for q in questions:
        is_correct = per_q.get(q.id, False)
        if not is_correct:
            chosen_index = answers_map.get(str(q.id))
            try:
                options = json.loads(q.options_json)
                student_ans = options[int(chosen_index)] if chosen_index is not None and 0 <= int(chosen_index) < len(options) else "Unanswered"
                correct_ans = options[int(q.correct_index)] if 0 <= int(q.correct_index) < len(options) else "N/A"
            except Exception:
                student_ans = "Unanswered"
                correct_ans = "N/A"
            
            incorrect_questions_list.append({
                "question_id": q.id,
                "question_text": q.text,
                "topic": q.topic,
                "student_answer": student_ans,
                "correct_answer": correct_ans,
                "video_url": None
            })
            fetch_items.append({"topic": q.topic, "question_text": q.text})

    if fetch_items:
        try:
            video_urls = batch_recommend_videos(fetch_items)
            for idx, vid_url in enumerate(video_urls):
                incorrect_questions_list[idx]["video_url"] = vid_url
        except Exception as e:
            current_app.logger.exception("Batch video recommendation failed: %s", e)

    # Identify weak topics (performance < 60%) in this attempt
    from app.utils import find_weak_topics
    weak_topics = find_weak_topics(topic_stats, threshold=0.6)
    
    # Generate study hub content in parallel
    study_hub = {}
    if weak_topics:
        try:
            study_hub = batch_generate_study_hub(weak_topics)
        except Exception as e:
            current_app.logger.exception("Failed to batch generate study hub content: %s", e)
            
    remediation_data = {
        "incorrect_questions": incorrect_questions_list,
        "study_hub": study_hub
    }

    try:
        if existing and can_retake:
            attempt = existing
            attempt.answers_json = json.dumps(answers_map)
            attempt.score = score
            attempt.completed = True
            attempt.remediation_json = json.dumps(remediation_data)
        else:
            attempt = StudentAssessmentAttempt(
                student_id=current_user.id,
                assessment_id=assessment_id,
                answers_json=json.dumps(answers_map),
                score=score,
                completed=True,
                watched_video_for_weak_topic=False,
                remediation_json=json.dumps(remediation_data)
            )
            db.session.add(attempt)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Failed to save attempt: %s", e)
        flash("Server error saving attempt.", "danger")
        return redirect(url_for('student_dashboard'))

    # award xp and badges (commits inside)
    leveled_up = False
    old_level = getattr(current_user, 'level', 1)
    new_level = getattr(current_user, 'level', 1)
    freeze_used = False
    try:
        xp_gain, new_badges, leveled_up, old_level, new_level = award_xp_and_badges(current_user, score, db.session)
        from app.utils import update_streak
        _, streak_bonus, streak_new_badges, freeze_used = update_streak(current_user, db.session)
        xp_gain += streak_bonus
        new_badges.extend(streak_new_badges)
    except Exception as e:
        current_app.logger.exception("Award XP and Streak failed: %s", e)
        xp_gain = 0
        new_badges = []

    attempt = StudentAssessmentAttempt.query.get(attempt.id)

    return render_template('student/result.html',
                           score=score,
                           attempt=attempt,
                           incorrect_questions=incorrect_questions_list,
                           study_hub=study_hub,
                           new_badges=new_badges,
                           xp_gain=xp_gain,
                           leveled_up=leveled_up,
                           old_level=old_level,
                           new_level=new_level,
                           freeze_used=freeze_used)

@app.route('/student/attempt/<int:attempt_id>')
@login_required
def view_attempt(attempt_id):
    if current_user.role != 'student':
        return "Forbidden", 403

    attempt = StudentAssessmentAttempt.query.get_or_404(attempt_id)
    if attempt.student_id != current_user.id:
        return "Forbidden", 403

    incorrect_questions = []
    study_hub = {}
    updated_remediation = False
    if attempt.remediation_json:
        try:
            data = json.loads(attempt.remediation_json)
            if isinstance(data, dict):
                incorrect_questions = data.get("incorrect_questions", [])
                study_hub = data.get("study_hub", {})
            else:
                incorrect_questions = data
                study_hub = {}
        except Exception:
            incorrect_questions = []
            study_hub = {}

    # Auto-backfill video_url if missing for any incorrect question (in parallel)
    missing_items = []
    missing_indices = []
    for idx, item in enumerate(incorrect_questions):
        if not item.get("video_url"):
            missing_items.append({"topic": item.get("topic", ""), "question_text": item.get("question_text", "")})
            missing_indices.append(idx)

    if missing_items:
        try:
            backfilled_urls = batch_recommend_videos(missing_items)
            for idx, vid_url in zip(missing_indices, backfilled_urls):
                incorrect_questions[idx]["video_url"] = vid_url
                updated_remediation = True
        except Exception as e:
            current_app.logger.exception("Backfilling video URL failed: %s", e)

    if updated_remediation and attempt.remediation_json:
        try:
            remediation_data = {
                "incorrect_questions": incorrect_questions,
                "study_hub": study_hub
            }
            attempt.remediation_json = json.dumps(remediation_data)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Failed to save backfilled remediation json: %s", e)

    return render_template('student/attempt_details.html', 
                           attempt=attempt, 
                           incorrect_questions=incorrect_questions, 
                           study_hub=study_hub)


@app.route('/api/fetch_remediation_video', methods=['POST'])
@login_required
def api_fetch_remediation_video():
    """
    Async API endpoint to fetch or refresh video URL for a given topic + question text.
    Returns JSON: {"status": "success", "video_url": "..."}
    """
    data = request.get_json() or {}
    topic = data.get("topic", "").strip()
    question_text = data.get("question_text", "").strip()

    if not topic:
        return jsonify({"status": "error", "message": "Topic is required"}), 400

    try:
        video_url = recommend_video_for_topic_ai(topic, [question_text] if question_text else None)
        return jsonify({"status": "success", "topic": topic, "video_url": video_url})
    except Exception as e:
        current_app.logger.exception("API video fetch failed: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


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

# simple in-app chatbot (rule-based / Gemini-powered). POST JSON: { "q": "text" }
@app.route('/student/chat', methods=['POST'])
@login_required
def student_chat():
    if current_user.role != 'student':
        return jsonify({"error":"forbidden"}), 403
    data = request.get_json()
    question = data.get("q", "")
    
    # Compile student context
    from collections import defaultdict
    try:
        badges = json.loads(current_user.badges or "[]")
    except Exception:
        badges = []
    
    attempts = StudentAssessmentAttempt.query.filter_by(student_id=current_user.id).order_by(StudentAssessmentAttempt.created_at.desc()).limit(5).all()
    topic_totals = defaultdict(lambda: {'correct': 0, 'total': 0})
    for att in attempts:
        if not att.answers_json:
            continue
        try:
            answers_map = json.loads(att.answers_json)
            questions = Question.query.filter_by(assessment_id=att.assessment_id).all()
            for q in questions:
                chosen = answers_map.get(str(q.id))
                is_correct = False
                if chosen is not None and int(chosen) == int(q.correct_index):
                    is_correct = True
                if is_correct:
                    topic_totals[q.topic]['correct'] += 1
                topic_totals[q.topic]['total'] += 1
        except Exception:
            continue

    weak_topics = []
    for t, s in topic_totals.items():
        rate = s['correct'] / s['total']
        if rate < 0.6:
            weak_topics.append(f"{t} (accuracy: {int(rate*100)}%)")

    context = (
        f"- Student Name: {current_user.full_name or current_user.username}\n"
        f"- Course/Year: {current_user.class_year or 'N/A'}\n"
        f"- Semester: {current_user.semester or 'N/A'}\n"
        f"- XP/Points: {current_user.xp or current_user.points or 0}\n"
        f"- Level: {current_user.level or 1}\n"
        f"- Badges Earned: {', '.join(badges) if badges else 'None'}\n"
        f"- Identified Weak Topics: {', '.join(weak_topics) if weak_topics else 'None'}\n"
    )

    answer = chatbot_answer(question, context)
    return jsonify({"answer": answer})


@app.route('/student/explain_question', methods=['POST'])
@login_required
def explain_question():
    if current_user.role != 'student':
        return jsonify({"error": "forbidden"}), 403
        
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400
        
    question_id = data.get("question_id")
    student_answer = data.get("student_answer", "Unanswered")
    correct_answer = data.get("correct_answer", "N/A")
    
    if not question_id:
        return jsonify({"error": "Missing question_id"}), 400
        
    question = Question.query.get(question_id)
    if not question:
        return jsonify({"error": "Question not found"}), 404
        
    from app.utils import generate_question_explanation
    explanation = generate_question_explanation(
        question_text=question.text,
        student_answer=student_answer,
        correct_answer=correct_answer
    )
    
    return jsonify({"explanation": explanation})

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
    students = User.query.filter_by(role='student').order_by(User.points.desc()).all()
    return render_template('leaderboard.html', students=students)


# Teacher Gradebook Export & Printable Report Routes
@app.route('/teacher/assessment/<int:assessment_id>/export_csv')
@login_required
def export_assessment_csv(assessment_id):
    if current_user.role != 'teacher':
        flash('Only teachers can export assessment gradebooks.')
        return redirect(url_for('login'))

    assessment = Assessment.query.get_or_404(assessment_id)
    attempts = StudentAssessmentAttempt.query.filter_by(assessment_id=assessment_id).all()

    import csv
    import io
    from flask import Response

    output = io.StringIO()
    writer = csv.writer(output)

    # Write Header
    writer.writerow([
        'Student Name',
        'Username',
        'Class / Year',
        'Semester',
        'Score (%)',
        'Completed',
        'Watched Video',
        'Attempt Date'
    ])

    # Write Student Rows
    for att in attempts:
        student = att.student
        writer.writerow([
            student.full_name or student.username if student else 'Unknown',
            student.username if student else 'N/A',
            student.class_year if student else 'N/A',
            student.semester if student else 'N/A',
            att.score,
            'Yes' if att.completed else 'No',
            'Yes' if att.watched_video_for_weak_topic else 'No',
            att.created_at.strftime('%Y-%m-%d %H:%M:%S') if att.created_at else 'N/A'
        ])

    csv_data = output.getvalue()
    filename = f"gradebook_assessment_{assessment_id}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )


@app.route('/teacher/assessment/<int:assessment_id>/report_print')
@login_required
def report_assessment_print(assessment_id):
    if current_user.role != 'teacher':
        flash('Only teachers can view performance reports.')
        return redirect(url_for('login'))

    assessment = Assessment.query.get_or_404(assessment_id)
    attempts = StudentAssessmentAttempt.query.filter_by(assessment_id=assessment_id).all()
    questions = Question.query.filter_by(assessment_id=assessment_id).all()

    scores = [att.score for att in attempts]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    highest_score = max(scores) if scores else 0
    lowest_score = min(scores) if scores else 0
    pass_count = sum(1 for s in scores if s >= 60)

    # Topic performance statistics
    from collections import defaultdict
    topic_totals = defaultdict(lambda: {'correct': 0, 'total': 0})
    for att in attempts:
        if not att.answers_json:
            continue
        try:
            answers_map = json.loads(att.answers_json)
            for q in questions:
                chosen = answers_map.get(str(q.id))
                is_correct = chosen is not None and int(chosen) == int(q.correct_index)
                if is_correct:
                    topic_totals[q.topic]['correct'] += 1
                topic_totals[q.topic]['total'] += 1
        except Exception:
            continue

    topic_percent = {}
    for topic, stats in topic_totals.items():
        if stats['total'] > 0:
            topic_percent[topic] = round((stats['correct'] / stats['total']) * 100, 1)

    return render_template(
        'teacher/print_report.html',
        assessment=assessment,
        attempts=attempts,
        questions=questions,
        avg_score=avg_score,
        highest_score=highest_score,
        lowest_score=lowest_score,
        pass_count=pass_count,
        topic_percent=topic_percent
    )


# ---------- Attendance Management Routes ----------

@app.route('/teacher/attendance', methods=['GET', 'POST'])
@login_required
def teacher_attendance():
    if current_user.role != 'teacher':
        return "Forbidden", 403

    teacher_subjects = Subject.query.filter_by(teacher_id=current_user.id).all()
    all_students = User.query.filter_by(role='student').order_by(User.full_name, User.username).all()

    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        date_str = request.form.get('date')

        if not subject_id or not date_str:
            flash("Subject and Date are required.", "danger")
            return redirect(url_for('teacher_attendance'))

        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(url_for('teacher_attendance'))

        subject = Subject.query.get_or_404(subject_id)
        if subject.teacher_id != current_user.id:
            return "Forbidden", 403

        # Form fields for student status are passed as `status_<student_id>`
        count_updated = 0
        for student in all_students:
            status_val = request.form.get(f'status_{student.id}')
            if status_val in ['Present', 'Absent']:
                record = Attendance.query.filter_by(
                    student_id=student.id,
                    subject_id=subject.id,
                    date=date_obj
                ).first()

                if record:
                    record.status = status_val
                    record.teacher_id = current_user.id
                else:
                    new_rec = Attendance(
                        student_id=student.id,
                        subject_id=subject.id,
                        teacher_id=current_user.id,
                        date=date_obj,
                        status=status_val
                    )
                    db.session.add(new_rec)
                count_updated += 1

        db.session.commit()
        flash(f"Attendance for {subject.name} on {date_str} saved successfully! ({count_updated} records updated)", "success")
        return redirect(url_for('teacher_attendance', subject_id=subject_id, date=date_str))

    # GET handling
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_date_str = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    
    # Defaults to first teacher subject if available
    selected_subject = None
    if selected_subject_id:
        selected_subject = Subject.query.get(selected_subject_id)
    elif teacher_subjects:
        selected_subject = teacher_subjects[0]

    # Enrolled students for marking
    enrolled_students = []
    attendance_map = {}
    selected_date_obj = None

    if selected_subject:
        # Filter students matching subject class_year/semester if present, else all students
        if selected_subject.class_year or selected_subject.semester:
            enrolled_students = [
                s for s in all_students
                if (not selected_subject.class_year or s.class_year == selected_subject.class_year) and
                   (not selected_subject.semester or s.semester == selected_subject.semester)
            ]
        else:
            enrolled_students = all_students

        try:
            selected_date_obj = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            existing_recs = Attendance.query.filter_by(
                subject_id=selected_subject.id,
                date=selected_date_obj
            ).all()
            attendance_map = {r.student_id: r.status for r in existing_recs}
        except ValueError:
            selected_date_str = datetime.utcnow().strftime('%Y-%m-%d')
            selected_date_obj = datetime.utcnow().date()

    # Attendance History & Filtering
    filter_date = request.args.get('filter_date')
    filter_student_id = request.args.get('filter_student_id', type=int)
    filter_status = request.args.get('filter_status')
    filter_subject_id = request.args.get('filter_subject_id', type=int)

    history_query = Attendance.query.join(Subject).filter(Subject.teacher_id == current_user.id)

    if filter_subject_id:
        history_query = history_query.filter(Attendance.subject_id == filter_subject_id)
    if filter_date:
        try:
            f_date_obj = datetime.strptime(filter_date, '%Y-%m-%d').date()
            history_query = history_query.filter(Attendance.date == f_date_obj)
        except ValueError:
            pass
    if filter_student_id:
        history_query = history_query.filter(Attendance.student_id == filter_student_id)
    if filter_status in ['Present', 'Absent']:
        history_query = history_query.filter(Attendance.status == filter_status)

    history_records = history_query.order_by(Attendance.date.desc(), Attendance.id.desc()).all()

    return render_template(
        'teacher/teacher_attendance.html',
        subjects=teacher_subjects,
        selected_subject=selected_subject,
        selected_date=selected_date_str,
        enrolled_students=enrolled_students,
        attendance_map=attendance_map,
        all_students=all_students,
        history_records=history_records,
        filter_date=filter_date,
        filter_student_id=filter_student_id,
        filter_status=filter_status,
        filter_subject_id=filter_subject_id,
        hide_sidebar=True
    )


@app.route('/student/attendance')
@login_required
def student_attendance():
    if current_user.role != 'student':
        return "Forbidden", 403

    records = Attendance.query.filter_by(student_id=current_user.id).order_by(Attendance.date.desc()).all()

    total_classes = len(records)
    total_present = sum(1 for r in records if r.status == 'Present')
    total_absent = sum(1 for r in records if r.status == 'Absent')
    overall_percentage = round((total_present / total_classes * 100), 1) if total_classes > 0 else 0.0

    # Subject-wise statistics
    from collections import defaultdict
    subject_stats_dict = defaultdict(lambda: {'subject': None, 'total': 0, 'present': 0, 'absent': 0})

    # Find all subjects enrolled / relevant for student
    student_subjects = Subject.query.filter(
        (Subject.class_year == current_user.class_year) | (Subject.class_year == None)
    ).all()

    for sub in student_subjects:
        subject_stats_dict[sub.id]['subject'] = sub

    for r in records:
        if r.subject_id not in subject_stats_dict:
            subject_stats_dict[r.subject_id]['subject'] = r.subject
        subject_stats_dict[r.subject_id]['total'] += 1
        if r.status == 'Present':
            subject_stats_dict[r.subject_id]['present'] += 1
        elif r.status == 'Absent':
            subject_stats_dict[r.subject_id]['absent'] += 1

    subject_wise = []
    for s_id, stats in subject_stats_dict.items():
        if stats['subject']:
            tot = stats['total']
            pres = stats['present']
            pct = round((pres / tot * 100), 1) if tot > 0 else 0.0
            subject_wise.append({
                'subject': stats['subject'],
                'total': tot,
                'present': pres,
                'absent': stats['absent'],
                'percentage': pct
            })

    return render_template(
        'student/student_attendance.html',
        records=records,
        total_classes=total_classes,
        total_present=total_present,
        total_absent=total_absent,
        overall_percentage=overall_percentage,
        subject_wise=subject_wise
    )


# ---------- Learning Materials / Resources Module ----------

def _detect_file_type(filename):
    if not filename:
        return 'text'
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext in ['pdf']:
        return 'pdf'
    elif ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg']:
        return 'image'
    elif ext in ['ppt', 'pptx']:
        return 'ppt'
    elif ext in ['doc', 'docx', 'txt', 'rtf', 'odt']:
        return 'doc'
    else:
        return 'other'

@app.route('/teacher/materials', methods=['GET', 'POST'])
@login_required
def teacher_materials():
    if current_user.role != 'teacher':
        flash('Access restricted to teachers.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        subject_id = request.form.get('subject_id')
        target_class = request.form.get('target_class', 'All').strip()
        external_url = request.form.get('external_url', '').strip()
        file_type_override = request.form.get('file_type')

        if not title:
            flash('Title is required to create a resource.', 'warning')
            return redirect(url_for('teacher_materials'))

        subject_id_int = int(subject_id) if subject_id and subject_id.isdigit() else None
        
        file_path = None
        file_name = None
        detected_type = 'text'

        file = request.files.get('file')
        if file and file.filename != '':
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'materials')
            os.makedirs(upload_dir, exist_ok=True)

            orig_filename = secure_filename(file.filename)
            timestamp_prefix = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            saved_filename = f"{timestamp_prefix}_{orig_filename}"
            full_save_path = os.path.join(upload_dir, saved_filename)
            file.save(full_save_path)

            file_path = f"uploads/materials/{saved_filename}"
            file_name = file.filename
            detected_type = _detect_file_type(file.filename)

        final_file_type = file_type_override if (file_type_override and file_type_override != 'auto') else detected_type

        material = LearningMaterial(
            title=title,
            description=description,
            file_path=file_path,
            file_name=file_name,
            file_type=final_file_type,
            external_url=external_url if external_url else None,
            teacher_id=current_user.id,
            subject_id=subject_id_int,
            target_class=target_class if target_class else 'All'
        )

        db.session.add(material)
        db.session.commit()
        flash('Learning Material published successfully!', 'success')
        return redirect(url_for('teacher_materials'))

    # GET request
    my_subjects = Subject.query.filter_by(teacher_id=current_user.id).all()
    materials = LearningMaterial.query.filter_by(teacher_id=current_user.id).order_by(LearningMaterial.created_at.desc()).all()
    
    classes = db.session.query(User.class_year).filter(User.role == 'student', User.class_year != None).distinct().all()
    class_list = sorted([c[0] for c in classes if c[0]])
    
    return render_template('teacher/teacher_materials.html', subjects=my_subjects, materials=materials, class_list=class_list)


@app.route('/teacher/materials/delete/<int:material_id>', methods=['POST'])
@login_required
def delete_material(material_id):
    if current_user.role != 'teacher':
        flash('Access restricted.', 'danger')
        return redirect(url_for('login'))

    material = LearningMaterial.query.get_or_404(material_id)
    if material.teacher_id != current_user.id and current_user.role != 'admin':
        flash('You can only delete your own published materials.', 'danger')
        return redirect(url_for('teacher_materials'))

    if material.file_path:
        full_path = os.path.join(current_app.root_path, 'static', material.file_path)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except Exception as e:
                current_app.logger.warning(f"Could not delete physical file: {e}")

    db.session.delete(material)
    db.session.commit()
    flash('Resource deleted successfully.', 'success')
    return redirect(url_for('teacher_materials'))


@app.route('/student/materials', methods=['GET'])
@login_required
def student_materials():
    if current_user.role != 'student':
        flash('Access restricted to students.', 'danger')
        return redirect(url_for('login'))

    subject_id = request.args.get('subject_id')
    file_type = request.args.get('type')
    search_query = request.args.get('q', '').strip()

    query = LearningMaterial.query.filter(
        (LearningMaterial.target_class == current_user.class_year) |
        (LearningMaterial.target_class == 'All') |
        (LearningMaterial.target_class == None) |
        (LearningMaterial.target_class == '')
    )

    if subject_id and subject_id.isdigit():
        query = query.filter(LearningMaterial.subject_id == int(subject_id))

    if file_type and file_type != 'all':
        query = query.filter(LearningMaterial.file_type == file_type)

    if search_query:
        query = query.filter(
            (LearningMaterial.title.ilike(f"%{search_query}%")) |
            (LearningMaterial.description.ilike(f"%{search_query}%"))
        )

    materials = query.order_by(LearningMaterial.created_at.desc()).all()

    subjects = Subject.query.filter(
        (Subject.class_year == current_user.class_year) | (Subject.class_year == None)
    ).all()

    return render_template(
        'student/student_materials.html',
        materials=materials,
        subjects=subjects,
        selected_subject_id=int(subject_id) if (subject_id and subject_id.isdigit()) else None,
        selected_type=file_type or 'all',
        search_query=search_query
    )


@app.route('/materials/download/<int:material_id>')
@login_required
def download_material(material_id):
    material = LearningMaterial.query.get_or_404(material_id)
    if not material.file_path:
        flash('No attached file for this resource.', 'warning')
        return redirect(request.referrer or url_for('student_materials'))

    relative_dir = os.path.dirname(material.file_path)
    file_name = os.path.basename(material.file_path)
    directory = os.path.join(current_app.root_path, 'static', relative_dir)

    return send_from_directory(directory, file_name, as_attachment=True, download_name=material.file_name or file_name)




