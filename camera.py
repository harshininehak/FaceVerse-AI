import cv2
import os

def capture_faces(userid):

    folder = f"dataset/{userid}"

    if not os.path.exists(folder):
        os.makedirs(folder)

    cap = cv2.VideoCapture(0)

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

    print(cascade_path)

    face_detector = cv2.CascadeClassifier(cascade_path)

    print(face_detector.empty())

    count = 0

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = face_detector.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:

            count += 1

            face = gray[y:y+h, x:x+w]

            face = cv2.resize(face, (200, 200))

            cv2.imwrite(f"{folder}/{count}.jpg", face)

            cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 2)

            cv2.putText(frame,
                        f"Image {count}/30",
                        (20,40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0,255,0),
                        2)

        cv2.imshow("Capturing Face", frame)

        if cv2.waitKey(1) == 13 or count >= 30:
            break

    cap.release()
    cv2.destroyAllWindows()