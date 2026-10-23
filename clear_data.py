import os
import sys
from app import create_app, db
from app.models import (
    User, Subject, Assessment, Question, 
    StudentAssessmentAttempt, Attendance, LearningMaterial
)

def clear_all_data():
    app = create_app()
    with app.app_context():
        print("--- Starting Database Cleanup ---")
        
        # 1. Delete Student Assessment Attempts
        attempts_count = StudentAssessmentAttempt.query.delete()
        print(f"Deleted {attempts_count} assessment attempt(s).")

        # 2. Delete Attendance Records
        attendance_count = Attendance.query.delete()
        print(f"Deleted {attendance_count} attendance record(s).")

        # 3. Delete Learning Materials
        materials_count = LearningMaterial.query.delete()
        print(f"Deleted {materials_count} learning material(s).")

        # 4. Delete Questions & Assessments
        questions_count = Question.query.delete()
        print(f"Deleted {questions_count} question(s).")

        assessments_count = Assessment.query.delete()
        print(f"Deleted {assessments_count} assessment(s).")

        # 5. Delete Subjects
        subjects_count = Subject.query.delete()
        print(f"Deleted {subjects_count} subject(s).")

        # 6. Delete all Teachers and Students
        users_to_delete = User.query.filter(User.role.in_(['student', 'teacher'])).all()
        deleted_users_count = len(users_to_delete)
        for u in users_to_delete:
            db.session.delete(u)
        print(f"Deleted {deleted_users_count} student & teacher user account(s).")

        # 7. Ensure Admin account exists and is approved
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=User.hash_password("admin123"),
                role="admin",
                full_name="Administrator"
            )
            db.session.add(admin)
            print("Created default Admin account (username: 'admin', password: 'admin123').")
        else:
            admin.password_hash = User.hash_password("admin123")
            print("Reset existing Admin account password (username: 'admin', password: 'admin123').")

        db.session.commit()
        print("--- Database Cleanup Complete! ---")

if __name__ == "__main__":
    clear_all_data()
