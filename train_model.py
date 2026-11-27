import cv2
import os
import numpy as np

recognizer = cv2.face.LBPHFaceRecognizer_create()

dataset_path = "dataset"

faces = []
labels = []

label_map = {}
current_label = 0

for user in sorted(os.listdir(dataset_path)):

    user_folder = os.path.join(dataset_path, user)

    if not os.path.isdir(user_folder):
        continue

    label_map[current_label] = user

    for image in os.listdir(user_folder):

        image_path = os.path.join(user_folder, image)

        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

        if img is None:
            continue

        faces.append(img)
        labels.append(current_label)

    current_label += 1

recognizer.train(faces, np.array(labels))

if not os.path.exists("trainer"):
    os.makedirs("trainer")

recognizer.save("trainer/trainer.yml")

print("Model Trained Successfully!")