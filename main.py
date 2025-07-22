import sys
import os
import json
import threading
import asyncio
import time
import traceback
import cv2
import numpy as np
from typing import Self
from dotenv import dotenv_values
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox,QFrame,QHBoxLayout,QLineEdit
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QImage, QPixmap,  QIcon

# Local imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from Fronted.GUI import FridayUI
from Backend.Model import firstlayer
from Backend.RealTimeSearchEngine import RealtimeSearchEngine
from Backend.Automation import Automation
from Backend.SpeechToText import speech_recognition
from Backend.chatbot import chatbot as ChatBot
from Backend.TextToSpeech import TextToSpeech
from Backend.ImageGenration import generate_images

# Load environment variables
env_vars = dotenv_values(".env")
USERNAME = env_vars.get("Username", "User")
ASSISTANT_NAME = env_vars.get("Assistance", "FRIDAY")
DEFAULT_MESSAGE = f"{USERNAME}: Hello {ASSISTANT_NAME}, How are you?\n{ASSISTANT_NAME}: Welcome {USERNAME}, I'm ready to help."
responsefile = r"Fronted\File\Responces.data"

class FaceAuthenticator:
    def __init__(self, faces_dir="Data/Private File"):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.known_faces = {}  # {user_id: face_encoding}
        self.load_known_faces(faces_dir)
    
    def load_known_faces(self, faces_dir):
        """Load known faces from directory"""
        if not os.path.exists(faces_dir):
            os.makedirs(faces_dir)
            return False
            
        for filename in os.listdir(faces_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                user_id = os.path.splitext(filename)[0]
                img_path = os.path.join(faces_dir, filename)
                img = cv2.imread(img_path)
                
                if img is not None:
                    # Pre-process image for faster recognition
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    gray = cv2.equalizeHist(gray)  # Improve contrast
                    faces = self.face_cascade.detectMultiScale(
                        gray, 
                        scaleFactor=1.1,
                        minNeighbors=5,
                        minSize=(100, 100),
                        flags=cv2.CASCADE_SCALE_IMAGE
                    )
                    
                    if len(faces) > 0:
                        x, y, w, h = faces[0]
                        face_roi = gray[y:y+h, x:x+w]
                        face_roi = cv2.resize(face_roi, (200, 200))
                        self.known_faces[user_id] = face_roi
        return len(self.known_faces) > 0
    
    def recognize_face(self):
        """Recognize face from camera with optimized performance"""
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # DirectShow for faster init
        if not cap.isOpened():
            return None
            
        try:
            # Set camera properties for faster processing
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 15)
            
            start_time = time.time()
            while time.time() - start_time < 5:  # 5 second timeout
                ret, frame = cap.read()
                if not ret:
                    continue
                
                # Convert to grayscale and equalize histogram
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.equalizeHist(gray)
                
                # Detect faces with optimized parameters
                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(100, 100),
                    flags=cv2.CASCADE_SCALE_IMAGE
                )
                
                for (x, y, w, h) in faces:
                    face_roi = gray[y:y+h, x:x+w]
                    face_roi = cv2.resize(face_roi, (200, 200))
                    
                    # Compare with known faces using template matching
                    best_match = None
                    best_score = 0
                    
                    for user_id, known_face in self.known_faces.items():
                        res = cv2.matchTemplate(face_roi, known_face, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(res)
                        
                        if max_val > best_score:
                            best_score = max_val
                            best_match = user_id
                    
                    if best_score > 0.75:  # Confidence threshold
                        return best_match
                
                time.sleep(0.05)  # Small delay to reduce CPU usage
        finally:
            cap.release()
        
        return None

class AuthDialog(QDialog):
    authentication_success = pyqtSignal(str)
    authentication_failed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Friday Authentication")
        self.setFixedSize(500, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: #111;
                color: white;
                border: 2px solid #444;
                border-radius: 10px;
            }
            QLabel {
                color: white;
                font-size: 16px;
            }
            QPushButton {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
                min-width: 120px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QLineEdit {
                background-color: #222;
                color: white;
                border: 1px solid #444;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
        """)

        # Initialize face recognizer
        self.face_recognizer = FaceAuthenticator()
        self.has_faces = self.face_recognizer.load_known_faces("Data/Private File")
        
        # Password from environment
        self.correct_password = env_vars.get("AUTH_PASSWORD", "friday123")
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header = QLabel("Friday Authentication")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
            padding-bottom: 20px;
        """)
        layout.addWidget(header)
        
        # Camera display
        self.camera_frame = QFrame()
        self.camera_frame.setFixedSize(400, 300)
        self.camera_frame.setStyleSheet("background-color: black;")
        
        self.camera_label = QLabel(self.camera_frame)
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setGeometry(0, 0, 400, 300)
        
        layout.addWidget(self.camera_frame, alignment=Qt.AlignCenter)
        
        # Status label
        self.status_label = QLabel("Select authentication method:")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Face recognition button
        self.face_btn = QPushButton()
        self.face_btn.setIcon(QIcon("Fronted/Graphics/face_icon.png"))  # Add your icon
        self.face_btn.setIconSize(QSize(40, 40))
        self.face_btn.setText("Face Recognition")
        self.face_btn.clicked.connect(self.start_face_recognition)
        self.face_btn.setEnabled(self.has_faces)
        buttons_layout.addWidget(self.face_btn)
        
        # Password button
        self.pass_btn = QPushButton()
        self.pass_btn.setIcon(QIcon("Fronted/Graphics/password_icon.png"))  # Add your icon
        self.pass_btn.setIconSize(QSize(40, 40))
        self.pass_btn.setText("Password")
        self.pass_btn.clicked.connect(self.show_password_input)
        buttons_layout.addWidget(self.pass_btn)
        
        layout.addLayout(buttons_layout)
        
        layout.addLayout(buttons_layout)
        
        # Password input (hidden initially)
        self.password_frame = QFrame()
        self.password_frame.hide()
        pass_layout = QVBoxLayout(self.password_frame)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.check_password)
        pass_layout.addWidget(self.password_input)
        
        self.submit_btn = QPushButton("Authenticate")
        self.submit_btn.clicked.connect(self.check_password)
        pass_layout.addWidget(self.submit_btn)
        
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self.hide_password_input)
        pass_layout.addWidget(self.back_btn)
        
        layout.addWidget(self.password_frame)
        
        # Attempts label
        self.attempts_label = QLabel()
        self.attempts_label.setAlignment(Qt.AlignCenter)
        self.attempts_label.hide()
        layout.addWidget(self.attempts_label)
        
        self.setLayout(layout)
        
        # Timer for face recognition
        self.camera_timer = QTimer()
        self.camera_timer.timeout.connect(self.update_camera)
        
        # Authentication attempts
        self.attempts = 0
        self.max_attempts = 3
    
    def start_face_recognition(self):
        """Start the face recognition process"""
        self.face_btn.setEnabled(False)
        self.pass_btn.setEnabled(False)
        self.status_label.setText("Looking for your face...")
        
        # Open camera
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            QMessageBox.warning(self, "Error", "Could not access camera")
            self.show_password_input()
            return
            
        # Set camera properties for optimal performance
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 15)
        
        self.camera_timer.start(30)  # Update every 30ms
        self.recognition_start_time = time.time()
    
    def update_camera(self):
        """Update camera feed and check for faces"""
        ret, frame = self.cap.read()
        if not ret:
            return
            
        # Display camera feed
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.camera_label.setPixmap(QPixmap.fromImage(q_img))
        
        # Try to recognize face every second
        current_time = time.time()
        if current_time - self.recognition_start_time >= 1:  # Check once per second
            self.recognition_start_time = current_time
            
            # Convert to grayscale and equalize histogram
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            
            # Detect faces
            faces = self.face_recognizer.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(100, 100),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            for (x, y, w, h) in faces:
                face_roi = gray[y:y+h, x:x+w]
                face_roi = cv2.resize(face_roi, (200, 200))
                
                # Compare with known faces
                best_match = None
                best_score = 0
                
                for user_id, known_face in self.face_recognizer.known_faces.items():
                    res = cv2.matchTemplate(face_roi, known_face, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    
                    if max_val > best_score:
                        best_score = max_val
                        best_match = user_id
                
                if best_score > 0.75:  # Confidence threshold
                    self.camera_timer.stop()
                    self.cap.release()
                    self.authentication_success.emit(best_match)
                    self.accept()
                    return
            
            # Timeout after 10 seconds
            if current_time - self.recognition_start_time > 10:
                self.camera_timer.stop()
                self.cap.release()
                QMessageBox.warning(self, "Timeout", "Face not recognized")
                self.show_password_input()
    
    def show_password_input(self):
        """Show password input fields"""
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.camera_timer.stop()
            self.cap.release()
            
        self.camera_frame.hide()
        self.password_frame.show()
        self.status_label.setText("Enter your password:")
        self.password_input.setFocus()
    
    def hide_password_input(self):
        """Hide password input fields"""
        self.password_frame.hide()
        self.camera_frame.show()
        self.status_label.setText("Select authentication method:")
        self.face_btn.setEnabled(self.has_faces)
        self.pass_btn.setEnabled(True)
        self.attempts_label.hide()
    
    def check_password(self):
        """Check the entered password"""
        password = self.password_input.text()
        
        if password == self.correct_password:
            self.authentication_success.emit("User")
            self.accept()
        else:
            self.attempts += 1
            remaining = self.max_attempts - self.attempts
            
            if remaining > 0:
                self.attempts_label.setText(
                    f"Incorrect password. {remaining} {'attempt' if remaining == 1 else 'attempts'} remaining."
                )
                self.attempts_label.show()
                self.password_input.clear()
            else:
                QMessageBox.critical(self, "Access Denied", "Too many failed attempts!")
                self.authentication_failed.emit()
                self.reject()

class FridayCore:
    def __init__(self, gui):
        self.gui = gui
        self.subprocesses = []

    def initialize_system(self):
        """Initialize system components and directories"""
        os.makedirs("Data", exist_ok=True)
        os.makedirs(os.path.join("Fronted", "File"), exist_ok=True)
        self.initialize_chatlog()

    def initialize_chatlog(self):
        """Initialize chat log file with default message"""
        chatlog_path = os.path.join("Data", "ChatLog.json")
        if not os.path.exists(chatlog_path) or os.path.getsize(chatlog_path) < 10:
            try:
                with open(chatlog_path, "w") as f:
                    json.dump([{
                        "role": "assistant",
                        "content": DEFAULT_MESSAGE
                    }], f, indent=4)
            except Exception as e:
                print(f"Error initializing chat log: {e}")
                traceback.print_exc()

    def process_command(self):
        """Optimized main processing loop for voice commands"""
        while True:
            if self.gui.mic_state:
                try:
                    result = speech_recognition()
                    if isinstance(result, dict) and not result.get('error', True):
                        translated_text = result.get('translated', '')
                        if translated_text:
                            self.handle_query(translated_text)
                    time.sleep(0.05)  # Reduced sleep time for more responsiveness
                except Exception as e:
                    print(f"Processing error: {e}")
                    traceback.print_exc()
                    time.sleep(1)  # Longer sleep after error
            else:
                time.sleep(0.5)  # Reduced sleep when mic is off

    def handle_query(self, query):
        try:
            with open(responsefile, "w") as f:
                f.write("true")

            decision = firstlayer(query)
            print(f"System Decision: {decision}")

            if isinstance(decision, str):
                decision = decision.split(", ")

            if not isinstance(decision, list):
                print(f"Error: Decision is not a list, got {type(decision)} instead.")
                return
            
            decision_lower = " ".join(decision).lower()
            automation_tasks = [cmd for cmd in decision_lower if any(
                key in cmd for key in ["open", "close", "play", "content", "google", "system"]
            )]
            
            if automation_tasks:
                print(f"Executing Automation Tasks: {automation_tasks}")
                asyncio.run(Automation(automation_tasks))
            elif "generate image" in decision_lower:
                prompt = decision_lower.replace("generate image", "").strip()
                self.handle_image_generation(prompt)
            else:
                if any(x in decision_lower for x in ["weather", "news", "stock", "realtime", "search"]):
                    return RealtimeSearchEngine(query)
                else:
                    return ChatBot(query)
        except Exception as e:
            print(f"Error in handle_query: {e}")
            return "Sorry, I encountered an error processing your request."
        finally:
            with open(responsefile, "w") as f:
                f.write("false")

    def handle_image_generation(self, prompt):
        """Call the image generation module"""
        try:
            generate_images(prompt)
        except Exception as e:
            print(f"Error during image generation: {e}")
            traceback.print_exc()

def launch_friday_system():
    """Launch the main Friday system"""
    app = QApplication(sys.argv)
    gui = FridayUI()
    core = FridayCore(gui)
    gui.connect_main(core)
    core.gui = gui
    core.initialize_system()
    
    processing_thread = threading.Thread(target=core.process_command, daemon=True)
    processing_thread.start()
    
    gui.show()
    sys.exit(app.exec_())

def authenticate_user():
    """Run the authentication dialog"""
    app = QApplication([])
    
    dialog = AuthDialog()
    dialog.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    
    # Center on screen
    screen_geometry = QApplication.desktop().screenGeometry()
    x = (screen_geometry.width() - dialog.width()) // 2
    y = (screen_geometry.height() - dialog.height()) // 2
    dialog.move(x, y)
    
    result = False
    username = None
    
    def on_success(name):
        nonlocal result, username
        result = True
        username = name
        dialog.accept()
    
    dialog.authentication_success.connect(on_success)
    dialog.exec_()
    
    return result, username

if __name__ == "__main__":
    try:
        print("🔐 Starting authentication...")
        
        # First try face recognition, fall back to password if needed
        success, username = authenticate_user()
        
        if success:
            print(f"✅ Welcome {username}! Access granted.")
            launch_friday_system()
        else:
            print("❌ Authentication failed! Access denied.")
            sys.exit(1)

    except Exception as e:
        print(f"Fatal error during authentication: {e}")
        traceback.print_exc()
        sys.exit(1)