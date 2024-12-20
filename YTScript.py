import json
import re
import sys
from dataclasses import dataclass
from enum import StrEnum
import requests
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QListWidget, QTextEdit, QWidget, QMessageBox, QCheckBox, QStatusBar, QComboBox, QLabel, QFileDialog,
    QListWidgetItem
)
from PyQt6.QtCore import QUrl
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable

@dataclass
class TranscriptSegment:
    start: float = 0.0
    text: str = ""

class FileType(StrEnum):
    JSON = "json"
    TXT = "txt"

def set_widget_style(widget, font_family='Segoe UI', font_size=10, padding=0, margin=0, border='none', height=None):
    style = f"font-family: '{font_family}'; font-size: {font_size}pt; padding: {padding}px; margin: {margin}px; border: {border}"
    if height:
        style += f"; min-height: {height}px; max-height: {height}px"
    widget.setStyleSheet(style)

def create_standard_layout():
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)  # Zmniejszenie odstępu do minimum
    return layout

def create_video_widget(title, url):
    widget = QWidget()
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)  # Zmniejszenie marginesów do minimum
    layout.setSpacing(0)  # Zmniejszenie odstępu do minimum
    layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # Ustawienie wyrównania układu w pionie na środek

    title_label = QLabel(title)
    title_font = QFont()
    title_font.setBold(True)
    title_label.setFont(title_font)
    set_widget_style(title_label, font_size=10, height=30, margin='3px 0')  # Ujednolicenie wysokości, stylu i paddingu

    url_label = QLabel(f"<a href=\"{url}\" style=\"text-decoration: none;\">{url}</a>")
    url_font = QFont()
    url_font.setPointSize(10)
    url_label.setFont(url_font)

    url_label.setTextFormat(Qt.TextFormat.RichText)
    url_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    url_label.setOpenExternalLinks(True)
    set_widget_style(url_label, font_size=10, height=30, margin='3px 0')  # Ujednolicenie wysokości, stylu i paddingu

    layout.addWidget(title_label)
    layout.addWidget(url_label, alignment=Qt.AlignmentFlag.AlignLeft)
    widget.setLayout(layout)

    return widget

class StyledButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(50)
        style = """
            QPushButton {
                font-family: 'Segoe UI';
                font-size: 12pt;
                padding-left: 20px;
                padding-right: 20px;
                margin: 0px;
                border: none;
                border-radius: 0px;
                background-color: #ffffff;
                color: #000;
                box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.2), -5px -5px 15px rgba(255, 255, 255, 0.8);
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                box-shadow: 3px 3px 10px rgba(0, 0, 0, 0.15), -3px -3px 10px rgba(255, 255, 255, 0.7);
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
                box-shadow: inset 5px 5px 15px rgba(0, 0, 0, 0.2), inset -5px -5px 15px rgba(255, 255, 255, 0.8);
            }
        """
        self.setStyleSheet(style)
        self.setFixedHeight(50)
        style = """
            QPushButton {
                font-family: 'Segoe UI';
                font-size: 12pt;
                padding: 0px;
                margin: 0px;
                border: none;
                border-radius: 0px;
                background-color: #ffffff;
                color: #000;
                box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.2), -5px -5px 15px rgba(255, 255, 255, 0.8);
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                box-shadow: 3px 3px 10px rgba(0, 0, 0, 0.15), -3px -3px 10px rgba(255, 255, 255, 0.7);
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
                box-shadow: inset 5px 5px 15px rgba(0, 0, 0, 0.2), inset -5px -5px 15px rgba(255, 255, 255, 0.8);
            }
        """
        self.setStyleSheet(style)

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
        input_layout = create_standard_layout()
        input_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Podaj link do filmu YouTube")
        self.url_input.setFixedHeight(50)
        set_widget_style(self.url_input, font_size=12, padding=10)

        self.fetch_button = StyledButton("Dodaj do kolejki")
        self.fetch_button.setFixedWidth(150)
        self.fetch_button.clicked.connect(self.add_to_queue)

        input_layout.addWidget(self.url_input)
        input_layout.addSpacing(5)
        input_layout.addWidget(self.fetch_button)
        self.layout.addLayout(input_layout)

    def setup_queue_ui(self):
        self.video_queue_list = QListWidget()
        self.video_queue_list.setFixedHeight(150)
        set_widget_style(self.video_queue_list, font_size=10)

        scrollbar_style = """
            QScrollBar:vertical {
                border: none;
                background: #ffffff;
                width: 14px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #e0e0e0;
                min-height: 30px;
                border-radius: 0px;
            }
            QScrollBar::handle:vertical:hover {
                background: #c0c0c0;
            }
            QScrollBar::handle:vertical:pressed {
                background: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """
        self.video_queue_list.verticalScrollBar().setStyleSheet(scrollbar_style)

        self.video_queue_list.addItem("Brak filmów w kolejce")
        self.video_queue_list.itemClicked.connect(self.handle_item_click)
        self.layout.addWidget(self.video_queue_list)

    def setup_transcript_ui(self):
        self.transcripts_list = QComboBox()
        self.transcripts_list.setFixedHeight(50)
        self.transcripts_list.setStyleSheet('QComboBox QAbstractItemView::item { padding-left: 50px; }')
        style = """
            QComboBox {
                font-family: 'Segoe UI';
                font-size: 10pt;
                padding-left: 10px;
                margin: 3px 0;
                border: none;
                border-radius: 0px;
                background-color: #ffffff;
                color: #000;
                box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.2), -5px -5px 15px rgba(255, 255, 255, 0.8);
                font-family: 'Segoe UI';
                font-size: 10pt;
                padding: 0px;
                margin: 3px 0;
                border: none;
                border-radius: 0px;
                background-color: #ffffff;
                color: #000;
                box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.2), -5px -5px 15px rgba(255, 255, 255, 0.8);
                qproperty-alignment: 'AlignLeft';
            }
                font-family: 'Segoe UI';
                font-size: 10pt;
                padding: 0px;
                margin: 3px 0;
                border: none;
                border-radius: 0px;
                background-color: #ffffff;
                color: #000;
                box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.2), -5px -5px 15px rgba(255, 255, 255, 0.8);
                QAbstractItemView {
                    padding-left: 50px;
                }
                padding-left: 50px;
                font-family: 'Segoe UI';
                font-size: 10pt;
                padding: 0px;
                margin: 3px 0;
                border: none;
                border-radius: 0px;
                background-color: #ffffff;
                color: #000;
                box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.2), -5px -5px 15px rgba(255, 255, 255, 0.8);
            }
            QComboBox:hover {
                background-color: #f0f0f0;
                box-shadow: 3px 3px 10px rgba(0, 0, 0, 0.15), -3px -3px 10px rgba(255, 255, 255, 0.7);
            }
            QComboBox::drop-down {
                border: none;
                background-color: transparent;
            }

        """

        self.transcripts_list.setStyleSheet(style)
        self.transcripts_list.addItem("Brak dostępnych transkrypcji")
        self.transcripts_list.currentIndexChanged.connect(self.display_transcript)
        self.layout.addWidget(self.transcripts_list)

        self.transcript_viewer = QTextEdit()
        self.transcript_viewer.setFixedHeight(300)
        self.transcript_viewer.setPlaceholderText("Brak treści transkrypcji")
        self.transcript_viewer.setReadOnly(True)
        set_widget_style(self.transcript_viewer, font_size=10, border='none')

        scrollbar_style = """
            QScrollBar:vertical {
                border: none;
                background: #ffffff;
                width: 14px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #e0e0e0;
                min-height: 30px;
                border-radius: 0px;
            }
            QScrollBar::handle:vertical:hover {
                background: #c0c0c0;
            }
            QScrollBar::handle:vertical:pressed {
                background: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """
        self.transcript_viewer.verticalScrollBar().setStyleSheet(scrollbar_style)

        self.layout.addWidget(self.transcript_viewer)

    def setup_clean_options_ui(self):
        clean_options_layout = QHBoxLayout()
        clean_options_layout.setContentsMargins(0, 0, 0, 0)
        self.remove_timestamps_checkbox = QCheckBox("Usuń znaczniki czasu")
        style = """
            QCheckBox {
                font-family: 'Segoe UI';
                font-size: 10pt;
                padding: 0px;
                margin: 0px;
                border: none;
                border-radius: 0px;
                color: #000;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 0px;
                background-color: #ffffff;

            }
            QCheckBox::indicator:checked {
                background-color: #e0e0e0;
            }
        """
        self.remove_timestamps_checkbox.setStyleSheet(style)
        self.remove_timestamps_checkbox.stateChanged.connect(self.update_transcript_viewer)
        clean_options_layout.addWidget(self.remove_timestamps_checkbox)
        self.layout.addLayout(clean_options_layout)

    def setup_save_buttons_ui(self):
        save_buttons_layout = QHBoxLayout()  # Użyj QHBoxLayout dla rozciągnięcia przycisków
        save_buttons_layout.setContentsMargins(0, 0, 0, 0)
        save_buttons_layout.setSpacing(5)  # Dodaj odstęp między przyciskami

        self.save_json_button = StyledButton("Zapisz jako JSON")
        self.save_json_button.clicked.connect(lambda: self.save_transcript(FileType.JSON))
        self.save_txt_button = StyledButton("Zapisz jako TXT")
        self.save_txt_button.clicked.connect(lambda: self.save_transcript(FileType.TXT))

        # Dodaj przyciski do layoutu i ustaw rozciąganie, aby wypełnić szerokość
        save_buttons_layout.addWidget(self.save_json_button)
        save_buttons_layout.addSpacing(5)  # Ustaw odstęp między przyciskami
        save_buttons_layout.addWidget(self.save_txt_button)

        self.layout.addLayout(save_buttons_layout)

    def setup_status_bar(self):
        self.status_bar = QStatusBar()
        set_widget_style(self.status_bar, font_size=10)
        self.setStatusBar(self.status_bar)

    def setup_github_link(self):
        self.github_link = QLabel()
        github_url = "https://github.com/gitpyblog/YouTubeText"
        self.github_link.setText(
            f'<a href="{github_url}" style="text-decoration: none; color: grey;">Repozytorium GitHub</a>')
        self.github_link.setOpenExternalLinks(True)
        self.github_link.setAlignment(Qt.AlignmentFlag.AlignRight)
        set_widget_style(self.github_link, padding=5)
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

        widget = create_video_widget(video_title, video_url)
        item = QListWidgetItem()
        item.setSizeHint(widget.sizeHint())
        self.video_queue_list.addItem(item)
        self.video_queue_list.setItemWidget(item, widget)

        item.setData(Qt.ItemDataRole.UserRole, video_id)
        self.video_queue.append(video_id)
        self.url_input.clear()
        self.display_message("Film dodany do kolejki")

    def handle_item_click(self, item):
        video_id = item.data(Qt.ItemDataRole.UserRole)
        if video_id:
            self.fetch_transcripts_from_queue(video_id)

    def fetch_transcripts_from_queue(self, video_id):
        if not video_id:
            return
        try:
            self.status_bar.showMessage("Pobieranie transkrypcji...", 2000)
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            self.populate_transcripts_list(transcripts)
            self.status_bar.showMessage("Transkrypcje pobrane", 5000)
        except (VideoUnavailable, NoTranscriptFound, TranscriptsDisabled) as e:
            self.display_message(f"Błąd: {str(e)}", error=True)
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
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
                return title_match.group(1).replace(" - YouTube", "").strip() if title_match else None
        except requests.RequestException:
            return None

    def update_transcript_viewer(self):
        if not self.current_transcript:
            return

        transcript_lines = [
            f"[{segment['start']:.2f}] {segment['text']}"
            for segment in self.current_transcript
        ]

        if self.remove_timestamps_checkbox.isChecked():
            cleaned_lines = [
                re.sub(r'\[\d+\.\d{2}\]', '', line).strip()
                for line in transcript_lines
            ]
            self.modified_transcript_text = "\n".join(cleaned_lines)
        else:
            self.modified_transcript_text = "\n".join(transcript_lines)

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

    def save_transcript(self, file_type: FileType | None) -> None:
        if not self.modified_transcript_text:
            self.display_message("Brak transkrypcji do zapisania.", error=True)
            return

        try:
            if file_type == FileType.JSON:
                file_path, _ = QFileDialog.getSaveFileName(self, "Zapisz jako JSON", re.sub(r'[\\/:*?"<>|]', '',
                                                                                            self.video_titles.get(
                                                                                                self.video_queue[-1],
                                                                                                'transcript')) + ".json",
                                                           "Pliki JSON (*.json)")
                if not file_path:
                    return

                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(self.modified_transcript_text.split("\n"), file, indent=4, ensure_ascii=False)
            elif file_type == FileType.TXT:
                file_path, _ = QFileDialog.getSaveFileName(self, "Zapisz jako TXT", re.sub(r'[\\/:*?"<>|]', '',
                                                                                           self.video_titles.get(
                                                                                               self.video_queue[-1],
                                                                                               'transcript')) + ".txt",
                                                           "Pliki tekstowe (*.txt)")
                if not file_path:
                    return

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
