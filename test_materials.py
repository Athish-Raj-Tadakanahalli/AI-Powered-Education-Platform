import os
import sys

# Ensure correct path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from app import create_app, db
from app.models import User, Subject, LearningMaterial

def test_learning_materials():
    app = create_app()
    with app.app_context():
        print("1. Creating DB tables...")
        db.create_all()

        print("2. Checking for teacher and student users...")
        teacher = User.query.filter_by(role='teacher').first()
        student = User.query.filter_by(role='student').first()

        if not teacher:
            print("Creating sample teacher...")
            teacher = User(username="sample_teacher", password_hash=User.hash_password("teacher123"), role="teacher", full_name="Prof. Alan Smith")
            db.session.add(teacher)
            db.session.commit()

        if not student:
            print("Creating sample student...")
            student = User(username="sample_student", password_hash=User.hash_password("student123"), role="student", full_name="Alex Johnson", class_year="CSE-3")
            db.session.add(student)
            db.session.commit()

        print("3. Checking for sample subject...")
        subject = Subject.query.filter_by(teacher_id=teacher.id).first()
        if not subject:
            subject = Subject(name="Data Structures & Algorithms", teacher_id=teacher.id, class_year="CSE-3")
            db.session.add(subject)
            db.session.commit()

        print("4. Creating sample Learning Material...")
        material = LearningMaterial(
            title="Module 1: Array & Linked List Lecture Notes",
            description="Comprehensive guide covering memory allocation, pointer manipulation, and dynamic arrays.",
            file_type="pdf",
            file_name="module1_dsa_notes.pdf",
            file_path="uploads/materials/sample_dsa_notes.pdf",
            teacher_id=teacher.id,
            subject_id=subject.id,
            target_class="All"
        )
        db.session.add(material)
        db.session.commit()
        print(f"   Created material ID: {material.id} - '{material.title}'")

        print("5. Querying published materials for Student...")
        student_query = LearningMaterial.query.filter(
            (LearningMaterial.target_class == student.class_year) | (LearningMaterial.target_class == 'All')
        ).all()
        
        print(f"   Found {len(student_query)} material(s) for student in class {student.class_year}:")
        for m in student_query:
            print(f"   - [{m.file_type.upper()}] {m.title} (Subject: {m.subject.name if m.subject else 'General'}, Teacher: {m.teacher.full_name})")

        print("\nSUCCESS: Learning Materials test completed cleanly!")

if __name__ == '__main__':
    test_learning_materials()
