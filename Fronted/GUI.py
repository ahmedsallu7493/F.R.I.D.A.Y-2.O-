import os
import json
import sys
import psutil
import speedtest
import threading
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLineEdit, QLabel, QStackedWidget,
    QScrollArea, QFileDialog, QInputDialog, QMessageBox, QMenu, 
    QAction, QStackedLayout, QFrame, QSizePolicy
)
from PyQt5.QtGui import QMovie, QIcon, QPixmap, QFont, QTextCursor, QPainter, QColor
from PyQt5.QtCore import Qt, QTimer, QDate, QTime, QSize, pyqtSignal, QObject, QThread, QPoint
from dotenv import dotenv_values
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Backend.TextToSpeech import TextToSpeech

sys.path.append(str(Path(__file__).resolve().parent.parent))

# Environment Setup
env_vars = dotenv_values(".env")
assistant_name = env_vars.get("AssistantName", "FRIDAY")
username = env_vars.get("Username", "User")
current_dir = os.getcwd()
msg = env_vars.get("msg")

# Path Configuration
Contentfile = r"Data\Content"
Imagefile = r"Data\Images"
GraphicsDirPath = os.path.join(current_dir, "Fronted", "Graphics")
ChatLogPath = os.path.join(current_dir, "Data", "ChatLog.json")
MIC_STATUS_PATH = r"Fronted\File\Mic.data"
datafile = r"F:\F.R.I.D.A.Y 2.O - Copy\Fronted\File\chat.data"
responsefile = r"Fronted\File\Responces.data"

# Ensure directories exist
os.makedirs(Contentfile, exist_ok=True)
os.makedirs(GraphicsDirPath, exist_ok=True)
os.makedirs(os.path.join(current_dir, "Data"), exist_ok=True)

class CommunicationChannel(QObject):
    message_received = pyqtSignal(str)

def DEFAULT_MESSAGE():
    return "Welcome to the assistant!"

class QueryWorker(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, main_object, query):
        super().__init__()
        self.main = main_object
        self.query = query

    def run(self):
        try:
            response = self.main.handle_query(self.query)
            self.finished_signal.emit(response)
        except Exception as e:
            self.error_signal.emit(str(e))

