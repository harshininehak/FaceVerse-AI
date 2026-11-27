
from flask import Flask, render_template, request, redirect, session
import sqlite3
import subprocess
import sys
import os
import shutil
from datetime import datetime
import json
import base64
import secrets
import hmac

import cv2
import numpy as np
from recognizer import recognize_face_from_image

app = Flask(__name__)

DATABASE = "database/facerecognition.db"
SESSION_FILE = "recognized_user.json"

# Session security
app.secret_key = os.environ.get(
    "FACEVERSE_SECRET_KEY",
    secrets.token_hex(32)
)

# Admin password loaded from environment variables
ADMIN_PASSWORD = os.environ.get("FACEVERSE_ADMIN_PASSWORD", "")

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024




# ---------------- DATABASE SETUP ----------------

def create_tables():

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            userid TEXT,
            email TEXT,
            phone TEXT,
            age INTEGER,
            gender TEXT
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userid TEXT,
            name TEXT,
            date TEXT,
            time TEXT,
            status TEXT
        )
    """)


    conn.commit()
    conn.close()



# ---------------- ATTENDANCE FUNCTION ----------------

def mark_attendance(userid, name):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()


    now = datetime.now()

    date = now.strftime("%d-%m-%Y")
    time = now.strftime("%H:%M:%S")


    cursor.execute(
        """
        SELECT * FROM attendance
        WHERE userid=? AND date=?
        """,
        (userid, date)
    )


    record = cursor.fetchone()


    if record is None:

        cursor.execute(
            """
            INSERT INTO attendance
            (userid, name, date, time, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                userid,
                name,
                date,
                time,
                "Present"
            )
        )

        print("Attendance Marked")


    else:

        print("Attendance Already Marked")


    conn.commit()
    conn.close()



# ---------------- ADMIN LOGIN & SECURITY ----------------

def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    csrf_token = get_csrf_token()
    error = None

    if request.method == 'POST':
        submitted_token = request.form.get("csrf_token", "")

        if not hmac.compare_digest(submitted_token, csrf_token):
            error = "Invalid request. Please try again."
        else:
            password = request.form.get("password", "")

            if not ADMIN_PASSWORD:
                error = "Admin password is not configured."

            elif hmac.compare_digest(password, ADMIN_PASSWORD):
                session.clear()
                session["admin_logged_in"] = True
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect("/admin")

            else:
                error = "Incorrect admin password."

    return render_template(
        "admin_login.html",
        csrf_token=csrf_token,
        error=error
    )


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    token = request.form.get("csrf_token", "")

    if (
        not session.get("admin_logged_in")
        or not hmac.compare_digest(token, get_csrf_token())
    ):
        return "Invalid logout request.", 400

    session.clear()
    return redirect("/admin/login")

# ---------------- HOME PAGE ----------------

@app.route('/')
def home():

    return render_template("index.html")



# ---------------- REGISTER ----------------


