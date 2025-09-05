# FDP_Timetable-Optimization
# Timetable Optimization

A web application that helps students organize their schedules automatically by optimizing tasks, deadlines, and weekly commitments.  
The system dynamically rearranges timetables whenever new tasks are added, reducing the mental load of manual planning.

---

## 📌 Features
- **Automatic scheduling** using a Backtracking Algorithm.
- **Three types of tasks**:
  - `TASK`: flexible tasks with deadlines and estimated hours.
  - `WEEKLY`: recurring weekly activities (e.g., classes).
  - `MEETING`: fixed events with a specific time.
- **Dynamic calendar** that updates whenever new tasks are created.
- **Canvas LMS integration**: import assignments automatically using the Canvas API.
- **Responsive web interface**: accessible from desktop and mobile.
- **User validation and authentication** with Django.

---

## 🛠️ Technologies
- **Backend**: [Django](https://www.djangoproject.com/) (Python)
- **Algorithm**: Backtracking for task scheduling
- **Database**: PostgreSQL
- **Frontend**: HTML, CSS, JavaScript, Bootstrap
- **External APIs**: Canvas LMS API

---
## 🚀 Installation & Setup

### 1\. Clone the repository

```bash
git clone https://github.com/<your-username>/timetable-optimization.git
cd timetable-optimization
```

### 2\. Create a virtual environment

```bash
python -m venv venv
```

### 3\. Activate the environment (Linux/Mac)

```bash
source venv/bin/activate
```

### 4\. Activate the environment (Windows PowerShell)

```bash
venv\Scripts\activate
```

### 5\. Install dependencies

```bash
pip install -r requirements.txt
```

### 6\. Configure the database

Edit `settings.py` with your PostgreSQL credentials:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'timetable_db',
        'USER': 'postgres',
        'PASSWORD': 'yourpassword',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 7\. Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 8\. Create a superuser

```bash
python manage.py createsuperuser
```

### 9\. Run the server

```bash
python manage.py runserver
```

Now open the app at 👉 [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

-----

### 📂 Project Structure

```
timetable-optimization/
│── timetable/       # Main Django app
│── templates/       # HTML templates
│── static/          # CSS / JS / Images
│── manage.py
│── requirements.txt
│── README.md
```

-----

## 📈 Future Work

  * Advanced group synchronization.
  * Daily auto-sync with Canvas.
  * Deployment on cloud services (Azure, AWS, or Heroku).
  * Extended analytics and workload prediction.

-----

## 👨‍💻 Author

Christopher Cobo Piekenbrock

**Tutor:** Jorge García Fernández – Universidad Francisco de Vitoria
