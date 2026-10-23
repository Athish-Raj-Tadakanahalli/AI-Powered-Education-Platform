import json
from app import create_app, db
from app.models import User, Subject, Assessment, Question, StudentAssessmentAttempt
from app.utils import (
    calculate_radar_skills,
    get_course_skill_tree,
    ensure_skill_tree_assessments,
    RADAR_DOMAINS
)

def run_tests():
    app = create_app()
    with app.app_context():
        print("=== Test 1: Radar Calculation Initial Baseline ===")
        # Create a test student
        test_student = User.query.filter_by(username="radar_student_test").first()
        if not test_student:
            test_student = User(
                username="radar_student_test",
                full_name="Radar Test Student",
                password_hash=User.hash_password("password123"),
                role="student",
                is_approved=True,
                approval_status="approved"
            )
            db.session.add(test_student)
            db.session.commit()

        # Clean previous attempts for test student
        StudentAssessmentAttempt.query.filter_by(student_id=test_student.id).delete()
        db.session.commit()

        radar = calculate_radar_skills(test_student, db.session)
        assert len(radar["labels"]) == 5, f"Expected 5 labels, got {len(radar['labels'])}"
        assert len(radar["values"]) == 5, f"Expected 5 values, got {len(radar['values'])}"
        assert all(b == "Untested" for b in radar["badges"]), "Expected initial badges to be 'Untested'"
        print("[PASS] Initial radar chart baseline initialized correctly!")

        print("\n=== Test 2: Auto-Seeding Skill Tree Assessments ===")
        ensure_skill_tree_assessments(db.session)
        # Check that 6 skill tree quizzes exist
        asmts = Assessment.query.all()
        assert len(asmts) >= 6, f"Expected at least 6 assessments, found {len(asmts)}"
        print(f"[PASS] Successfully ensured {len(asmts)} skill tree assessments exist in database!")

        print("\n=== Test 3: Course Skill Tree Prerequisite Locking ===")
        tree = get_course_skill_tree(test_student, db.session)
        nodes = tree["nodes"]
        assert len(nodes) == 6, f"Expected 6 skill nodes, got {len(nodes)}"

        # Node 1 should be available
        assert nodes[0]["id"] == "basics_syntax", f"First node should be basics_syntax"
        assert nodes[0]["status"] == "available", f"Node 1 should be available initially, got {nodes[0]['status']}"

        # Node 2 should be locked
        assert nodes[1]["id"] == "control_loops"
        assert nodes[1]["status"] == "locked", f"Node 2 should be locked initially, got {nodes[1]['status']}"
        assert nodes[2]["status"] == "locked", f"Node 3 should be locked initially, got {nodes[2]['status']}"
        print("[PASS] Skill Tree locks subsequent nodes until prerequisite is passed!")

        print("\n=== Test 4: Node Unlocking Upon Achieving >= 60% Score ===")
        # Find Node 1's assessment
        node1_asmt = Assessment.query.filter_by(title="Basics & Syntax Quiz").first()
        assert node1_asmt is not None, "Basics & Syntax Quiz must exist"

        # Attempt Node 1 with 100% score
        answers = {str(q.id): q.correct_index for q in node1_asmt.questions}
        attempt1 = StudentAssessmentAttempt(
            student_id=test_student.id,
            assessment_id=node1_asmt.id,
            answers_json=json.dumps(answers),
            score=100.0,
            completed=True
        )
        db.session.add(attempt1)
        db.session.commit()

        # Re-evaluate tree
        tree_after = get_course_skill_tree(test_student, db.session)
        nodes_after = tree_after["nodes"]

        # Node 1 should now be mastered
        assert nodes_after[0]["status"] == "mastered", f"Node 1 should be mastered, got {nodes_after[0]['status']}"
        assert nodes_after[0]["score"] == 100.0

        # Node 2 should now be unlocked to 'available'
        assert nodes_after[1]["status"] == "available", f"Node 2 should now be unlocked, got {nodes_after[1]['status']}"

        # Node 3 should still be locked
        assert nodes_after[2]["status"] == "locked", f"Node 3 should remain locked, got {nodes_after[2]['status']}"
        print("[PASS] Node 1 marked mastered and Node 2 successfully unlocked!")

        print("\n=== Test 5: Radar Proficiency Update from Quiz Answers ===")
        radar_updated = calculate_radar_skills(test_student, db.session)
        syntax_idx = radar_updated["labels"].index("Syntax & Fundamentals")
        syntax_score = radar_updated["values"][syntax_idx]
        assert syntax_score == 100, f"Expected Syntax score 100%, got {syntax_score}%"
        assert radar_updated["badges"][syntax_idx] == "Master", f"Expected 'Master' badge, got {radar_updated['badges'][syntax_idx]}"
        print(f"[PASS] Radar chart proficiency updated! Syntax & Fundamentals: {syntax_score}% ({radar_updated['badges'][syntax_idx]})")

        print("\n=== Test 6: Route Rendering with Test Client ===")
        client = app.test_client()
        # Login test student
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_student.id)
            sess['_fresh'] = True

        # Check dashboard
        dash_res = client.get('/student/dashboard')
        assert dash_res.status_code == 200, f"Dashboard failed with {dash_res.status_code}"
        assert b"Knowledge Radar" in dash_res.data, "Dashboard missing Knowledge Radar"
        assert b"Course Skill Tree" in dash_res.data, "Dashboard missing Course Skill Tree"
        assert b"radarChart" in dash_res.data, "Dashboard missing radarChart canvas"
        print("[PASS] /student/dashboard rendered Knowledge Radar and Course Skill Tree successfully!")

        # Check dedicated /student/skill-tree page
        tree_res = client.get('/student/skill-tree')
        assert tree_res.status_code == 200, f"Skill tree page failed with {tree_res.status_code}"
        assert b"Computer Science Skill Tree" in tree_res.data, "Skill tree page missing title"
        assert b"treeRadarChart" in tree_res.data, "Skill tree page missing radar canvas"
        assert b"Basics &amp; Syntax" in tree_res.data or b"Basics & Syntax" in tree_res.data, "Skill tree page missing node 1"
        print("[PASS] /student/skill-tree rendered full talent tree and radar chart successfully!")

        # Clean up test user
        StudentAssessmentAttempt.query.filter_by(student_id=test_student.id).delete()
        db.session.delete(test_student)
        db.session.commit()

        print("\n=== ALL SKILL TREE & RADAR TESTS PASSED! ===")

if __name__ == "__main__":
    run_tests()
