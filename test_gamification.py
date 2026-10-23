import os
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User
from app.utils import update_streak, award_xp_and_badges

def test_gamification():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    client = app.test_client()

    with app.app_context():
        print("=== Test 1: User Title and Avatar Border Properties ===")
        user = User(
            username="gamer_student",
            password_hash=User.hash_password("password123"),
            role="student",
            full_name="Gamer Student",
            level=1,
            xp=0,
            streak=1,
            streak_freeze=1,
            is_approved=True
        )
        db.session.add(user)
        db.session.commit()

        assert user.title == "Apprentice Engineer", f"Expected Apprentice Engineer, got {user.title}"
        assert "border-slate-300" in user.avatar_border_class

        user.level = 5
        assert user.title == "Code Artisan", f"Expected Code Artisan, got {user.title}"
        assert "border-cyan-400" in user.avatar_border_class

        user.level = 9
        assert user.title == "Algorithm Master", f"Expected Algorithm Master, got {user.title}"
        assert "border-amber-400" in user.avatar_border_class

        user.level = 14
        assert user.title == "Cyber Grandmaster", f"Expected Cyber Grandmaster, got {user.title}"
        assert "border-purple-500" in user.avatar_border_class
        print("[PASS] Titles and Avatar Border Classes evaluated correctly across all tiers!")

        print("\n=== Test 2: Streak Freeze Protection on Missed Days ===")
        user.streak = 5
        user.streak_freeze = 1
        # Simulate last active 2 days ago (missed yesterday)
        user.last_active = datetime.utcnow() - timedelta(days=2)
        db.session.commit()

        updated, bonus_xp, badges, freeze_used = update_streak(user, db.session)
        assert freeze_used is True, "Streak freeze should have been used"
        assert user.streak == 6, f"Streak should have been preserved and incremented to 6, got {user.streak}"
        assert user.streak_freeze == 0, f"Streak freeze count should now be 0, got {user.streak_freeze}"
        print("[PASS] Streak Freeze successfully protected user's streak when missing a day!")

        print("\n=== Test 3: Streak Reset When No Freeze Available ===")
        # Missed another day, no freeze left
        user.last_active = datetime.utcnow() - timedelta(days=2)
        db.session.commit()

        updated, bonus_xp, badges, freeze_used = update_streak(user, db.session)
        assert freeze_used is False, "No streak freeze should have been used"
        assert user.streak == 1, f"Streak should reset to 1, got {user.streak}"
        print("[PASS] Streak correctly resets to 1 when no freezes are left!")

        print("\n=== Test 4: Level-Up Detection and Reward ===")
        user.xp = 450
        user.level = 1
        user.streak_freeze = 0
        db.session.commit()

        # Score 90 -> gains 90 XP -> total 540 XP -> triggers level 2!
        xp_gain, new_badges, leveled_up, old_lvl, new_lvl = award_xp_and_badges(user, 90, db.session)
        assert leveled_up is True, "User should have leveled up"
        assert new_lvl == 2, f"Expected level 2, got {new_lvl}"
        assert user.streak_freeze == 1, "Level-up should have awarded a bonus streak freeze"
        print("[PASS] Level-up detected successfully and awarded +1 Streak Freeze shield!")

        print("\n=== Test 5: Student Dashboard UI Rendering ===")
        # Log in as the test student
        client.post('/', data={'username': 'gamer_student', 'password': 'password123'}, follow_redirects=True)
        dash = client.get('/student')
        assert dash.status_code == 200
        assert b"Days Streak" in dash.data
        assert b"Freeze Active" in dash.data
        assert b"Apprentice Engineer" in dash.data or b"Code Artisan" in dash.data
        print("[PASS] Student dashboard renders streak flame, freeze shield, and title correctly!")

        # Cleanup test user
        db.session.delete(user)
        db.session.commit()
        print("\n=== ALL GAMIFICATION TESTS PASSED! ===")

if __name__ == "__main__":
    test_gamification()
