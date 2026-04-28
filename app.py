import json
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = "smartvolunteers_secret_key_2024"

# Render Free Tier - saves in project folder. Data resets on deploy/sleep.
DATA_FILE = "data.json"

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"LOAD_DATA ERROR: {e}")
        return {
            "users": {
                "admin@admin.com": {
                    "password": generate_password_hash("admin123"),
                    "role": "admin",
                    "name": "Admin"
                }
            },
            "volunteers": [],
            "tasks": [],
            "matches": []
        }

def save_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print("DATA SAVED SUCCESS")
    except Exception as e:
        print(f"SAVE_DATA ERROR: {e}")

def ai_match_volunteers():
    data = load_data()
    volunteers = data["volunteers"]
    tasks = data["tasks"]
    matches = []

    for task in tasks:
        task_skills = set(skill.lower().strip() for skill in task["skills_required"])

        for volunteer in volunteers:
            vol_skills = set(skill.lower().strip() for skill in volunteer["skills"])

            # Calculate match score
            skill_match = len(task_skills & vol_skills) / len(task_skills) if task_skills else 0
            location_match = 1.0 if volunteer["location"].lower() == task["location"].lower() else 0.3
            availability_match = 1.0 if volunteer["availability"] == "Flexible" else 0.7
            priority_bonus = 0.2 if task["priority"] == "High" else 0.1

            total_score = (skill_match * 0.5 + location_match * 0.3 + availability_match * 0.1 + priority_bonus) * 100

            if total_score > 30: # Only match if >30%
                reasons = []
                if skill_match > 0:
                    reasons.append(f"{len(task_skills & vol_skills)} matching skills")
                if location_match == 1.0:
                    reasons.append("Same location")
                if volunteer["availability"] == "Flexible":
                    reasons.append("Flexible schedule")

                matches.append({
                    "id": len(matches) + 1,
                    "task_id": task["id"],
                    "volunteer_id": volunteer["id"],
                    "task_name": task["task_name"],
                    "volunteer_name": volunteer["name"],
                    "volunteer_email": volunteer["email"],
                    "match_score": round(total_score, 1),
                    "reasons": ", ".join(reasons) if reasons else "Partial match",
                    "status": "Pending",
                    "created_at": datetime.now().isoformat()
                })

    data["matches"] = sorted(matches, key=lambda x: x["match_score"], reverse=True)
    save_data(data)
    return len(matches)

@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
    if session['user']['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('volunteer_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        data = load_data()

        if email in data["users"] and check_password_hash(data["users"][email]["password"], password):
            session['user'] = {
                "email": email,
                "role": data["users"][email]["role"],
                "name": data["users"][email]["name"]
            }
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'error')

    return render_template('login.html')

@app.route('/volunteer_signup', methods=['GET', 'POST'])
def volunteer_signup():
    if request.method == 'POST':
        data = load_data()
        email = request.form['email']

        if email in data["users"]:
            flash('Email already registered', 'error')
            return render_template('volunteer_signup.html')

        # Create user account
        data["users"][email] = {
            "password": generate_password_hash(request.form['password']),
            "role": "volunteer",
            "name": request.form['name']
        }

        # Create volunteer profile
        volunteer = {
            "id": len(data["volunteers"]) + 1,
            "name": request.form['name'],
            "email": email,
            "skills": [s.strip() for s in request.form['skills'].split(',')],
            "location": request.form['location'],
            "availability": request.form['availability']
        }
        data["volunteers"].append(volunteer)
        save_data(data)

        # Auto login
        session['user'] = {"email": email, "role": "volunteer", "name": request.form['name']}
        flash('Signup successful! Welcome to SmartVolunteers', 'success')
        return redirect(url_for('volunteer_dashboard'))

    return render_template('volunteer_signup.html')

@app.route('/admin')
def admin_dashboard():
    if 'user' not in session or session['user']['role']!= 'admin':
        return redirect(url_for('login'))

    data = load_data()
    stats = {
        "total_volunteers": len(data["volunteers"]),
        "total_tasks": len(data["tasks"]),
        "active_matches": len([m for m in data["matches"] if m["status"] == "Pending"]),
        "total_matches": len(data["matches"])
    }
    return render_template('index.html', stats=stats, tasks=data["tasks"], matches=data["matches"], user=session['user'])