@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form.get('name')
        userid = request.form.get('userid')
        email = request.form.get('email')
        phone = request.form.get('phone')
        age = request.form.get('age')
        gender = request.form.get('gender')

        # Validate User ID
        if not userid or not userid.replace("_", "").replace("-", "").isalnum():
            return "Invalid User ID. Use letters, numbers, _ or -."

        # Receive captured browser images
        try:
            images = json.loads(request.form.get('face_images', '[]'))

            if len(images) != 30:
                return "Please capture all 30 face images."

        except (json.JSONDecodeError, TypeError):
            return "Invalid face image data."

        # Initialize face detector
        cascade_path = (
            cv2.data.haarcascades +
            "haarcascade_frontalface_default.xml"
        )

        face_detector = cv2.CascadeClassifier(cascade_path)

        if face_detector.empty():
            return "Face detector could not be loaded."

        folder = os.path.join("dataset", userid)

        # Prepare face images before updating the database
        processed_faces = []

        for image_data in images:

            try:
                image_bytes = base64.b64decode(
                    image_data.split(",", 1)[1],
                    validate=True
                )

                image_array = np.frombuffer(
                    image_bytes,
                    dtype=np.uint8
                )

                frame = cv2.imdecode(
                    image_array,
                    cv2.IMREAD_COLOR
                )

                if frame is None:
                    return "Could not read a captured image."

                gray = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2GRAY
                )

                faces = face_detector.detectMultiScale(
                    gray, 1.3, 5
                )

                if len(faces) == 0:
                    return "Face not detected in all images. Please try again."

                # Select the largest detected face
                x, y, w, h = max(
                    faces,
                    key=lambda face: face[2] * face[3]
                )

                face = gray[y:y+h, x:x+w]
                face = cv2.resize(face, (200, 200))

                processed_faces.append(face)

            except (ValueError, IndexError):
                return "Invalid captured image."

        # Save the 30 processed face images
        os.makedirs(folder, exist_ok=True)

        # Clear previous samples for this user
        for old_file in os.listdir(folder):
            old_path = os.path.join(folder, old_file)

            if os.path.isfile(old_path):
                os.remove(old_path)

        for index, face in enumerate(processed_faces, start=1):

            image_path = os.path.join(
                folder,
                f"{index}.jpg"
            )

            cv2.imwrite(image_path, face)

        # Save user details in SQLite
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE userid=?",
            (userid,)
        )

        existing = cursor.fetchone()

        if existing:

            cursor.execute("""
                UPDATE users
                SET name=?, email=?, phone=?, age=?, gender=?
                WHERE userid=?
            """, (
                name, email, phone, age, gender, userid
            ))

        else:

            cursor.execute("""
                INSERT INTO users
                (name, userid, email, phone, age, gender)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                name, userid, email, phone, age, gender
            ))

        conn.commit()
        conn.close()

        # Retrain face recognition model
        result = subprocess.run(
            [sys.executable, "train_model.py"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return "Face model training failed. Check the PyCharm terminal."

        return render_template("success.html")

    return render_template("register.html")



# ---------------- ADMIN PANEL ----------------

@app.route('/admin')
def admin():

    if not session.get("admin_logged_in"):
        return redirect("/admin/login")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    total = len(users)

    cursor.execute(
        "SELECT * FROM attendance ORDER BY id DESC"
    )
    attendance = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        users=users,
        total=total,
        attendance=attendance,
        csrf_token=get_csrf_token()
    )


# ---------------- DELETE USER ----------------

@app.route('/delete/<userid>', methods=['POST'])
def delete(userid):

    if not session.get("admin_logged_in"):
        return redirect("/admin/login")

    submitted_token = request.form.get("csrf_token", "")

    if not hmac.compare_digest(
        submitted_token,
        get_csrf_token()
    ):
        return "Invalid request. Please refresh and try again.", 400

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM attendance WHERE userid=?",
        (userid,)
    )

    cursor.execute(
        "DELETE FROM users WHERE userid=?",
        (userid,)
    )

    conn.commit()
    conn.close()

    folder = os.path.join("dataset", userid)

    if os.path.exists(folder):
        shutil.rmtree(folder)

    result = subprocess.run(
        [sys.executable, "train_model.py"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("Model training error:", result.stderr)
        return "User deleted, but model retraining failed. Check the server logs.", 500

    return redirect("/admin")




# ---------------- LOGIN + FACE RECOGNITION ----------------




@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'GET':
        return render_template("login.html")

    face_image = request.form.get('face_image')

    if not face_image:
        return render_template("error.html")

    result = recognize_face_from_image(face_image)

    if not result["success"]:
        return render_template("error.html")

    userid = result["userid"]

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, userid, email, phone, age, gender
        FROM users
        WHERE userid=?
    """, (userid,))

    user = cursor.fetchone()
    conn.close()

    if user is None:
        return render_template("error.html")

    return render_template(
        "dashboard.html",
        name=user[0],
        userid=user[1],
        email=user[2],
        phone=user[3],
        age=user[4],
        gender=user[5]
    )



# ---------------- ATTENDANCE PAGE ----------------


# ---------------- ATTENDANCE PAGE ----------------

@app.route('/attendance')
def attendance():

    if not session.get("admin_logged_in"):
        return redirect("/admin/login")

    search = request.args.get("search", "")
    date = request.args.get("date", "")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    query = """
        SELECT *
        FROM attendance
        WHERE 1=1
    """

    values = []

    if search:
        query += " AND (name LIKE ? OR userid LIKE ?)"
        values.append(f"%{search}%")
        values.append(f"%{search}%")

    if date:
        query += " AND date=?"
        values.append(date)

    query += " ORDER BY id DESC"

    cursor.execute(query, values)
    records = cursor.fetchall()

    conn.close()

    return render_template(
        "attendance.html",
        records=records,
        search=search,
        date=date
    )


# ---------------- START APP ----------------

if __name__ == '__main__':
    create_tables()
    app.run(debug=True)
