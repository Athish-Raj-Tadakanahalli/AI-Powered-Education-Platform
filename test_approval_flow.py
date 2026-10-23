import os
from app import create_app, db
from app.models import User

def test_full_approval_workflow():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    client = app.test_client()

    with app.app_context():
        print("=== Step 1: Testing Student Registration ===")
        # Student registers
        reg_response = client.post('/register', data={
            'username': 'student_alice',
            'full_name': 'Alice Wonder',
            'email': 'alice@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'class_year': 'CSE',
            'semester': '4'
        }, follow_redirects=True)
        
        assert reg_response.status_code == 200
        alice = User.query.filter_by(username='student_alice').first()
        assert alice is not None, "Alice should exist in DB"
        assert alice.is_approved is False, "Alice should NOT be approved yet"
        assert alice.approval_status == 'pending', "Status should be pending"
        print("[PASS] Student registered successfully with pending status!")

        print("\n=== Step 2: Testing Blocked Login for Pending Student ===")
        # Alice tries to log in
        login_response = client.post('/', data={
            'username': 'student_alice',
            'password': 'password123'
        }, follow_redirects=True)
        
        # Should remain on login page with warning message
        assert b"awaiting administrator approval" in login_response.data
        print("[PASS] Login correctly blocked with message: 'awaiting administrator approval'!")

        print("\n=== Step 3: Testing Admin View of Pending Request Page ===")
        # Admin logs in
        admin_login = client.post('/', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)
        assert admin_login.status_code == 200
        
        # Check admin dashboard
        dash_response = client.get('/admin')
        assert b"Pending Student Requests" in dash_response.data
        assert b"Review Requests" in dash_response.data
        print("[PASS] Admin dashboard displays pending requests link!")

        # Check dedicated pending requests page
        pending_page_response = client.get('/admin/pending_requests')
        assert pending_page_response.status_code == 200
        assert b"Alice Wonder" in pending_page_response.data
        assert b"@student_alice" in pending_page_response.data
        assert b"Student Account Requests" in pending_page_response.data
        print("[PASS] Dedicated /admin/pending_requests page lists pending students and actions!")

        print("\n=== Step 4: Testing Admin Approval ===")
        approve_response = client.post(f'/admin/approve_student/{alice.id}', follow_redirects=True)
        assert approve_response.status_code == 200
        
        db.session.refresh(alice)
        assert alice.is_approved is True, "Alice should now be approved"
        assert alice.approval_status == 'approved', "Alice status should be approved"
        print("[PASS] Student approved successfully by admin!")

        print("\n=== Step 5: Testing Approved Student Login ===")
        # Log out admin
        client.get('/logout')
        
        # Alice logs in now
        alice_login = client.post('/', data={
            'username': 'student_alice',
            'password': 'password123'
        }, follow_redirects=True)
        
        assert alice_login.status_code == 200
        assert b"Student" in alice_login.data or b"Dashboard" in alice_login.data
        print("[PASS] Approved student successfully logged in and accessed student dashboard!")

        print("\n=== Step 6: Testing Admin Rejection Flow ===")
        # Register Bob
        client.get('/logout')
        client.post('/register', data={
            'username': 'student_bob',
            'full_name': 'Bob Builder',
            'password': 'password123',
            'confirm_password': 'password123',
            'class_year': 'IT',
            'semester': '2'
        }, follow_redirects=True)

        bob = User.query.filter_by(username='student_bob').first()
        assert bob is not None

        # Admin logs in and rejects Bob
        client.post('/', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        reject_response = client.post(f'/admin/reject_student/{bob.id}', follow_redirects=True)
        assert reject_response.status_code == 200

        bob_check = User.query.filter_by(username='student_bob').first()
        assert bob_check is None, "Bob should be removed from database after rejection"
        print("[PASS] Rejection workflow removed unapproved student request cleanly!")

        # Clean up Alice test user so DB is pristine
        db.session.delete(alice)
        db.session.commit()
        print("\n=== ALL 6 TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_full_approval_workflow()
