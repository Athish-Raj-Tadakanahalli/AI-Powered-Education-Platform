import os
import sys
import json

# Add project path to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Subject, Assessment, Question, StudentAssessmentAttempt
from app.utils import grade_attempt, find_weak_topics

app = create_app()

def test_assessment_workflow():
    print("=== Testing Assessment & Grading Integration ===")
    with app.app_context():
        db.create_all()
        
        # 1. Fetch or create teacher
        teacher = User.query.filter_by(role='teacher').first()
        if not teacher:
            teacher = User(
                username="test_teacher_assessment",
                password_hash=User.hash_password("password123"),
                role="teacher",
                full_name="Assessment Test Teacher"
            )
            db.session.add(teacher)
            db.session.commit()

        # 2. Fetch or create student
        student = User.query.filter_by(role='student').first()
        if not student:
            student = User(
                username="test_student_assessment",
                password_hash=User.hash_password("password123"),
                role="student",
                full_name="Assessment Test Student",
                class_year="CSE-2026",
                semester="Sem 6"
            )
            db.session.add(student)
            db.session.commit()

        # 3. Create test subject & assessment
        subject = Subject(
            name="Sample Test Subject - CS Principles",
            teacher_id=teacher.id,
            class_year="CSE-2026",
            semester="Sem 6"
        )
        db.session.add(subject)
        db.session.commit()

        assessment = Assessment(
            title="Sample Assessment Test Suite",
            subject_id=subject.id
        )
        db.session.add(assessment)
        db.session.commit()

        q1 = Question(
            assessment_id=assessment.id,
            text="What is the time complexity of searching in a balanced BST?",
            options_json=json.dumps(["O(1)", "O(log n)", "O(n)", "O(n^2)"]),
            correct_index=1,
            topic="Data Structures"
        )
        q2 = Question(
            assessment_id=assessment.id,
            text="Which HTTP status code represents 'Not Found'?",
            options_json=json.dumps(["200", "401", "404", "500"]),
            correct_index=2,
            topic="Web Development"
        )
        db.session.add_all([q1, q2])
        db.session.commit()

        print(f"Created Assessment ID {assessment.id} with 2 Questions.")

        # 4. Grade simulated student submission (q1 correct, q2 incorrect)
        questions = Question.query.filter_by(assessment_id=assessment.id).all()
        answers_map = {
            str(q1.id): "1",  # Correct
            str(q2.id): "0"   # Incorrect
        }

        score, per_q, topic_stats = grade_attempt(questions, answers_map)
        print(f"Calculated Score: {score}%")
        print(f"Per Question Correctness: {per_q}")
        print(f"Topic Stats: {dict(topic_stats)}")

        assert score == 50.0
        assert per_q[q1.id] is True
        assert per_q[q2.id] is False

        weak_topics = find_weak_topics(topic_stats, threshold=0.6)
        print(f"Weak Topics identified: {weak_topics}")
        weak_topic_names = [t[0] for t in weak_topics]
        assert "Web Development" in weak_topic_names

        # 5. Record attempt in DB
        attempt = StudentAssessmentAttempt(
            student_id=student.id,
            assessment_id=assessment.id,
            answers_json=json.dumps(answers_map),
            score=score,
            completed=True
        )
        db.session.add(attempt)
        db.session.commit()
        print(f"[+] Assessment attempt ID {attempt.id} successfully recorded!")

        print("\nAll Assessment integration tests passed successfully! [OK]")

if __name__ == "__main__":
    test_assessment_workflow()
