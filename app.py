from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_session import Session
import sqlite3
from datetime import date, datetime
from flask import jsonify
# import requests

TOKEN = "8385224522:AAFKdjWPA9PeuVyZDcr9ElAS_fDu1HqcOqk"


app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# ================= DATABASE =================
def get_db():
    conn = sqlite3.connect("tasks.db")
    conn.row_factory = sqlite3.Row
    return conn


# ================= HOME =================
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect("/login")

    tasks = load_tasks("all")
    return render_template("index.html", tasks=tasks, active="inbox")

# ================= FILTER HELP =================
def load_tasks(filter_type):
    db = get_db()
    rows = db.execute("""
        SELECT *
        FROM tasks
        WHERE user_id = ?
        ORDER BY completed ASC, priority DESC, id DESC
    """, (session["user_id"],)).fetchall()

    today = date.today()
    tasks = []

    for row in rows:
        task = dict(row)

        if task["deadline"]:
            d = datetime.strptime(task["deadline"], "%Y-%m-%d").date()
            if d < today:
                task["status"] = "late"
            elif d == today:
                task["status"] = "today"
            else:
                task["status"] = "future"
        else:
            task["status"] = "none"

        # filtering
        if filter_type == "today" and task["status"] != "today":
            continue
        if filter_type == "upcoming" and task["status"] != "future":
            continue
        if filter_type == "late" and task["status"] != "late":
            continue

        tasks.append(task)

    return tasks

# ================= TODAY =================
@app.route("/today")
def today_view():
    if "user_id" not in session:
        return redirect("/login")

    tasks = load_tasks("today")
    return render_template("index.html", tasks=tasks, active="today")

# ================= UPCOMING =================
@app.route("/upcoming")
def upcoming_view():
    if "user_id" not in session:
        return redirect("/login")

    tasks = load_tasks("upcoming")
    return render_template("index.html", tasks=tasks, active="upcoming")

# ================= LATE =================
@app.route("/late")
def late_view():
    if "user_id" not in session:
        return redirect("/login")

    tasks = load_tasks("late")
    return render_template("index.html", tasks=tasks, active="late")

# ================= ADD =================
@app.route("/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect("/login")

    task = request.form.get("task")
    category = request.form.get("category") or "Personal"
    deadline = request.form.get("deadline") or None

    db = get_db()
    db.execute(
        "INSERT INTO tasks (user_id, task, category, deadline) VALUES (?, ?, ?, ?)",
        (session["user_id"], task, category, deadline)
    )
    db.commit()

    return redirect("/")


# ================= DELETE =================
@app.route("/delete/<int:id>")
def delete(id):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    db.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    )
    db.commit()
    return redirect("/")


# ================= PRIORITY =================
@app.route("/set_priority/<int:id>/<int:level>")
def set_priority(id, level):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    db.execute(
        "UPDATE tasks SET priority = ? WHERE id = ? AND user_id = ?",
        (level, id, session["user_id"])
    )
    db.commit()
    return redirect("/")


# ================= COMPLETE =================
@app.route("/complete/<int:id>")
def complete(id):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    db.execute(
        "UPDATE tasks SET completed = 1 WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    )
    db.commit()
    return redirect("/")


@app.route("/undo/<int:id>")
def undo(id):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    db.execute(
        "UPDATE tasks SET completed = 0 WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    )
    db.commit()
    return redirect("/")


# ================= DEADLINE EDIT =================
@app.route("/edit_deadline/<int:id>", methods=["GET", "POST"])
def edit_deadline(id):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()

    if request.method == "POST":
        deadline = request.form.get("deadline") or None
        db.execute(
            "UPDATE tasks SET deadline = ? WHERE id = ? AND user_id = ?",
            (deadline, id, session["user_id"])
        )
        db.commit()
        return redirect("/")

    task = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    ).fetchone()

    return render_template("edit_deadline.html", task=task)


# ================= AUTH =================
@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user and check_password_hash(user["hash"], password):
            session["user_id"] = user["id"]
            return redirect("/")

        return "invalid username or password"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return "Please provide username and password"

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            db.commit()
        except sqlite3.IntegrityError:
            return "Username already exists!"

        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        session["user_id"] = user["id"]
        return redirect("/")

    return render_template("register.html")

# ================= CATEGORY =================
@app.route("/category/<name>")
def category(name):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    rows = db.execute("""
        SELECT *
        FROM tasks
        WHERE user_id = ? AND category = ?
        ORDER BY completed ASC, priority DESC, id DESC
    """, (session["user_id"], name)).fetchall()

    from datetime import date, datetime
    today = date.today()

    tasks = []
    for row in rows:
        task = dict(row)

        if task["deadline"]:
            d = datetime.strptime(task["deadline"], "%Y-%m-%d").date()
            if d < today:
                task["status"] = "late"
            elif d == today:
                task["status"] = "today"
            else:
                task["status"] = "future"
        else:
            task["status"] = "none"

        tasks.append(task)

    return render_template(
        "index.html",
        tasks=tasks,
        active="category",
        current_category=name
    )

# ================= TELEGRAM =================
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    print("TELEGRAM HIT")
    data = request.get_json()

    message = data.get("message")
    if not message:
        return "ok"

    text = message.get("text")
    chat_id = message["chat"]["id"]

    user_id = 1

    db = get_db()
    db.execute(
        "INSERT INTO tasks (user_id, task, category) VALUES (?, ?, ?)",
        (user_id, text, "Telegram")
    )
    db.commit()

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": "✅ Task added!"
    })

    return "ok"



if __name__ == "__main__":
    app.run(debug=True)
