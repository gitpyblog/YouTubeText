import sys
import re
import requests
import json
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QListWidget, QTextEdit, QWidget, QMessageBox, QFileDialog, QCheckBox, QStatusBar, QComboBox
)
from PyQt6.QtCore import Qt
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable

@dataclass
class TranscriptSegment:
    start: float
    text: str

class FileType(Enum):
    JSON = "json"
    TXT = "txt"

class YouTubeTranscriptApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initialize_ui()
        self.initialize_data()

    def initialize_ui(self):
        self.setWindowTitle("YouTube Transcript Viewer")
        self.setGeometry(100, 100, 1200, 600)

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)

        self.setup_input_ui()
        self.setup_queue_ui()
        self.setup_transcript_ui()
        self.setup_clean_options_ui()
        self.setup_save_buttons_ui()
        self.setup_status_bar()

    def initialize_data(self):
        self.current_transcript = None
        self.video_queue = []
        self.video_titles = {}

    def setup_input_ui(self):
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Podaj link do filmu YouTube")
        self.url_input.setFixedHeight(50)

        self.fetch_button = QPushButton("Dodaj do kolejki")
        self.fetch_button.setFixedSize(200, 50)
        self.fetch_button.clicked.connect(self.add_to_queue)

        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.fetch_button)
        self.layout.addLayout(input_layout)

    def setup_queue_ui(self):
        self.video_queue_list = QListWidget()
        self.video_queue_list.setFixedHeight(150)

        self.video_queue_list.addItem("Brak filmów w kolejce")
        self.video_queue_list.itemClicked.connect(self.fetch_transcripts_from_queue)
        self.layout.addWidget(self.video_queue_list)

    def setup_transcript_ui(self):
        self.transcripts_list = QComboBox()
        self.transcripts_list.setFixedHeight(50)
        self.transcripts_list.addItem("Brak dostępnych transkrypcji")
        self.transcripts_list.currentIndexChanged.connect(self.display_transcript)
        self.layout.addWidget(self.transcripts_list)

        self.transcript_viewer = QTextEdit()
        self.transcript_viewer.setFixedHeight(300)
        self.transcript_viewer.setPlaceholderText("Brak treści transkrypcji")
        self.layout.addWidget(self.transcript_viewer)

    def setup_clean_options_ui(self):
        clean_options_layout = QHBoxLayout()
        self.remove_timestamps_checkbox = QCheckBox("Usuń znaczniki czasu")
        self.remove_timestamps_checkbox.stateChanged.connect(self.update_transcript_viewer)
        clean_options_layout.addWidget(self.remove_timestamps_checkbox)
        self.layout.addLayout(clean_options_layout)

    def setup_save_buttons_ui(self):
        save_buttons_layout = QHBoxLayout()
        self.save_json_button = QPushButton("Zapisz jako JSON")
        self.save_json_button.setFixedSize(200, 50)
        self.save_json_button.clicked.connect(lambda: self.save_transcript(FileType.JSON))
        self.save_txt_button = QPushButton("Zapisz jako TXT")
        self.save_txt_button.setFixedSize(200, 50)
        self.save_txt_button.clicked.connect(lambda: self.save_transcript(FileType.TXT))
        save_buttons_layout.addWidget(self.save_json_button)
        save_buttons_layout.addWidget(self.save_txt_button)
        self.layout.addLayout(save_buttons_layout)

    def setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def add_to_queue(self):
        video_url = self.url_input.text().strip()
        video_id = self.extract_video_id(video_url)
        if not video_id:
            self.display_message("Nieprawidłowy link do filmu.", error=True)
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

    def save_transcript(self, file_type: FileType):
        if not self.current_transcript:
            self.display_message("Najpierw wybierz transkrypcję do zapisania.", error=True)
            return

        transcript_text = self.transcript_viewer.toPlainText()
        options = QFileDialog.Options()
        file_filter = "Plik JSON (*.json)" if file_type == FileType.JSON else "Plik TXT (*.txt)"

        current_row = self.video_queue_list.currentRow()
        if current_row == -1:
            self.display_message("Nie wybrano żadnego filmu do zapisania.", error=True)
            return

        current_video_id = self.video_queue[current_row]
        default_file_name = self.video_titles.get(current_video_id, "transkrypcja")

        file_path, _ = QFileDialog.getSaveFileName(self, "Zapisz plik", f"{default_file_name}", file_filter,
                                                   options=options)
        if not file_path:
            return

        file_path = Path(file_path)

        try:
            if file_type == FileType.JSON:
                transcript_data = [TranscriptSegment(segment['start'], segment['text']).__dict__ for segment in
                                   self.current_transcript]
                with file_path.open("w", encoding="utf-8") as file:
                    json.dump(transcript_data, file, ensure_ascii=False, indent=4)
            elif file_type == FileType.TXT:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(transcript_text)
            self.display_message(f"Plik został zapisany jako {file_path}")
        except Exception as e:
            self.display_message(f"Nie udało się zapisać pliku: {str(e)}", error=True)

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

        transcript_text = "\n".join(
            [f"[{segment['start']:.2f}] {segment['text']}" for segment in self.current_transcript])

        if self.remove_timestamps_checkbox.isChecked():
            transcript_text = re.sub(r'\[\d+\.\d{2}\]', '', transcript_text)
            transcript_text = "\n".join([re.sub(r'\s+', ' ', line).strip() for line in transcript_text.splitlines()])

        self.transcript_viewer.setText(transcript_text)
        self.status_bar.showMessage("Transkrypcja wyświetlona", 5000)

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
            self.status_bar.showMessage("Transkrypcja wyświetlona", 5000)
        except Exception as e:
            self.display_message(f"Nie udało się pobrać transkrypcji: {str(e)}", error=True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeTranscriptApp()
    window.show()
    sys.exit(app.exec())
