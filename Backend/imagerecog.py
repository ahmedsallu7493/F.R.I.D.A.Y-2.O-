import os
import cv2
import sys
import numpy as np
import time
from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                            QLabel, QPushButton, QLineEdit, QMessageBox, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QImage, QPixmap, QFont, QIcon

class FaceRecognizer:
    def __init__(self):
        self.known_faces = {}
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
    def load_known_faces(self, faces_dir):
        """Load known faces from directory and create face encodings"""
        if not os.path.exists(faces_dir):
            os.makedirs(faces_dir)
            return False
            
        for filename in os.listdir(faces_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                user_id = os.path.splitext(filename)[0]
                img_path = os.path.join(faces_dir, filename)
                img = cv2.imread(img_path)
                
                if img is not None:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    faces = self.face_cascade.detectMultiScale(
                        gray, 
                        scaleFactor=1.1,
                        minNeighbors=5,
                        minSize=(100, 100))
                    
                    if len(faces) > 0:
                        x, y, w, h = faces[0]
                        face_roi = gray[y:y+h, x:x+w]
                        face_roi = cv2.resize(face_roi, (200, 200))
                        self.known_faces[user_id] = face_roi
        return len(self.known_faces) > 0

    def recognize_face(self, frame):
        """Recognize face from camera frame"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(100, 100))
        
        for (x, y, w, h) in faces:
            face_roi = gray[y:y+h, x:x+w]
            face_roi = cv2.resize(face_roi, (200, 200))
            
            best_match = None
            best_score = 0
            
            # Compare with known faces
            for user_id, known_face in self.known_faces.items():
                # Use template matching
                res = cv2.matchTemplate(face_roi, known_face, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                
                if max_val > best_score:
                    best_score = max_val
                    best_match = user_id
            
            if best_score > 0.7:  # Confidence threshold
                return best_match
        
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
        self.face_recognizer = FaceRecognizer()
        self.has_faces = self.face_recognizer.load_known_faces("Data/Private File")
        
        # Password from environment
        self.correct_password = "friday123"  # Should be loaded from .env in production
        
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
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            QMessageBox.warning(self, "Error", "Could not access camera")
            self.show_password_input()
            return
            
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
            recognized_user = self.face_recognizer.recognize_face(frame)
            
            if recognized_user:
                self.camera_timer.stop()
                self.cap.release()
                self.authentication_success.emit(recognized_user)
                self.accept()
            elif current_time - self.recognition_start_time > 10:  # Timeout after 10 seconds
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
    
    if dialog.exec_() == QDialog.Accepted:
        print("Authentication successful!")
        return True
    else:
        print("Authentication failed!")
        return False

if __name__ == "__main__":
    if authenticate_user():
        # Launch your main application
        print("Starting Friday system...")
    else:
        sys.exit(1)