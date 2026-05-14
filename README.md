# 🎓 AI-Powered Education & Assessment Platform

A full-stack web application built with **Flask** that enables teachers to create assessments, students to attempt them, and an AI engine (Google Gemini + YouTube API) to recommend personalized remediation videos based on weak topics. The platform features role-based access, gamification (XP, levels, badges), a leaderboard, and a built-in chatbot.

---

## ✨ Features

### 👨‍🏫 Teacher
- Create and manage **subjects & assessments**
- Add multiple-choice questions with topic tagging
- View **per-student results** and class-level analytics
- Assign subjects to specific class years and semesters

### 👨‍🎓 Student
- Attempt assessments (single-attempt, proctored with camera)
- Receive **AI-recommended YouTube videos** for weak topics
- Earn **XP, badges, and level up** through performance
- View personal dashboard with score history and weak topics
- Access a **built-in chatbot** for platform queries

### 🔐 Admin
- Manage all users (students, teachers)
- Full platform oversight

### 🤖 AI Engine
- **Google Gemini 1.5 Flash** generates optimized YouTube search queries from topic + question context
- **YouTube Data API v3** fetches the most relevant tutorial video
- Weak topic detection via per-topic accuracy thresholding

### 🏆 Gamification
| Badge | Score Threshold |
|-------|----------------|
| 🎓 Learner | ≥ 50% |
| 💪 Proficient | ≥ 75% |
| 🌟 Ace | ≥ 90% |
| 🏆 Perfectionist | ≥ 99% |

- XP = score points per attempt  
- Level = `XP / 500 + 1`  
- Global **Leaderboard** ranked by XP

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, Flask |
| ORM | Flask-SQLAlchemy |
| Auth | Flask-Login, Passlib (PBKDF2-SHA256) |
| Forms | Flask-WTF |
| Database | MySQL (production) / SQLite (dev) |
| AI | Google Gemini 1.5 Flash |
| Video | YouTube Data API v3 |
| Frontend | HTML5, CSS3, JavaScript, Chart.js |
| Config | python-dotenv |

---

## 📁 Project Structure

```
├── app/
│   ├── __init__.py          # App factory, DB & login manager setup
│   ├── config.py            # Flask configuration
│   ├── models.py            # SQLAlchemy models (User, Subject, Assessment, etc.)
│   ├── routes.py            # All route handlers (admin, teacher, student)
│   ├── utils.py             # Grading, AI video recommendation, gamification, chatbot
│   ├── forms.py             # WTForms definitions
│   ├── static/              # CSS, JS, images, sounds
│   └── templates/           # Jinja2 HTML templates
│       ├── base.html
│       ├── login.html
│       ├── leaderboard.html
│       ├── admin/
│       ├── teacher/
│       └── student/
├── run.py                   # App entry point
├── create_admin.py          # Script to seed first admin user
├── ai_edu.sql               # MySQL schema dump
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
└── .gitignore
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- MySQL (or use SQLite for quick local dev)
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)
- A [YouTube Data API v3 key](https://console.cloud.google.com/apis/library/youtube.googleapis.com)

### 1. Clone the Repository

```bash
git clone https://github.com/Athish-Raj-Tadakanahalli/ai-education-assessment.git
cd ai-education-assessment
```

### 2. Create & Activate a Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your actual values:

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=mysql+pymysql://user:password@localhost/ai_edu
GEMINI_API_KEY=your-gemini-api-key
YOUTUBE_API_KEY=your-youtube-api-key
```

### 5. Set Up the Database

**MySQL:**
```bash
mysql -u root -p < ai_edu.sql
```

**SQLite (quick start):**
```env
DATABASE_URL=sqlite:///ai_edu.db
```
The tables will be auto-created on first run.

### 6. Create an Admin User

```bash
python create_admin.py
```

### 7. Run the Application

```bash
python run.py
```

Visit → [http://localhost:5000](http://localhost:5000)

---

## 🔑 Default Roles & Login Flow

| Role | Capabilities |
|------|-------------|
| `admin` | Manage all users, full oversight |
| `teacher` | Create subjects, assessments, view results |
| `student` | Attempt assessments, view videos, earn XP |

Use `create_admin.py` to seed the first admin. Teachers and students are created by the admin through the dashboard.

---

## 📸 Screenshots

> _Coming soon — add screenshots of the dashboard, assessment page, and leaderboard here._

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first.

1. Fork the repo
2. Create your feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Athish Raj Tadakanahalli**  
[![GitHub](https://img.shields.io/badge/GitHub-Athish--Raj--Tadakanahalli-181717?style=flat&logo=github)](https://github.com/Athish-Raj-Tadakanahalli)  
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Athish%20Raj-0A66C2?style=flat&logo=linkedin)](https://www.linkedin.com/in/athish-raj-tadakanahalli-3a6052296/)
