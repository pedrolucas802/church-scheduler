@Tech_maraponga_2026

# 📺 Church Streaming Scheduler

A bilingual (**Português / English**) scheduling system for church streaming ministries, built with **Streamlit** and **PostgreSQL**, focused on automation and fair volunteer rotation.

Designed to start as a **local MVP** and evolve into a **VPS-hosted production system**.

## ✨ Features
### Current MVP
- 👥 Volunteer management
- 📅 Automatic schedule generation (Thursdays & Sundays)
- 🔄 Fair role rotation
- 🗓️ Monthly calendar view
- ✏️ Manual editing
- 🔁 Swap requests
- ⏰ Reminder queue (24h before)
- 🌎 Bilingual UI
- 🐘 PostgreSQL (Docker)

## 🚀 Quick start
```bash
docker compose up -d
pip install -r requirements.txt
streamlit run app.py
```

## 🙏 Purpose
Serve church teams and replace spreadsheets with a reliable system.


### Planned / Next Steps
- 📲 WhatsApp reminders & confirmations
- 🔐 Volunteer login (role-based access)
- 📈 Usage & participation metrics
- 🛠️ Alembic migrations
- 🚀 VPS deployment (Hostinger)

---

## 🧱 Tech Stack

| Layer | Technology |
|------|------------|
| UI | Streamlit |
| Language | Python 3.11+ |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Containers | Docker / Docker Compose |
| i18n | Custom dictionary-based system |
| Hosting (planned) | Hostinger VPS + Nginx |

## 📁 Project Structure
    church-scheduler/
    │
    ├── app.py
    ├── requirements.txt
    ├── docker-compose.yml
    ├── .env
    │
    ├── pages/
    │   ├── 1_👥_Volunteers.py
    │   ├── 2_📅_Schedule.py
    │   ├── 3_⚙️_Generate.py
    │   ├── 4_✏️_Edit.py
    │   ├── 5_🔁_Swap_Requests.py
    │   └── 6_⏰_Reminders.py
    │
    ├── src/
    │   ├── auth.py
    │   ├── db.py
    │   ├── scheduler.py
    │   └── i18n.py
    │
    └── data/
    └── (local artifacts / legacy sqlite if needed)

## 🚀 Getting Started (Local Development)

### 1️⃣ Prerequisites
- Python **3.11+**
- Docker & Docker Compose
- Git

---

### 2️⃣ Clone the repository
```bash
git clone <your-repo-url>
cd church-scheduler