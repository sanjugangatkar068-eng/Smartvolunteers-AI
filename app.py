from flask import Flask, render_template, request, redirect, url_for, session, flash
import json
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "smartvolunteers_secret_key_2024"

# Use Render Disk for persistence
DATA_FILE = "/data/data.json" if os.path.exists("/data") else "data.json"

# ---------- Data Handling ----------
def load_data():
    try:
        if not os.path.exists(DATA_FILE):
            print(f"Creating new {DATA_FILE}")
            default_data = {"volunteers": [], "tasks": [], "matches": []}
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, "w") as f:
                json.dump(default_data, f, indent=2)
            return default_data
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"LOAD_DATA ERROR: {e}")
        return {"volunteers": [], "tasks": [], "matches": []}

def save_data(data):
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print("DATA SAVED SUCCESS")
    except Exception as e:
        print(f"SAVE_DATA ERROR: {e}")

# ---------- AI Matching Logic ----------
def calculate_match_score(volunteer, task):
    score = 0
    reasons = []
    v_skills = [s.lower().strip() for s in volunteer.get("skills", [])]
    t_skills = [s.lower().strip() for s in task.get("skills_required", [])]
    skill_matches = len(set(v_skills) & set(t_skills))
    if skill_matches > 0 and len(t_skills) > 0:
        score += 40 * (skill_matches / len(t_skills))
        reasons.append(f"{skill_matches} matching skills")
    if volunteer.get("location", "").lower().strip() == task.get("location", "").lower().strip():
        score += 30
        reasons.append("Same location")
    if volunteer.get("availability") == "flexible":
        score += 20
        reasons.append("Flexible schedule")
    if task.get("priority") == "High":
        score += 10
        reasons.append("High priority task")
    return min(round(score), 100), ", ".join(reasons)

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/admin")
def admin_login():
    session["user"] = "admin"
    session["role"] = "admin"
    session["name"] = "Admin"
    return redirect(url_for("dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        print(f"LOGIN ATTEMPT: email='{email}'")
        
        if password == "admin123" and email in ["admin", "admin@admin.com"]:
            print("ADMIN LOGIN SUCCESS")
            session["user"] = "admin"
            session["role"] = "admin" 
            session["name"] = "Admin"
            return redirect(url_for("dashboard"))
        
        data = load_data()
        for volunteer in data["volunteers"]:
            if volunteer["email"].lower() == email:
                if check_password_hash(volunteer.get("password_hash", ""), password):
                    session["user"] = volunteer["id"]
                    session["role"] = "volunteer"
                    session["name"] = volunteer["name"]
                    return redirect(url_for("dashboard"))
                break
        
        return render_template("login.html", error="Invalid email or password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/volunteer_signup", methods=["GET"])
def volunteer_signup_page():
    return render_template("volunteer_signup.html")

@app.route("/volunteer_signup", methods=["POST"])
def volunteer_signup():
    try:
        data = load_data()
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        
        print(f"SIGNUP ATTEMPT: name={name}, email={email}")
        
        if not email or not name or not password:
            return render_template("volunteer_signup.html", error="Name, email and password are required")
        
        for v in data["volunteers"]:
            if v["email"].lower() == email:
                print(f"SIGNUP FAILED: Email {email} already exists")
                return render_template("volunteer_signup.html", error="Email already registered")
        
        new_volunteer = {
            "id": f"v_{len(data['volunteers']) + 1}",
            "name": name,
            "email": email,
            "password_hash": generate_password_hash(password),
            "skills": [s.strip() for s in request.form.get("skills", "").split(",") if s.strip()],
            "location": request.form.get("location", "").strip(),
            "availability": request.form.get("availability", "").strip(),
            "languages": [l.strip() for l in request.form.get("languages", "").split(",") if l.strip()]
        }
        data["volunteers"].append(new_volunteer)
        save_data(data)
        print(f"SIGNUP SUCCESS: {email}")
        flash(f"Signup successful for {email}! Please login.")
        return redirect(url_for("login"))
    except Exception as e:
        print(f"SIGNUP ERROR: {str(e)}")
        return render_template("volunteer_signup.html", error=f"Signup failed: {str(e)}")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    data = load_data()
    if session.get("role") == "admin":
        stats = {"total_volunteers": len(data["volunteers"]), "total_tasks": len(data["tasks"]), "active_matches": len(data.get("matches", []))}
        return render_template("index.html", stats=stats, tasks=data["tasks"], matches=data.get("matches", []), user_role=session.get("role"), user_name=session.get("name"))
    else:
        volunteer_id = session["user"]
        my_matches = [m for m in data.get("matches", []) if m["volunteer_id"] == volunteer_id]
        stats = {"total_tasks": len(data["tasks"]), "my_matches": len(my_matches), "active_matches": len(my_matches)}
        return render_template("volunteer_dashboard.html", stats=stats, tasks=data["tasks"], matches=my_matches, user_role=session.get("role"), user_name=session.get("name"))

@app.route("/create_task", methods=["POST"])
def create_task():
    if "user" not in session or session.get("role")!= "admin":
        return redirect(url_for("login"))
    data = load_data()
    new_task = {"id": f"t_{len(data['tasks']) + 1}", "title": request.form.get("task_name", "").strip(), "description": request.form.get("task_name", "").strip(), "skills_required": [s.strip() for s in request.form.get("skills", "").split(",") if s.strip()], "location": request.form.get("location", "").strip(), "priority": request.form.get("priority", "").strip(), "volunteers_needed": int(request.form.get("volunteers_needed", 1)), "deadline": request.form.get("deadline", "").strip(), "status": "open"}
    data["tasks"].append(new_task)
    save_data(data)
    return redirect(url_for("dashboard"))

@app.route("/load_demo", methods=["POST"])
def load_demo():
    if "user" not in session or session.get("role")!= "admin":
        return redirect(url_for("login"))
    demo_data = {"volunteers": [{"id": "v_1", "name": "Priya Sharma", "email": "priya@example.com", "password_hash": generate_password_hash("pass123"), "skills": ["environment", "driving", "hindi"], "location": "Bengaluru", "availability": "flexible", "languages": ["English", "Hindi"]}, {"id": "v_2", "name": "Rahul Verma", "email": "rahul@example.com", "password_hash": generate_password_hash("pass123"), "skills": ["teaching", "english", "hindi"], "location": "Bengaluru", "availability": "weekends", "languages": ["English", "Hindi"]}, {"id": "v_3", "name": "Alex Kumar", "email": "alex@example.com", "password_hash": generate_password_hash("pass123"), "skills": ["logistics", "management", "english"], "location": "Bengaluru", "availability": "flexible", "languages": ["English"]}], "tasks": [{"id": "t_1", "title": "Beach Cleanup Drive", "description": "Clean up city beach", "skills_required": ["environment", "driving"], "location": "Bengaluru", "priority": "High", "volunteers_needed": 10, "deadline": "2025-12-31", "status": "open"}, {"id": "t_2", "title": "Food Drive Distribution", "description": "Distribute food packets", "skills_required": ["logistics", "management"], "location": "Bengaluru", "priority": "Medium", "volunteers_needed": 5, "deadline": "2025-12-25", "status": "open"}, {"id": "t_3", "title": "Teaching Assistant", "description": "Help teach kids", "skills_required": ["teaching", "hindi"], "location": "Bengaluru", "priority": "Medium", "volunteers_needed": 3, "deadline": "2025-12-20", "status": "open"}], "matches": []}
    save_data(demo_data)
    flash("Demo data loaded successfully!")
    return redirect(url_for("dashboard"))

@app.route("/run_match", methods=["POST"])
def run_match():
    if "user" not in session or session.get("role")!= "admin":
        return redirect(url_for("login"))
    data = load_data()
    matches = []
    for i, task in enumerate(data["tasks"]):
        if "id" not in task: task["id"] = f"t_{i+1}"
        if "title" not in task: task["title"] = task.get("task_name", "Untitled Task")
    for i, volunteer in enumerate(data["volunteers"]):
        if "id" not in volunteer: volunteer["id"] = f"v_{i+1}"
    for task in data["tasks"]:
        best_match = None
        best_score = 0
        best_reason = ""
        for volunteer in data["volunteers"]:
            score, reason = calculate_match_score(volunteer, task)
            if score > best_score:
                best_score = score
                best_match = volunteer
                best_reason = reason
        if best_match:
            matches.append({"task_id": task.get("id", "unknown"), "task_title": task.get("title", "Untitled Task"), "volunteer_id": best_match.get("id", "unknown"), "volunteer_name": best_match.get("name", "Unknown"), "match_score": best_score, "reason": best_reason})
    data["matches"] = matches
    save_data(data)
    flash(f"AI matching complete! Found {len(matches)} matches.")
    return redirect(url_for("dashboard"))

@app.route("/export_csv")
def export_csv():
    if "user" not in session:
        return redirect(url_for("login"))
    data = load_data()
    csv_data = "Task,Volunteer,Match Score,Reason\n"
    for match in data.get("matches", []):
        csv_data += f"{match['task_title']},{match['volunteer_name']},{match['match_score']}%,{match['reason']}\n"
    return csv_data, 200, {"Content-Type": "text/csv", "Content-Disposition": "attachment; filename=smartvolunteers_matches.csv"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
