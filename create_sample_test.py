import json
import os
import sys

# Ensure project path is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Subject, Assessment, Question

app = create_app()

def create_sample_assessment():
    with app.app_context():
        # Find or pick a teacher
        teacher = User.query.filter_by(role='teacher').first()
        if not teacher:
            teacher = User.query.filter_by(role='admin').first()

        teacher_id = teacher.id if teacher else None

        # 1. Create or get Subject
        subject_name = "Core Computer Science & AI Fundamentals"
        subject = Subject.query.filter_by(name=subject_name).first()
        if not subject:
            subject = Subject(
                name=subject_name,
                teacher_id=teacher_id,
                class_year="CSE-2026",
                semester="Sem 6"
            )
            db.session.add(subject)
            db.session.commit()
            print(f"[+] Created Subject: '{subject.name}' (ID: {subject.id})")
        else:
            print(f"[*] Using existing Subject: '{subject.name}' (ID: {subject.id})")

        # 2. Create Assessment
        assessment_title = "Sample Practice Assessment - CS & Data Structures"
        assessment = Assessment(
            title=assessment_title,
            subject_id=subject.id
        )
        db.session.add(assessment)
        db.session.commit()
        print(f"[+] Created Assessment: '{assessment.title}' (ID: {assessment.id})")

        # 3. Add Sample Questions across various topics
        sample_questions = [
            {
                "text": "Which data structure follows the Last-In, First-Out (LIFO) principle?",
                "options": ["Queue", "Stack", "Array", "Linked List"],
                "correct_index": 1,
                "topic": "Data Structures"
            },
            {
                "text": "What is the worst-case time complexity of QuickSort?",
                "options": ["O(n log n)", "O(n)", "O(n^2)", "O(1)"],
                "correct_index": 2,
                "topic": "Algorithms"
            },
            {
                "text": "In a relational database (DBMS), what does the 'ACID' property 'I' stand for?",
                "options": ["Integrity", "Isolation", "Index", "Inheritance"],
                "correct_index": 1,
                "topic": "Database Systems"
            },
            {
                "text": "Which OSI layer is responsible for routing packets across network boundaries?",
                "options": ["Data Link Layer", "Transport Layer", "Network Layer", "Application Layer"],
                "correct_index": 2,
                "topic": "Computer Networks"
            },
            {
                "text": "What is the primary function of an Operating System's Virtual Memory mechanism?",
                "options": [
                    "Accelerate CPU clock speed",
                    "Extend physical RAM space using secondary storage",
                    "Encrypt file permissions",
                    "Manage GPU rendering pipelines"
                ],
                "correct_index": 1,
                "topic": "Operating Systems"
            },
            {
                "text": "In Python, which of the following data types is immutable?",
                "options": ["List", "Dictionary", "Set", "Tuple"],
                "correct_index": 3,
                "topic": "Python Programming"
            }
        ]

        for q_data in sample_questions:
            q = Question(
                assessment_id=assessment.id,
                text=q_data["text"],
                options_json=json.dumps(q_data["options"]),
                correct_index=q_data["correct_index"],
                topic=q_data["topic"]
            )
            db.session.add(q)
        
        db.session.commit()
        print(f"[+] Successfully added {len(sample_questions)} sample questions to Assessment #{assessment.id}!")
        print("\n--- Summary of Created Sample Assessment ---")
        print(f"ID: {assessment.id}")
        print(f"Title: {assessment.title}")
        print(f"Subject: {subject.name}")
        print(f"Total Questions: {len(sample_questions)}")
        for idx, q in enumerate(sample_questions, 1):
            print(f"  Q{idx} [{q['topic']}]: {q['text']}")

if __name__ == "__main__":
    create_sample_assessment()
