import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Add the project directory to sys.path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_dir)

from app.utils import update_streak

class MockUser:
    def __init__(self, username, points=0, xp=0, level=1, badges="[]", streak=0, last_active=None):
        self.username = username
        self.points = points
        self.xp = xp
        self.level = level
        self.badges = badges
        self.streak = streak
        self.last_active = last_active

def run_tests():
    print("Starting streak unit tests...")
    
    db_session = MagicMock()
    
    # Test 1: First time active
    print("Test 1: First time active...")
    u1 = MockUser("student1")
    updated, bonus, badges = update_streak(u1, db_session)
    assert updated is True
    assert u1.streak == 1
    assert u1.last_active is not None
    assert bonus == 0
    assert badges == []
    print("Test 1 Passed!")
    
    # Test 2: Active twice on the same day
    print("Test 2: Same day activity...")
    u2 = MockUser("student2", streak=2, last_active=datetime.utcnow())
    updated, bonus, badges = update_streak(u2, db_session)
    assert updated is False
    assert u2.streak == 2
    assert bonus == 0
    assert badges == []
    print("Test 2 Passed!")
    
    # Test 3: Consecutive day activity (streak incremented)
    print("Test 3: Consecutive day activity...")
    yesterday = datetime.utcnow() - timedelta(days=1)
    u3 = MockUser("student3", streak=2, last_active=yesterday, xp=100, points=100)
    updated, bonus, badges = update_streak(u3, db_session)
    assert updated is True
    assert u3.streak == 3
    assert bonus == 50  # 3-day streak milestone reward
    assert u3.xp == 150
    assert u3.points == 150
    print("Test 3 Passed!")
    
    # Test 4: Broken streak resets to 1
    print("Test 4: Broken streak...")
    two_days_ago = datetime.utcnow() - timedelta(days=2)
    u4 = MockUser("student4", streak=5, last_active=two_days_ago)
    updated, bonus, badges = update_streak(u4, db_session)
    assert updated is True
    assert u4.streak == 1
    assert bonus == 0
    print("Test 4 Passed!")

    # Test 5: 7-day streak milestone reward (badge + XP)
    print("Test 5: 7-day streak milestone...")
    u5 = MockUser("student5", streak=6, last_active=yesterday, xp=200, points=200, badges="[]")
    updated, bonus, badges_awarded = update_streak(u5, db_session)
    assert updated is True
    assert u5.streak == 7
    assert bonus == 150
    assert "7-Day Streak" in badges_awarded
    import json
    user_badges = json.loads(u5.badges)
    assert "7-Day Streak" in user_badges
    print("Test 5 Passed!")

    print("\nAll streak unit tests completed successfully!")

if __name__ == "__main__":
    run_tests()
