import json
import re
import sys
from dataclasses import dataclass
from enum import Enum

import requests
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QListWidget, QTextEdit, QWidget, QMessageBox, QCheckBox, QStatusBar, QComboBox, QLabel, QFileDialog
)
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable

@dataclass
class TranscriptSegment:
    start: float
    text: str

class FileType(Enum):
    JSON = "json"
    TXT = "txt"

class StyledButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(200, 50)
        self.setStyleSheet("font-family: 'Segoe UI'; font-size: 12pt; padding: 5px;")

class YouTubeTranscriptApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initialize_ui()
        self.initialize_data()

    def initialize_ui(self):
        self.setWindowTitle("YouTube Transcript Viewer")
        self.setGeometry(100, 100, 900, 600)
        self.setWindowIcon(QIcon('icon.ico'))  # Set the application icon

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        self.setup_input_ui()
        self.setup_queue_ui()
        self.setup_transcript_ui()
        self.setup_clean_options_ui()
        self.setup_save_buttons_ui()
        self.setup_status_bar()
        self.setup_github_link()

    def initialize_data(self):
        self.current_transcript = None
        self.modified_transcript_text = ""
        self.video_queue = []
        self.video_titles = {}

    def setup_input_ui(self):
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 10, 0, 10)
        input_layout.setSpacing(10)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Podaj link do filmu YouTube")
        self.url_input.setFixedHeight(50)
        self.url_input.setStyleSheet("font-family: 'Segoe UI'; font-size: 12pt; padding: 5px; border: none;")

        self.fetch_button = StyledButton("Dodaj do kolejki")
        self.fetch_button.clicked.connect(self.add_to_queue)

        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.fetch_button)
        self.layout.addLayout(input_layout)

    def setup_queue_ui(self):
        self.video_queue_list = QListWidget()
        self.video_queue_list.setFixedHeight(150)
        self.video_queue_list.setStyleSheet("font-family: 'Segoe UI'; font-size: 10pt; padding: 5px;")

        self.video_queue_list.addItem("Brak filmów w kolejce")
        self.video_queue_list.itemClicked.connect(self.fetch_transcripts_from_queue)
        self.layout.addWidget(self.video_queue_list)

    def setup_transcript_ui(self):
        self.transcripts_list = QComboBox()
        self.transcripts_list.setFixedHeight(50)
        self.transcripts_list.setStyleSheet("font-family: 'Segoe UI'; font-size: 10pt; padding: 5px;")
        self.transcripts_list.addItem("Brak dostępnych transkrypcji")
        self.transcripts_list.currentIndexChanged.connect(self.display_transcript)
        self.layout.addWidget(self.transcripts_list)

        self.transcript_viewer = QTextEdit()
        self.transcript_viewer.setFixedHeight(300)
        self.transcript_viewer.setPlaceholderText("Brak treści transkrypcji")
        self.transcript_viewer.setStyleSheet(
            "border: none; font-family: 'Segoe UI'; font-size: 10pt; padding: 5px; scrollbar: QScrollBar:vertical { width: 10px; background: #f0f0f0; border-radius: 5px; } QScrollBar::handle:vertical { background: #888; border-radius: 5px; }")
        self.layout.addWidget(self.transcript_viewer)

    def setup_clean_options_ui(self):
        clean_options_layout = QHBoxLayout()
        clean_options_layout.setContentsMargins(10, 10, 10, 10)
        clean_options_layout.setSpacing(10)
        self.remove_timestamps_checkbox = QCheckBox("Usuń znaczniki czasu")
        self.remove_timestamps_checkbox.setStyleSheet("font-family: 'Segoe UI'; font-size: 10pt; padding: 5px;")
        self.remove_timestamps_checkbox.stateChanged.connect(self.update_transcript_viewer)
        clean_options_layout.addWidget(self.remove_timestamps_checkbox)
        self.layout.addLayout(clean_options_layout)

    def setup_save_buttons_ui(self):
        save_buttons_layout = QHBoxLayout()
        save_buttons_layout.setContentsMargins(10, 10, 10, 10)
        save_buttons_layout.setSpacing(10)
        self.save_json_button = StyledButton("Zapisz jako JSON")
        self.save_txt_button = StyledButton("Zapisz jako TXT")
        self.save_json_button.clicked.connect(lambda: self.save_transcript(FileType.JSON))
        self.save_txt_button.clicked.connect(lambda: self.save_transcript(FileType.TXT))
        save_buttons_layout.addWidget(self.save_json_button)
        save_buttons_layout.addWidget(self.save_txt_button)
        self.layout.addLayout(save_buttons_layout)

    def setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("font-family: 'Segoe UI'; font-size: 10pt; padding: 5px;")
        self.setStatusBar(self.status_bar)

    def setup_github_link(self):
        self.github_link = QLabel()
        github_url = "https://github.com/gitpyblog/YouTubeText"
        self.github_link.setText(github_url)
        self.github_link.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.github_link.setStyleSheet("color: grey; padding: 5px;")
        self.status_bar.addPermanentWidget(self.github_link)

    def add_to_queue(self):
        video_url = self.url_input.text().strip()
        video_id = self.extract_video_id(video_url)
        if not video_id:
            self.display_message("Nieprawidłowy link do filmu. Podaj link do filmu YouTube.", error=True)
            return

        video_title = self.video_titles.get(video_id) or self.get_video_title(video_url) or "Nieznany tytuł"
        self.video_titles[video_id] = video_title

        if self.video_queue_list.count() == 1 and self.video_queue_list.item(0).text() == "Brak filmów w kolejce":
            self.video_queue_list.clear()

        self.video_queue.append(video_id)
        self.video_queue_list.addItem(f"{video_title} ({video_url})")
        self.url_input.clear()
        self.display_message("Film dodany do kolejki")

    def fetch_transcripts_from_queue(self, item):
        if item.text() == "Brak filmów w kolejce":
            return

        video_index = self.video_queue_list.row(item)
        video_id = self.video_queue[video_index]
        try:
            self.status_bar.showMessage("Pobieranie transkrypcji...", 2000)
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            self.populate_transcripts_list(transcripts)
            self.status_bar.showMessage("Transkrypcje pobrane", 5000)
        except VideoUnavailable:
            self.display_message("Błąd: Wideo niedostępne.", error=True)
        except NoTranscriptFound:
            self.display_message("Błąd: Nie znaleziono transkrypcji.", error=True)
        except TranscriptsDisabled:
            self.display_message("Błąd: Transkrypcje wyłączone dla tego filmu.", error=True)
        except Exception as e:
            self.display_message(f"Nieoczekiwany błąd: {str(e)}", error=True)

    def populate_transcripts_list(self, transcripts):
        self.transcripts_list.clear()
        for transcript in transcripts:
            lang = transcript.language
            lang_code = transcript.language_code
            self.transcripts_list.addItem(f"{lang} ({lang_code})", userData=transcript)
        if self.transcripts_list.count() == 0:
            self.transcripts_list.addItem("Brak dostępnych transkrypcji")

    def display_message(self, message, error=False):
        if error:
            QMessageBox.critical(self, "Błąd", message)
        self.status_bar.showMessage(message, 7000)

    @staticmethod
    def extract_video_id(url):
        match = re.search(r'(?:v=|youtu\.be/|embed/|v/|watch\?v=|&v=)([\w-]{11})', url)
        return match.group(1) if match else None

    def get_video_title(self, url):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
                return title_match.group(1).replace(" - YouTube", "").strip() if title_match else None
        except requests.RequestException:
            return None

    def update_transcript_viewer(self):
        if not self.current_transcript:
            return

        # Transkrypcja linia po linii
        transcript_lines = [
            f"[{segment['start']:.2f}] {segment['text']}"
            for segment in self.current_transcript
        ]

        if self.remove_timestamps_checkbox.isChecked():
            cleaned_lines = []
            for line in transcript_lines:
                # Usuń znacznik czasu z każdej linii
                line_without_timestamp = re.sub(r'\[\d+\.\d{2}\]', '', line)
                # Usuń dodatkowe spacje i dodaj do listy
                cleaned_lines.append(re.sub(r'\s+', ' ', line_without_timestamp).strip())

            self.modified_transcript_text = "\n".join(cleaned_lines)
        else:
            self.modified_transcript_text = "\n".join(transcript_lines)

        # Wyświetl przetworzoną transkrypcję
        self.transcript_viewer.setText(self.modified_transcript_text)
        self.status_bar.showMessage("Transkrypcja wyświetlona", 3000)

    def display_transcript(self):
        if self.transcripts_list.currentText() == "Brak dostępnych transkrypcji":
            return

        transcript = self.transcripts_list.currentData()
        if not transcript:
            return

        try:
            segments = transcript.fetch()
            self.current_transcript = segments
            self.update_transcript_viewer()
            self.status_bar.showMessage("Transkrypcja wyświetlona", 3000)
        except Exception as e:
            self.display_message(f"Nie udało się pobrać transkrypcji: {str(e)}", error=True)

    def save_transcript(self, file_type: FileType):
        if not self.modified_transcript_text:
            self.display_message("Brak transkrypcji do zapisania.", error=True)
            return

        try:
            # Użycie QFileDialog do wyboru ścieżki zapisu
            if file_type == FileType.JSON:
                file_path, _ = QFileDialog.getSaveFileName(self, "Zapisz jako JSON", re.sub(r'[\\\\/:*?"<>|]', '', self.video_titles.get(self.video_queue[-1], 'transcript')) + ".json", "Pliki JSON (*.json)")
                if not file_path:
                    return  # użytkownik anulował zapis

                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(self.modified_transcript_text.split("\n"), file, indent=4, ensure_ascii=False)
            elif file_type == FileType.TXT:
                file_path, _ = QFileDialog.getSaveFileName(self, "Zapisz jako TXT", re.sub(r'[\\\\/:*?"<>|]', '', self.video_titles.get(self.video_queue[-1], 'transcript')) + ".txt", "Pliki tekstowe (*.txt)")
                if not file_path:
                    return  # użytkownik anulował zapis

                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(self.modified_transcript_text)

            self.display_message(f"Transkrypcja zapisana jako {file_type.value.upper()}.")
        except Exception as e:
            self.display_message(f"Nie udało się zapisać pliku: {str(e)}", error=True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeTranscriptApp()
    window.show()
    sys.exit(app.exec())
