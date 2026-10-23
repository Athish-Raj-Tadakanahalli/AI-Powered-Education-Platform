import os
import sys
from datetime import datetime, date

# Add project path to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Subject, Attendance

app = create_app()

def test_attendance_system():
    print("=== Testing Attendance System Integration ===")
    with app.app_context():
        # Ensure database tables are created
        db.create_all()
        
        # Fetch or create sample teacher and student
        teacher = User.query.filter_by(role='teacher').first()
        if not teacher:
            teacher = User(
                username="test_teacher_att",
                password_hash=User.hash_password("password123"),
                role="teacher",
                full_name="Test Teacher Attendance"
            )
            db.session.add(teacher)
            db.session.commit()

        student = User.query.filter_by(role='student').first()
        if not student:
            student = User(
                username="test_student_att",
                password_hash=User.hash_password("password123"),
                role="student",
                full_name="Test Student Attendance",
                class_year="CSE-2026",
                semester="Sem 6"
            )
            db.session.add(student)
            db.session.commit()

        subject = Subject.query.filter_by(teacher_id=teacher.id).first()
        if not subject:
            subject = Subject(
                name="Software Engineering & AI Architecture",
                teacher_id=teacher.id,
                class_year="CSE-2026",
                semester="Sem 6"
            )
            db.session.add(subject)
            db.session.commit()

        today = date.today()

        print(f"Teacher: {teacher.username} (ID: {teacher.id})")
        print(f"Student: {student.username} (ID: {student.id})")
        print(f"Subject: {subject.name} (ID: {subject.id})")
        print(f"Date: {today}")

        # 1. Add / Upsert Attendance record
        rec = Attendance.query.filter_by(
            student_id=student.id,
            subject_id=subject.id,
            date=today
        ).first()

        if rec:
            rec.status = 'Present'
        else:
            rec = Attendance(
                student_id=student.id,
                subject_id=subject.id,
                teacher_id=teacher.id,
                date=today,
                status='Present'
            )
            db.session.add(rec)
        
        db.session.commit()
        print("[+] Attendance record created/updated successfully!")

        # 2. Query Student Attendance Statistics
        records = Attendance.query.filter_by(student_id=student.id).all()
        total_classes = len(records)
        present_count = sum(1 for r in records if r.status == 'Present')
        absent_count = sum(1 for r in records if r.status == 'Absent')
        overall_pct = round((present_count / total_classes * 100), 1) if total_classes > 0 else 0.0

        print(f"\n--- Student Attendance Summary ---")
        print(f"Total Sessions: {total_classes}")
        print(f"Present: {present_count}")
        print(f"Absent: {absent_count}")
        print(f"Overall Percentage: {overall_pct}%")

        assert total_classes > 0
        assert present_count > 0
        print("\nAll Attendance integration tests passed successfully! [OK]")

if __name__ == "__main__":
    test_attendance_system()