@app.route('/volunteer_dashboard')
def volunteer_dashboard():
    if 'user' not in session or session['user']['role']!= 'volunteer':
        return redirect(url_for('login'))

    data = load_data()
    user_email = session['user']['email']

    # Get volunteer's matches
    my_matches = [m for m in data["matches"] if m["volunteer_email"] == user_email]
    # Get all open tasks
    open_tasks = [t for t in data["tasks"] if t["volunteers_needed"] > 0]

    return render_template('volunteer_dashboard.html',
                         matches=my_matches,
                         tasks=open_tasks,
                         user=session['user'])

@app.route('/create_task', methods=['POST'])
def create_task():
    if 'user' not in session or session['user']['role']!= 'admin':
        return redirect(url_for('login'))

    data = load_data()
    task = {
        "id": len(data["tasks"]) + 1,
        "task_name": request.form['task_name'],
        "skills_required": [s.strip() for s in request.form['skills_required'].split(',')],
        "location": request.form['location'],
        "priority": request.form['priority'],
        "volunteers_needed": int(request.form['volunteers_needed']),
        "deadline": request.form['deadline'],
        "created_at": datetime.now().isoformat()
    }
    data["tasks"].append(task)
    save_data(data)
    flash('Task created successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/run_ai_match')
def run_ai_match():
    if 'user' not in session or session['user']['role']!= 'admin':
        return redirect(url_for('login'))

    count = ai_match_volunteers()
    flash(f'AI matching complete! Found {count} matches.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/load_demo')
def load_demo():
    if 'user' not in session or session['user']['role']!= 'admin':
        return redirect(url_for('login'))

    data = load_data()

    # Demo volunteers
    demo_volunteers = [
        {"name": "Priya Sharma", "email": "priya@example.com", "skills": ["teaching", "communication", "hindi"], "location": "Bengaluru", "availability": "Flexible"},
        {"name": "Rahul Kumar", "email": "rahul@example.com", "skills": ["coding", "python", "web development"], "location": "Bengaluru", "availability": "Weekends"},
        {"name": "Anjali Patel", "email": "anjali@example.com", "skills": ["design", "photoshop", "social media"], "location": "Mumbai", "availability": "Flexible"}
    ]

    # Demo tasks
    demo_tasks = [
        {"task_name": "Teach English to Kids", "skills_required": ["teaching", "communication"], "location": "Bengaluru", "priority": "High", "volunteers_needed": 2, "deadline": (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')},
        {"task_name": "Build NGO Website", "skills_required": ["coding", "web development"], "location": "Bengaluru", "priority": "Medium", "volunteers_needed": 1, "deadline": (datetime.now() + timedelta(days=45)).strftime('%Y-%m-%d')},
        {"task_name": "Social Media Campaign", "skills_required": ["design", "social media"], "location": "Mumbai", "priority": "High", "volunteers_needed": 1, "deadline": (datetime.now() + timedelta(days=20)).strftime('%Y-%m-%d')}
    ]

    # Add demo data if not exists
    for vol in demo_volunteers:
        if not any(v["email"] == vol["email"] for v in data["volunteers"]):
            vol["id"] = len(data["volunteers"]) + 1
            data["volunteers"].append(vol)
            data["users"][vol["email"]] = {
                "password": generate_password_hash("demo123"),
                "role": "volunteer",
                "name": vol["name"]
            }

    for task in demo_tasks:
        if not any(t["task_name"] == task["task_name"] for t in data["tasks"]): # Fixed this line
            task["id"] = len(data["tasks"]) + 1
            task["created_at"] = datetime.now().isoformat()
            data["tasks"].append(task)

    save_data(data)
    flash('Demo data loaded! 3 volunteers + 3 tasks added.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/export_matches')
def export_matches():
    if 'user' not in session or session['user']['role']!= 'admin':
        return redirect(url_for('login'))

    data = load_data()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Task', 'Volunteer', 'Email', 'Match Score', 'Reasons', 'Status'])

    for match in data["matches"]:
        writer.writerow([
            match["task_name"],
            match["volunteer_name"],
            match["volunteer_email"],
            f"{match['match_score']}%",
            match["reasons"],
            match["status"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=matches.csv"}
    )

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
