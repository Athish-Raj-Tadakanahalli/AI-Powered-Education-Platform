
import sys
from app import create_app, db
from app.models import User, StudentAssessmentAttempt, Subject

def delete_user(username):
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"Error: User '{username}' not found.")
            return False
        
        print(f"Found user '{username}' with role '{user.role}'.")
        
        if user.role == 'student':
            # Delete attempts
            attempts_deleted = StudentAssessmentAttempt.query.filter_by(student_id=user.id).delete()
            print(f"Deleted {attempts_deleted} assessment attempt(s) for student '{username}'.")
            
        elif user.role == 'teacher':
            # Reassign or nullify subjects
            subjects = Subject.query.filter_by(teacher_id=user.id).all()
            for s in subjects:
                s.teacher_id = None
            print(f"Nullified teacher_id for {len(subjects)} subject(s) assigned to teacher '{username}'.")
            
        db.session.delete(user)
        db.session.commit()
        print(f"Successfully deleted user '{username}' from database.")
        return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python delete_user.py <username>")
        sys.exit(1)
    
    username_to_delete = sys.argv[1]
    delete_user(username_to_delete)
