import tensorflow as tf
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.vgg16 import VGG16, preprocess_input
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow import keras
from nudenet import NudeDetector
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
from inference_sdk import InferenceHTTPClient
from django.conf import settings
import os
import cv2
from mtcnn import MTCNN
import tempfile


CLIENT = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key="PaB4RkzKGvF67QNkUPMa"
)

CLIENT = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key="PaB4RkzKGvF67QNkUPMa"
)



pothole_model_path = os.path.join(settings.BASE_DIR, 'base', 'models', 'pothole_gap.h5')
pothole_classifier_model = load_model(pothole_model_path)
pothole_feature_extractor = VGG16(weights='imagenet', include_top=False, input_shape=(224, 224, 3))

fallen_tree_path = os.path.join(settings.BASE_DIR, 'base', 'models', 'fallen_trees.h5')
fallen_tree_model = load_model(fallen_tree_path)

garbage_model_path = os.path.join(settings.BASE_DIR, 'base', 'models', 'garbage_classifier.h5')
garbage_classifier_model = load_model(garbage_model_path)


def sensitive_content(image_path):
    detector = NudeDetector()
    detection_results = detector.detect(image_path)
    for result in detection_results:
        if "EXPOSED" in result['class']:
            return "Sensitive"
    return "Not Sensitive"  


def detect_hoarding(image_path, model_id="billboards-detection/2", confidence_threshold=0.6):
    result = CLIENT.infer(image_path, model_id=model_id)
    for prediction in result.get('predictions', []):
        if prediction.get('confidence', 0) >= confidence_threshold:
            return "Hoarding Detected"
    
    return "No Hoarding Detected"


def predict_pothole(img_path, img_width=224, img_height = 224):
    img = image.load_img(img_path, target_size=(img_width, img_height))
    img_tensor = image.img_to_array(img)
    img_tensor = np.expand_dims(img_tensor, axis=0)
    img_tensor = preprocess_input(img_tensor)  
    features = pothole_feature_extractor.predict(img_tensor)
    prediction = pothole_classifier_model.predict(features)
    return prediction[0][0] >= 0.5 


def predict_garbage(image_path):
    image = cv2.imread(image_path)
    image = cv2.resize(image, (224, 224)) 
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)  
    image = image / 255.0 
    image = np.expand_dims(image, axis=0)  
    prediction = garbage_classifier_model.predict(image)
    classes = {0: 'clean', 1: 'dirty'}
    predicted_label = np.argmax(prediction)  
    predicted_class = classes[predicted_label]
    return predicted_class


def predict_fallen_tree(image_path):
    image = cv2.imread(image_path)
    image = cv2.resize(image, (150, 150))  
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)  
    image = image / 255.0  
    image = np.expand_dims(image, axis=0)  
    prediction = fallen_tree_model.predict(image)
    predicted_label = 1 if prediction[0][0] >= 0.5 else 0
    classes = {0: 'clear_road', 1: 'fallen_tree'}
    predicted_class = classes[predicted_label]
    return predicted_class


def detect_stagnant_water(image_path, model_id="stagnant-water-7ayix-hftcm/1"):
    with open(image_path, "rb") as image_file:
        result = CLIENT.infer(image_file, model_id=model_id)
    if result.get('predictions'):
        return "Stagnant Water detected"
    else:
        return "No Stagnant Water detected"


def detect_and_blur_faces(image_path):
    detector = MTCNN()
    image = cv2.imread(image_path)
    if image is None:
        with Image.open(image_path) as pil_image:
            if pil_image.mode == "RGBA":
                pil_image = pil_image.convert("RGB")
            temp_image_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
            pil_image.save(temp_image_path, format="PNG")
            image = cv2.imread(temp_image_path)

    max_dimension = 800
    height, width, _ = image.shape
    if height > width:
        new_height = max_dimension
        new_width = int((max_dimension / height) * width)
    else:
        new_width = max_dimension
        new_height = int((max_dimension / width) * height)

    image = cv2.resize(image, (new_width, new_height))

    faces = detector.detect_faces(image)

    for face in faces:
        x, y, w, h = face['box']
        # ensuring the box is within bounds
        x, y = max(0, x), max(0, y)
        w, h = max(0, w), max(0, h)

        # extracting and blur the face region
        face_region = image[y:y+h, x:x+w]
        blurred_face = cv2.GaussianBlur(face_region, (99, 99), 30)
        image[y:y+h, x:x+w] = blurred_face

    # saving the modified image to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        cv2.imwrite(temp_file.name, image)
        return temp_file.name
