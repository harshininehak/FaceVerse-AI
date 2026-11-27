
import cv2
import os
import sqlite3
import numpy as np
import base64
from datetime import datetime


DATABASE = "database/facerecognition.db"
MODEL_PATH = "trainer/trainer.yml"

CASCADE_PATH = (
    cv2.data.haarcascades +
    "haarcascade_frontalface_default.xml"
)


def mark_attendance(userid, name):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    today = datetime.now().strftime("%d-%m-%Y")
    current_time = datetime.now().strftime("%H:%M:%S")

    cursor.execute(
        "SELECT id FROM attendance WHERE userid=? AND date=?",
        (userid, today)
    )

    if cursor.fetchone() is None:

        cursor.execute("""
            INSERT INTO attendance
            (userid, name, date, time, status)
            VALUES (?, ?, ?, ?, ?)
        """, (userid, name, today, current_time, "Present"))

        print("Attendance marked successfully")

    else:
        print("Attendance already marked today")

    conn.commit()
    conn.close()


def recognize_face_from_image(image_data):

    # Check trained model
    if not os.path.exists(MODEL_PATH):
        return {
            "success": False,
            "message": "Trained model not found."
        }

    # Load LBPH model
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(MODEL_PATH)

    # Load face detector
    face_detector = cv2.CascadeClassifier(CASCADE_PATH)

    if face_detector.empty():
        return {
            "success": False,
            "message": "Face detector could not be loaded."
        }

    # Decode browser image
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
            raise ValueError("Invalid image")

    except (ValueError, IndexError, TypeError):
        return {
            "success": False,
            "message": "Invalid image received."
        }

    # Convert image to grayscale
    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    # Detect faces
    faces = face_detector.detectMultiScale(
        gray,
        scaleFactor=1.3,
        minNeighbors=5
    )

    if len(faces) == 0:
        return {
            "success": False,
            "message": "No face detected. Please try again."
        }

    # Select largest detected face
    x, y, w, h = max(
        faces,
        key=lambda face: face[2] * face[3]
    )

    face = gray[y:y+h, x:x+w]
    face = cv2.resize(face, (200, 200))

    # Load registered users
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("SELECT userid, name FROM users")

    users = {
        userid: name
        for userid, name in cursor.fetchall()
    }

    conn.close()

    # Rebuild training label mapping
    if not os.path.exists("dataset"):
        return {
            "success": False,
            "message": "Face dataset not found."
        }

    user_ids = sorted(
        folder
        for folder in os.listdir("dataset")
        if os.path.isdir(os.path.join("dataset", folder))
    )

    label_to_userid = {
        label: userid
        for label, userid in enumerate(user_ids)
    }

    # Predict face
    label, confidence = recognizer.predict(face)

    userid = label_to_userid.get(label)

    # Verify recognition
    if userid not in users or confidence >= 65:

        return {
            "success": False,
            "message": "Face not recognised."
        }

    name = users[userid]

    # Record attendance
    mark_attendance(userid, name)

    return {
        "success": True,
        "userid": userid,
        "name": name,
        "confidence": round(float(confidence), 2)
    }