class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.mouse_pressed = False
        self.old_pos = None
        self.initUI()

    def initUI(self):
        self.setFixedHeight(40)
        self.setStyleSheet("""
            background-color: #1a1a1a;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        # Logo and Title
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap(os.path.join(GraphicsDirPath, "logo.jpg")).scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logo.setStyleSheet("background: transparent;")
        
        self.title = QLabel(assistant_name)
        self.title.setStyleSheet("""
            color: white;
            font-size: 16px;
            font-weight: bold;
            background: transparent;
        """)
        
        # Spacer to push buttons to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        spacer.setStyleSheet("background: transparent;")

        # Window control buttons
        self.minimize_btn = QPushButton("─")
        self.maximize_btn = QPushButton("□")
        self.close_btn = QPushButton("✕")

        # Button styling
        button_style = """
            QPushButton {
                color: white;
                background: transparent;
                border: none;
                font-size: 16px;
                padding: 0px 8px;
                min-width: 20px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }
        """
        close_style = button_style + """
            QPushButton:hover {
                background: #e81123;
            }
        """

        self.minimize_btn.setStyleSheet(button_style)
        self.maximize_btn.setStyleSheet(button_style)
        self.close_btn.setStyleSheet(close_style)

        # Button actions
        self.minimize_btn.clicked.connect(self.parent.showMinimized)
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        self.close_btn.clicked.connect(self.parent.close)

        # Add widgets to layout
        layout.addWidget(self.logo)
        layout.addWidget(self.title)
        layout.addWidget(spacer)
        layout.addWidget(self.minimize_btn)
        layout.addWidget(self.maximize_btn)
        layout.addWidget(self.close_btn)

    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.maximize_btn.setText("□")
        else:
            self.parent.showMaximized()
            self.maximize_btn.setText("❐")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse_pressed = True
            self.old_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.mouse_pressed and self.old_pos:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.parent.move(self.parent.x() + delta.x(), self.parent.y() + delta.y())
            self.old_pos = event.globalPos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.mouse_pressed = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.toggle_maximize()
        super().mouseDoubleClickEvent(event)

class FridayUI(QMainWindow):
    def connect_main(self, main_object):
        self.main = main_object

    def __init__(self):
        super().__init__()
        self.current_dir = current_dir
        self.graphics_path = GraphicsDirPath
        self.datafile = datafile
        self.ChatLogPath = ChatLogPath
        self.assistant_name = assistant_name
        self.username = username
        self.mic_state = True
        self.wifi_speed = "Measuring..."
        self.comm = CommunicationChannel()
        self.last_speedtest = 0
        self.loading_screen = None
        self.worker = None
        self.last_message_count = 0

        # Remove default title bar
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.initUI()
        self.initialize_mic_state()
        self.load_chat_history()
        self.chat_page = None
        self.main = None
        self.start_history_checker()

    def initUI(self):
        # Main container widget with rounded corners
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.setCentralWidget(self.container)
        
        # Main layout for the container
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Add custom title bar
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        # Content area
        content_widget = QWidget()
        content_widget.setObjectName("content")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Background
        self.background = QLabel(content_widget)
        self.background.setScaledContents(True)
        self.bg_movie = QMovie(os.path.join(self.graphics_path, "bg.gif"))
        self.background.setMovie(self.bg_movie)
        self.bg_movie.start()
        self.background.lower()

        # Foreground Widget
        self.foreground_widget = QWidget(content_widget)
        self.foreground_layout = QVBoxLayout(self.foreground_widget)
        self.foreground_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header_layout = QHBoxLayout()
        self.foreground_layout.addLayout(header_layout)
        self.create_header_buttons(header_layout)

        # Stacked Widget for Pages
        self.create_stacked_widget()
        self.foreground_layout.addWidget(self.stacked_widget, stretch=3)

        # Bottom Controls
        bottom_layout = QHBoxLayout()
        self.foreground_layout.addLayout(bottom_layout)

        # Bottom Widgets
        self.create_mic_button()
        bottom_layout.addWidget(self.mic_btn)

        self.create_clock()
        bottom_layout.addWidget(self.clock_label)

        self.create_system_monitor()
        bottom_layout.addWidget(self.system_monitor)

        content_layout.addWidget(self.foreground_widget)
        main_layout.addWidget(content_widget)

        # Apply Styles
        self.set_styles()

    def set_styles(self):
        self.setStyleSheet("""
            #container {
                background-color: #1a1a1a;
                border-radius: 10px;
            }
            #content {
                background-color: rgba(0, 0, 0, 0.7);
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }
            QLabel {
                color: white;
            }
            QMainWindow {
                background-color: transparent;
            }
        """)

    def show_loading_screen(self):
        """Show fullscreen loading animation"""
        if not hasattr(self, 'loading_screen') or not self.loading_screen:
            # Create loading screen if it doesn't exist
            self.loading_screen = QLabel(self)
            self.loading_screen.setAlignment(Qt.AlignCenter)
            self.loading_screen.setStyleSheet("""
                background-color: rgba(0, 0, 0, 180);
                border: none;
                border-radius: 10px;
            """)
            
            # Load and setup GIF
            self.loading_movie = QMovie(os.path.join(self.graphics_path, "loading.png"))
            loading_label = QLabel(self.loading_screen)
            loading_label.setAlignment(Qt.AlignCenter)
            loading_label.setMovie(self.loading_movie)
            
            # Center the GIF
            layout = QVBoxLayout(self.loading_screen)
            layout.addWidget(loading_label, 0, Qt.AlignCenter)
            
            # Start animation
            self.loading_movie.start()
        
        # Show and raise to top
        self.loading_screen.resize(self.size())
        self.loading_screen.show()
        self.loading_screen.raise_()

    def hide_loading_screen(self):
        """Hide loading animation"""
        if hasattr(self, 'loading_screen') and self.loading_screen:
            self.loading_screen.hide()
            self.loading_movie.stop()

    def process_query(self, message):
        """Handle query in a separate thread"""
        self.show_loading_screen()
        QApplication.processEvents()  # Force UI update
        
        # Create and start worker thread
        self.worker = QueryWorker(self.main, message)
        self.worker.finished_signal.connect(self.handle_query_result)
        self.worker.error_signal.connect(self.handle_query_error)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.worker.start()

    def handle_query_result(self, response):
        """Handle successful query result"""
        try:
            if response:
                self.chat_display.append(f"<b style='color:lightgreen'>{self.assistant_name}:</b> {response}")
                self.save_to_chat_log("assistant", response)
                clean_response = response.replace("Response of Real time Engine ", "")
                
                # Update response file
                with open(responsefile, "w") as f:
                    f.write("false")
                
                # Run TTS in separate thread
                tts_thread = threading.Thread(
                    target=lambda: TextToSpeech(clean_response),
                    daemon=True
                )
                tts_thread.start()
        finally:
            self.hide_loading_screen()

    def handle_query_error(self, error_msg):
        """Handle query errors"""
        self.hide_loading_screen()
        self.chat_display.append(f"<b style='color:red'>Error:</b> {error_msg}")
        print(f"Query error: {error_msg}")
        with open(responsefile, "w") as f:
            f.write("false")

    def create_stacked_widget(self):
        self.stacked_widget = QStackedWidget()
        
        # Create all pages
        self.create_voice_page()
        self.create_chat_page()
        self.create_files_page()
        self.create_image_page()
        
        # Add to foreground layout
        self.foreground_layout.addWidget(self.stacked_widget)

    def create_voice_page(self):
        self.voice_page = QWidget()

        # Container for background and overlay (acts as a canvas)
        container = QFrame(self.voice_page)
        container.setStyleSheet("background: transparent;")
        container.setGeometry(250, 0, 1000, 800)  # Adjust size as needed

        # --- Background GIF ---
        self.bg_label = QLabel(container)
        self.bg_label.setGeometry(0, 0, 800, 600)
        self.bg_label.setScaledContents(True)
        self.bg_label.setStyleSheet("background: transparent;")
        self.bg_movie = QMovie(os.path.join(self.graphics_path, "bg.gif"))
        self.bg_label.setMovie(self.bg_movie)
        self.bg_movie.start()

        # --- Overlay Label ---
        self.voice_status = QLabel(container)
        self.voice_status.setGeometry(0, 250, 800, 100)  # Centered vertically
        self.voice_status.setAlignment(Qt.AlignCenter)
        self.voice_status.setFont(QFont("Arial", 24, QFont.Bold))
        self.voice_status.setStyleSheet("""
            color: black;
            background-color: rgba(0, 0, 0, 0);
        """)
        self.voice_status.setText("F.R.I.D.A.Y Is Activated")

        # Add the voice page to the stacked widget
        self.stacked_widget.addWidget(self.voice_page)

    def create_mic_button(self):
        self.mic_btn = QPushButton()
        self.mic_btn.setIcon(QIcon(os.path.join(self.graphics_path, "Mic On.png")))
        self.mic_btn.setIconSize(QSize(60, 60))
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 30px;
            }
        """)
        self.mic_btn.clicked.connect(self.toggle_mic)

    def initialize_mic_state(self):
        try:
            with open(MIC_STATUS_PATH, "r") as f:
                self.mic_state = f.read().strip().lower() == "true"
        except:
            self.mic_state = False
        self.update_mic_ui()

    def update_mic_ui(self):
        icon = "Mic On.png" if self.mic_state else "Mic Off.png"
        self.mic_btn.setIcon(QIcon(os.path.join(self.graphics_path, icon)))
        self.voice_status.setText("F.R.I.D.A.Y Is Activated" if self.mic_state else "Mic is off")

    def toggle_mic(self):
        self.mic_state = not self.mic_state
        try:
            with open(MIC_STATUS_PATH, "w") as f:
                f.write(str(self.mic_state))
        except Exception as e:
            print(f"Error saving mic state: {e}")
        self.update_mic_ui()

    def create_clock(self):
        self.clock_label = QLabel()
        self.clock_label.setFont(QFont("Consolas", 16))
        self.clock_label.setStyleSheet("color: cyan;")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)
        self.update_clock()

    def update_clock(self):
        current_date = QDate.currentDate().toString("dddd, MMMM dd, yyyy")
        current_time = QTime.currentTime().toString("hh:mm:ss")
        self.clock_label.setText(f"{current_date}\n{current_time}")

    def create_system_monitor(self):
        self.system_monitor = QLabel()
        self.system_monitor.setFont(QFont("Consolas", 12))
        self.system_monitor.setStyleSheet("color: white;")

        self.sys_timer = QTimer(self)
        self.sys_timer.timeout.connect(self.update_system_stats)
        self.sys_timer.start(2000)
        self.update_system_stats()

    def update_system_stats(self):
        """Update system monitoring statistics"""
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        # Only run speedtest if it's been more than 5 minutes since last test
        if time.time() - self.last_speedtest > 300:  # 300 seconds = 5 minutes
            self.run_speedtest()
        
        stats = f"CPU: {cpu}%\nRAM: {ram}%\nWi-Fi: {self.wifi_speed}"
        self.system_monitor.setText(stats)

    def run_speedtest(self):
        try:
            st = speedtest.Speedtest()
            st.get_best_server()
            download = st.download() / 1_000_000
            upload = st.upload() / 1_000_000
            self.wifi_speed = f"Down: {download:.2f} Mbps\nUp: {upload:.2f} Mbps"
            self.last_speedtest = time.time()
        except:
            self.wifi_speed = "Speed test failed"

    def create_chat_page(self):
        self.chat_page = QWidget()
        self.chat_page.setStyleSheet("background-color: black;")  # 🔴 Set black background for the whole page

        layout = QVBoxLayout(self.chat_page)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: black;
                color: white;
                border: none;
                font-family: Consolas;
                font-size: 14px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.chat_display)

        # Chat input
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type your message...")
        self.chat_input.setStyleSheet("""
            QLineEdit {
                background-color: #111;
                color: white;
                border: 1px solid #333;
                padding: 8px;
                border-radius: 4px;
            }
        """)
        self.chat_input.returnPressed.connect(self.send_message)
        layout.addWidget(self.chat_input)

        self.chat_page.setLayout(layout)
        self.stacked_widget.addWidget(self.chat_page)

    def send_message(self):
        mic_path = Path(MIC_STATUS_PATH)
        mic_status = mic_path.read_text().strip().lower() if mic_path.exists() else "true"

        if mic_status == "true":
            self.chat_display.append(f"<i style='color:red'>{self.assistant_name}:</i> Mic is currently active. Please wait.")
            return

        message = self.chat_input.text().strip()
        if message:
            self.chat_display.append(f"<b style='color:cyan'>{self.username}:</b> {message}")
            self.save_to_chat_log("user", message)
            self.chat_input.clear()
            # self.check_env_message()

            if hasattr(self, "main") and hasattr(self.main, "handle_query"):
                self.show_loading_screen()  # Show loading before processing
                QApplication.processEvents()  # Force UI update
                
                try:
                    response = self.main.handle_query(message)
                    with open(responsefile, "w") as f:
                        f.write("false")
                    
                    if response:
                        self.chat_display.append(f"<b style='color:lightgreen'>{self.assistant_name}:</b> {response}")
                        self.save_to_chat_log("assistant", response)
                        clean_response = response.replace("Response of Real time Engine ", "")
                        
                        with open(responsefile) as f:
                            data = f.read()
                            if data == "false":
                                self.hide_loading_screen()  # Hide when done
                                
                        # Show loading during TTS
                        TextToSpeech(clean_response)
                        
                except Exception as e:
                    self.hide_loading_screen()
                    print(f"Error in query handling: {e}")

            else:
                self.chat_display.append(f"<i style='color:orange'>{self.assistant_name}:</i> Backend not ready.")

    def save_to_chat_log(self, role, content):
        entry = {"role": role, "content": content}
        try:
            if os.path.exists(self.ChatLogPath):
                with open(self.ChatLogPath, "r+") as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = []
                    data.append(entry)
                    f.seek(0)
                    json.dump(data, f, indent=4)
                    f.truncate()
            else:
                with open(self.ChatLogPath, "w") as f:
                    json.dump([entry], f, indent=4)
        except Exception as e:
            print(f"Error saving to chat log: {e}")

    def load_chat_history(self):
        try:
            if os.path.exists(self.ChatLogPath):
                with open(self.ChatLogPath, "r") as f:
                    messages = json.load(f)[-100:]  # Last 100 messages

                if len(messages) == self.last_message_count:
                    return  # No change, skip update

                self.chat_display.clear()
                for msg in messages:
                    role = msg.get('role', 'unknown')
                    name = self.username if role == "user" else self.assistant_name
                    color = "cyan" if role == "user" else "lightgreen"
                    self.chat_display.append(f"<b style='color:{color}'>{name}:</b> {msg.get('content', '')}")
                self.chat_display.moveCursor(QTextCursor.End)
                self.last_message_count = len(messages)
        except Exception as e:
            print(f"Load history error: {e}")

    def start_history_checker(self):
        self.history_timer = QTimer(self)
        self.history_timer.timeout.connect(self.load_chat_history)
        self.history_timer.start(5000)  # Every 5 seconds

    def create_files_page(self):
        files_page = QWidget()
        layout = QVBoxLayout(files_page)

        # File List
        self.file_list = QTextEdit()
        self.file_list.setReadOnly(True)
        self.file_list.setStyleSheet("""
            QTextEdit {
                background-color: rgba(10, 10, 10, 0.9);
                color: white;
                font-family: Consolas;
                font-size: 13px;
                border: 2px solid #333;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        layout.addWidget(QLabel("📁 Files in Directory:"))
        layout.addWidget(self.file_list)

        # Buttons
        button_layout = QHBoxLayout()

        open_btn = QPushButton("Open")
        open_btn.setStyleSheet(self.get_button_style())
        open_btn.clicked.connect(self.open_file)
        button_layout.addWidget(open_btn)

        rename_btn = QPushButton("Rename")
        rename_btn.setStyleSheet(self.get_button_style())
        rename_btn.clicked.connect(self.rename_file)
        button_layout.addWidget(rename_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet(self.get_button_style("red"))
        delete_btn.clicked.connect(self.delete_file)
        button_layout.addWidget(delete_btn)

        layout.addLayout(button_layout)
        self.refresh_file_list()

        files_page.setLayout(layout)
        self.stacked_widget.addWidget(files_page)

    def get_button_style(self, color="default"):
        base_style = """
            QPushButton {
                background-color: rgba(30, 30, 30, 0.8);
                color: white;
                border: 1px solid #444;
                border-radius: 5px;
                padding: 8px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 60, 0.8);
            }
        """
        if color == "red":
            return base_style + """
                QPushButton {
                    border: 1px solid #800000;
                }
                QPushButton:hover {
                    background-color: rgba(100, 0, 0, 0.8);
                }
            """
        return base_style

    def refresh_file_list(self):
        try:
            files = os.listdir(Contentfile)
            self.file_list.setText('\n'.join(files) if files else "No files found.")
        except Exception as e:
            self.file_list.setText(f"Error: {e}")

    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open File", Contentfile)
        if filename:
            os.startfile(filename)

    def rename_file(self):
        files = os.listdir(Contentfile)
        if not files:
            QMessageBox.information(self, "Info", "No files to rename.")
            return
        old_name, ok = QInputDialog.getItem(self, "Rename File", "Select file:", files, editable=False)
        if ok:
            new_name, ok2 = QInputDialog.getText(self, "Rename File", "Enter new name:")
            if ok2 and new_name:
                os.rename(os.path.join(Contentfile, old_name), os.path.join(Contentfile, new_name))
                self.refresh_file_list()

    def delete_file(self):
        files = os.listdir(Contentfile)
        if not files:
            QMessageBox.information(self, "Info", "No files to delete.")
            return
        file_name, ok = QInputDialog.getItem(self, "Delete File", "Select file:", files, editable=False)
        if ok:
            file_path = os.path.join(Contentfile, file_name)
            os.remove(file_path)
            self.refresh_file_list()

    def create_image_page(self):
        image_page = QWidget()
        layout = QVBoxLayout(image_page)

        # Title Label
        label = QLabel("\U0001F5BC Images in Directory:")
        label.setStyleSheet("color: white; font-weight: bold; font-size: 16px;")
        layout.addWidget(label)

        # Button Layout
        button_layout = QHBoxLayout()
        
        # Refresh Button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self.get_button_style())
        refresh_btn.clicked.connect(self.refresh_images)
        button_layout.addWidget(refresh_btn)
        
        # Open Button
        open_btn = QPushButton("Open Image")
        open_btn.setStyleSheet(self.get_button_style())
        open_btn.clicked.connect(self.open_image_file)
        button_layout.addWidget(open_btn)
        
        # Delete Button
        delete_btn = QPushButton("Delete Image")
        delete_btn.setStyleSheet(self.get_button_style("red"))
        delete_btn.clicked.connect(self.delete_image)
        button_layout.addWidget(delete_btn)
        
        layout.addLayout(button_layout)

        # Scroll Area for Images
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.image_scroll_layout = QHBoxLayout(self.scroll_content)
        
        # Load images initially
        self.refresh_images()
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)

        image_page.setLayout(layout)
        self.stacked_widget.addWidget(image_page)

    def refresh_images(self):
        # Clear existing images
        for i in reversed(range(self.image_scroll_layout.count())): 
            widget = self.image_scroll_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        
        try:
            image_files = [f for f in os.listdir(Imagefile) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            
            if not image_files:
                no_images_label = QLabel("No images found in directory.")
                no_images_label.setStyleSheet("color: white; font-size: 14px;")
                self.image_scroll_layout.addWidget(no_images_label)
                return
                
            for img_file in image_files:
                img_frame = QWidget()
                img_frame_layout = QVBoxLayout(img_frame)
                img_frame_layout.setAlignment(Qt.AlignCenter)
                
                # Image Label
                img_label = QLabel()
                pixmap = QPixmap(os.path.join(Imagefile, img_file)).scaled(
                    300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                img_label.setPixmap(pixmap)
                img_label.setAlignment(Qt.AlignCenter)
                
                # File Name Label
                file_label = QLabel(img_file)
                file_label.setStyleSheet("color: white; font-size: 12px;")
                file_label.setAlignment(Qt.AlignCenter)
                file_label.setWordWrap(True)
                
                img_frame_layout.addWidget(img_label)
                img_frame_layout.addWidget(file_label)
                
                # Add context menu for right-click actions
                img_label.setContextMenuPolicy(Qt.CustomContextMenu)
                img_label.customContextMenuRequested.connect(
                    lambda pos, file=img_file: self.show_image_context_menu(pos, file)
                )
                
                self.image_scroll_layout.addWidget(img_frame)

        except Exception as e:
            err_label = QLabel(f"Error loading images: {e}")
            err_label.setStyleSheet("color: red; font-size: 14px;")
            self.image_scroll_layout.addWidget(err_label)

    def show_image_context_menu(self, pos, image_file):
        context_menu = QMenu(self)
        
        open_action = QAction("Open", self)
        open_action.triggered.connect(lambda: self.open_specific_image(image_file))
        
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.delete_specific_image(image_file))
        
        context_menu.addAction(open_action)
        context_menu.addAction(delete_action)
        
        # Get the sender widget (the image label that was right-clicked)
        sender_widget = self.sender()
        if sender_widget:
            context_menu.exec_(sender_widget.mapToGlobal(pos))

    def open_specific_image(self, image_file):
        image_path = os.path.join(Imagefile, image_file)
        if os.path.exists(image_path):
            os.startfile(image_path)
        else:
            QMessageBox.warning(self, "Error", f"Image not found: {image_file}")

    def delete_specific_image(self, image_file):
        reply = QMessageBox.question(
            self, 'Delete Image', 
            f"Are you sure you want to delete '{image_file}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                image_path = os.path.join(Imagefile, image_file)
                if os.path.exists(image_path):
                    os.remove(image_path)
                    self.refresh_images()
                    QMessageBox.information(self, "Success", f"Deleted '{image_file}' successfully.")
                else:
                    QMessageBox.warning(self, "Error", f"Image not found: {image_file}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete image: {str(e)}")

    def open_image_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Image", 
            Imagefile, 
            "Image Files (*.png *.jpg *.jpeg *.gif)"
        )
        if filename:
            os.startfile(filename)

    def delete_image(self):
        image_files = [f for f in os.listdir(Imagefile) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
        
        if not image_files:
            QMessageBox.information(self, "Info", "No images to delete.")
            return
        
        image_file, ok = QInputDialog.getItem(
            self, 
            "Delete Image", 
            "Select image to delete:", 
            image_files, 
            editable=False
        )
        
        if ok and image_file:
            self.delete_specific_image(image_file)

    def create_header_buttons(self, layout):
        button_data = [
            ("Home.png", 0, "Home"),
            ("chat.png", 1, "Chat"),
            ("files.png", 2, "Files"),
            ("image.png", 3, "Images"),
        ]

        for icon_name, index, tooltip in button_data:
            button = QPushButton()
            button.setIcon(QIcon(os.path.join(self.graphics_path, icon_name)))
            button.setIconSize(QSize(50, 50))
            button.setToolTip(tooltip)
            button.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.1);
                    border-radius: 25px;
                }
            """)
            button.clicked.connect(lambda _, idx=index: self.stacked_widget.setCurrentIndex(idx))
            layout.addWidget(button)

    def closeEvent(self, event):
        """Clean up when window closes"""
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FridayUI()
    window.show()
    sys.exit(app.exec_())