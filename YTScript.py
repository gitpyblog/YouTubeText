import sys
import re
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QListWidget, QTextEdit, QWidget, QMessageBox, QFileDialog, QCheckBox, QStatusBar, QComboBox
)
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
import json

class YouTubeTranscriptApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Transcript Viewer")
        self.setGeometry(100, 100, 1200, 600)

        # Load Modern Fonts
        self.setStyleSheet("font-family: 'Roboto', 'Open Sans'; font-size: 16px;")

        # Layouts
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)

        # Input and Button
        self.input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setFixedHeight(50)
        self.url_input.setStyleSheet("padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
        self.url_input.setPlaceholderText("Podaj link do filmu YouTube")
        self.fetch_button = QPushButton("Dodaj do kolejki")
        self.fetch_button.setFixedWidth(200)
        self.fetch_button.setFixedHeight(50)
        self.fetch_button.clicked.connect(self.add_to_queue)
        self.input_layout.addWidget(self.url_input)
        self.input_layout.addWidget(self.fetch_button)

        # List of Videos in Queue
        self.video_queue_list = QListWidget()
        self.video_queue_list.setFixedHeight(150)
        self.video_queue_list.setStyleSheet(
            "border: 1px solid #ccc; background-color: #fafafa; padding: 10px; font-size: 16px; "
            "QScrollBar:vertical {border: none; background-color: #E0E0E0; width: 12px; margin: 0px;} "
            "QScrollBar::handle:vertical {background-color: #A0A0A0; min-height: 20px; border-radius: 6px;} "
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height: 0px;}"
        )
        self.video_queue_list.addItem("Brak filmów w kolejce")
        self.video_queue_list.itemClicked.connect(self.fetch_transcripts_from_queue)

        # Transcript List (QComboBox for selecting available transcripts)
        self.transcripts_list = QComboBox()
        self.transcripts_list.setStyleSheet(
            "border: 1px solid #ccc; background-color: #fafafa; padding: 10px; font-size: 16px; "
            "QScrollBar:vertical {border: none; background-color: #E0E0E0; width: 12px; margin: 0px;} "
            "QScrollBar::handle:vertical {background-color: #C0C0C0; min-height: 20px; border-radius: 6px;} "
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height: 0px;}"
        )
        self.transcripts_list.setFixedHeight(50)
        self.transcripts_list.addItem("Brak dostępnych transkrypcji")
        self.transcripts_list.currentIndexChanged.connect(self.display_transcript)

        # Clean Options
        self.clean_options_layout = QHBoxLayout()
        self.remove_filler_checkbox = QCheckBox("Usuń wtrącenia (np. uhm, eee)")
        self.remove_timestamps_checkbox = QCheckBox("Usuń znaczniki czasu")
        self.remove_filler_checkbox.stateChanged.connect(self.update_transcript_viewer)
        self.remove_timestamps_checkbox.stateChanged.connect(self.update_transcript_viewer)
        self.clean_options_layout.addWidget(self.remove_filler_checkbox)
        self.clean_options_layout.addWidget(self.remove_timestamps_checkbox)

        # Transcript Viewer
        self.transcript_viewer = QTextEdit()
        self.transcript_viewer.setStyleSheet(
            "border: 1px solid #ccc; background-color: #fafafa; padding: 10px; font-size: 16px; "
            "QScrollBar:vertical {border: none; background-color: #E0E0E0; width: 12px; margin: 0px;} "
            "QScrollBar::handle:vertical {background-color: #C0C0C0; min-height: 20px; border-radius: 6px;} "
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height: 0px;}"
        )
        self.transcript_viewer.setFixedHeight(300)
        self.transcript_viewer.setPlaceholderText("Brak treści transkrypcji")
        self.transcript_viewer.setReadOnly(False)

        # Save Buttons
        self.save_buttons_layout = QHBoxLayout()
        self.save_json_button = QPushButton("Zapisz jako JSON")
        self.save_json_button.setFixedHeight(50)
        self.save_json_button.clicked.connect(lambda: self.save_transcript("json"))
        self.save_txt_button = QPushButton("Zapisz jako TXT")
        self.save_txt_button.setFixedHeight(50)
        self.save_txt_button.clicked.connect(lambda: self.save_transcript("txt"))
        self.save_buttons_layout.addWidget(self.save_json_button)
        self.save_buttons_layout.addWidget(self.save_txt_button)

        # Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("padding: 10px;")
        self.setStatusBar(self.status_bar)

        # Add to layout
        self.layout.addLayout(self.input_layout)
        self.layout.addWidget(self.video_queue_list)
        self.layout.addWidget(self.transcripts_list)
        self.layout.addLayout(self.clean_options_layout)
        self.layout.addWidget(self.transcript_viewer)
        self.layout.addLayout(self.save_buttons_layout)

        # Transcript Data
        self.current_transcript = None
        self.video_queue = []
        self.video_titles = {}

    def add_to_queue(self):
        video_url = self.url_input.text().strip()
        video_id = self.extract_video_id(video_url)
        if not video_id:
            QMessageBox.warning(self, "Błąd", "Nieprawidłowy link do filmu.")
            self.status_bar.showMessage("Nieprawidłowy link do filmu.", 5000)
            return

        # Check if title is already cached
        if video_id in self.video_titles:
            video_title = self.video_titles[video_id]
        else:
            video_title = self.get_video_title(video_url)
            if not video_title:
                video_title = "Nieznany tytuł"
            self.video_titles[video_id] = video_title

        if self.video_queue_list.count() == 1 and self.video_queue_list.item(0).text() == "Brak filmów w kolejce":
            self.video_queue_list.clear()

        self.video_queue.append(video_id)
        self.video_queue_list.addItem(f"{video_title} ({video_url})")
        self.url_input.clear()
        self.status_bar.showMessage("Film dodany do kolejki", 5000)

    def fetch_transcripts_from_queue(self, item):
        # Clear previous transcript and transcript list
        self.transcript_viewer.clear()
        self.transcripts_list.clear()

        if item.text() == "Brak filmów w kolejce":
            return

        video_index = self.video_queue_list.row(item)
        video_id = self.video_queue[video_index]
        try:
            self.status_bar.showMessage("Pobieranie transkrypcji...", 2000)
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            if transcripts:
                for transcript in transcripts:
                    lang = transcript.language
                    lang_code = transcript.language_code
                    self.transcripts_list.addItem(f"{lang} ({lang_code})", userData=transcript)
            else:
                self.transcripts_list.addItem("Brak dostępnych transkrypcji")
            self.status_bar.showMessage("Transkrypcje pobrane", 5000)
        except (VideoUnavailable, NoTranscriptFound, TranscriptsDisabled):
            QMessageBox.warning(self, "Błąd", "Brak dostępnych transkrypcji dla tego filmu.")
            self.status_bar.showMessage("Brak dostępnych transkrypcji dla tego filmu.", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nieoczekiwany błąd: {str(e)}")
            self.status_bar.showMessage(f"Nieoczekiwany błąd: {str(e)}", 5000)

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
            QMessageBox.critical(self, "Błąd", f"Nie udało się pobrać transkrypcji: {str(e)}")
            self.status_bar.showMessage(f"Nie udało się pobrać transkrypcji: {str(e)}", 5000)

    def update_transcript_viewer(self):
        if not self.current_transcript:
            return

        transcript_text = "\n".join([f"[{segment['start']:.2f}] {segment['text']}" for segment in self.current_transcript])

        # Apply cleaning based on checkboxes
        if self.remove_filler_checkbox.isChecked():
            unwanted_phrases = ["uhm", "eee", "no więc", "[Muzyka]"]
            for phrase in unwanted_phrases:
                transcript_text = re.sub(re.escape(phrase), "", transcript_text, flags=re.IGNORECASE).strip()

        if self.remove_timestamps_checkbox.isChecked():
            transcript_text = re.sub(r'\[\d+\.\d{2}\]', '', transcript_text)
            transcript_text = "\n".join([re.sub(r'\s+', ' ', line).strip() for line in transcript_text.splitlines()])

        self.transcript_viewer.setText(transcript_text)
        self.status_bar.showMessage("Transkrypcja wyświetlona", 5000)

    def save_transcript(self, file_type):
        if not self.current_transcript:
            QMessageBox.warning(self, "Błąd", "Najpierw wybierz transkrypcję do zapisania.")
            self.status_bar.showMessage("Wybierz transkrypcję do zapisania.", 5000)
            return

        # Apply cleaning options before saving
        transcript_text = self.transcript_viewer.toPlainText()

        options = QFileDialog.Options()
        file_filter = "Plik JSON (*.json)" if file_type == "json" else "Plik TXT (*.txt)"

        # Use cached title if available
        current_video_id = self.video_queue[self.video_queue_list.currentRow()]
        default_file_name = self.video_titles.get(current_video_id, "transkrypcja")

        file_path, _ = QFileDialog.getSaveFileName(self, "Zapisz plik", default_file_name, file_filter, options=options)
        if not file_path:
            return

        try:
            if file_type == "json":
                transcript_data = [{"start": segment["start"], "text": segment["text"]} for segment in self.current_transcript]
                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(transcript_data, file, ensure_ascii=False, indent=4)
            elif file_type == "txt":
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(transcript_text)
            QMessageBox.information(self, "Sukces", f"Plik został zapisany jako {file_path}")
            self.status_bar.showMessage(f"Plik został zapisany jako {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nie udało się zapisać pliku: {str(e)}")
            self.status_bar.showMessage(f"Nie udało się zapisać pliku: {str(e)}", 5000)

    @staticmethod
    def extract_video_id(url):
        if "youtube.com/watch?v=" in url:
            return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        return None

    @staticmethod
    def get_video_title(url):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
                if title_match:
                    return title_match.group(1).replace(" - YouTube", "").strip()
        except requests.RequestException as e:
            print(f"Błąd podczas pobierania tytułu: {e}")
        return None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeTranscriptApp()
    window.show()
    sys.exit(app.exec_())
