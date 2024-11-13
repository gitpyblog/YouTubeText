import os
import re
import sys
import threading
from PyQt5 import QtWidgets, QtGui, QtCore
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi


class YouTubeTranscriptApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.youtube_client = None
        self.channel_id = None
        self.video_data = []
        self.init_ui()

    def init_ui(self):
        # Inicjalizacja interfejsu użytkownika
        self.setWindowTitle("YouTubeText - Pobieranie transkrypcji z YouTube")
        self.setGeometry(100, 100, 900, 600)

        # Wprowadzanie klucza API
        self.api_key_label = QtWidgets.QLabel("Klucz API YouTube Data v3:", self)
        self.api_key_input = QtWidgets.QLineEdit(self)
        self.api_key_input.setFixedWidth(400)
        self.save_api_key_button = QtWidgets.QPushButton("Zapisz", self)
        self.save_api_key_button.clicked.connect(self.save_api_key)

        # Wprowadzanie URL kanału
        self.channel_url_label = QtWidgets.QLabel("URL kanału YouTube:", self)
        self.channel_url_input = QtWidgets.QLineEdit(self)
        self.channel_url_input.setFixedWidth(400)
        self.fetch_channel_button = QtWidgets.QPushButton("Pobierz ID Kanału", self)
        self.fetch_channel_button.clicked.connect(self.fetch_channel_id)
        self.channel_id_label = QtWidgets.QLabel("", self)

        # Wybór katalogu do zapisu transkrypcji
        self.output_dir_label = QtWidgets.QLabel("Katalog do zapisu transkrypcji:", self)
        self.output_dir_input = QtWidgets.QLineEdit(self)
        self.output_dir_input.setText("transcriptions")
        self.output_dir_button = QtWidgets.QPushButton("Wybierz", self)
        self.output_dir_button.clicked.connect(self.select_output_directory)

        # Tekst statusu
        self.status_label = QtWidgets.QLabel("", self)

        # Widok listy wideo
        self.video_list_text = QtWidgets.QTextEdit(self)
        self.video_list_text.setReadOnly(True)
        self.video_list_text.setFixedHeight(200)

        # Przyciski do pobierania filmów i transkrypcji
        self.fetch_videos_button = QtWidgets.QPushButton("Pobierz listę filmów", self)
        self.fetch_videos_button.clicked.connect(self.fetch_videos)
        self.download_all_button = QtWidgets.QPushButton("Pobierz wszystkie dostępne transkrypcje", self)
        self.download_all_button.clicked.connect(self.download_all_transcriptions)

        # Layout
        layout = QtWidgets.QVBoxLayout()
        form_layout = QtWidgets.QFormLayout()

        form_layout.addRow(self.api_key_label, self.api_key_input)
        form_layout.addWidget(self.save_api_key_button)
        form_layout.addRow(self.channel_url_label, self.channel_url_input)
        form_layout.addWidget(self.fetch_channel_button)
        form_layout.addWidget(self.channel_id_label)
        form_layout.addRow(self.output_dir_label, self.output_dir_input)
        form_layout.addWidget(self.output_dir_button)

        layout.addLayout(form_layout)
        layout.addWidget(self.fetch_videos_button)
        layout.addWidget(self.video_list_text)
        layout.addWidget(self.download_all_button)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def save_api_key(self):
        # Zapisz klucz API
        api_key = self.api_key_input.text()
        if api_key:
            try:
                self.youtube_client = build("youtube", "v3", developerKey=api_key)
                self.status_label.setText("🔑 Zapisano klucz API.")
            except Exception as e:
                self.status_label.setText(f"🔐 Błąd klucza API: {e}")

    def fetch_channel_id(self):
        # Pobierz ID kanału YouTube na podstawie URL
        if not self.youtube_client:
            self.status_label.setText("🔐 Klucz API nie został zapisany.")
            return

        channel_url = self.channel_url_input.text()
        try:
            self.channel_id = self.get_channel_id_from_url(channel_url)
            self.channel_id_label.setText(f"ID Kanału: {self.channel_id}")
        except ValueError as e:
            self.status_label.setText(str(e))
        except Exception as e:
            self.status_label.setText(f"Błąd: {e}")

    def get_channel_id_from_url(self, channel_url):
        # Metoda do wyodrębnienia ID kanału z URL
        if "channel/" in channel_url:
            return channel_url.split("channel/")[1]
        elif "@" in channel_url:
            username = channel_url.split("@")[1]
            request = self.youtube_client.search().list(
                part="snippet",
                q=username,
                type="channel",
                maxResults=1
            )
            response = request.execute()
            if "items" in response and len(response["items"]) > 0:
                return response["items"][0]["snippet"]["channelId"]
        else:
            request = self.youtube_client.channels().list(
                part="id",
                forUsername=channel_url.split("/")[-1]
            )
            response = request.execute()
            if "items" in response and len(response["items"]) > 0:
                return response["items"][0]["id"]
        raise ValueError("Nie udało się znaleźć ID kanału dla podanego URL.")

    def select_output_directory(self):
        # Wybierz katalog do zapisu transkrypcji
        options = QtWidgets.QFileDialog.Options()
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Wybierz katalog do zapisu transkrypcji", "", options)
        if directory:
            self.output_dir_input.setText(directory)
            self.status_label.setText(f"Wybrano katalog: {directory}")

    def fetch_videos(self):
        # Pobierz listę wideo z kanału
        if not self.youtube_client or not self.channel_id:
            self.status_label.setText("🔐 Klucz API lub ID kanału nie zostało zapisane.")
            return

        self.status_label.setText("Pobieranie listy wideo...")
        request = self.youtube_client.search().list(
            part="id,snippet",
            channelId=self.channel_id,
            maxResults=50,
            type="video"
        )
        response = request.execute()

        self.video_data = []
        for item in response.get("items", []):
            video_id = item["id"].get("videoId")
            if video_id:
                title = item["snippet"]["title"]
                self.video_data.append((video_id, title))

        self.video_list_text.clear()
        for video_id, title in self.video_data:
            self.video_list_text.append(f"{title} (ID: {video_id})")

        self.status_label.setText("Pobieranie zakończone.")

    def download_all_transcriptions(self):
        # Pobierz transkrypcje dla wszystkich wideo
        output_dir = self.output_dir_input.text()
        if not output_dir:
            self.status_label.setText("Wybierz katalog do zapisu transkrypcji.")
            return

        for video_id, title in self.video_data:
            self.status_label.setText(f"Pobieranie transkrypcji dla wideo: {title}")
            QtCore.QCoreApplication.processEvents()
            threading.Thread(target=self.download_transcription, args=(video_id, title, output_dir)).start()

    def download_transcription(self, video_id, title, output_dir):
        # Pobierz transkrypcję dla pojedynczego wideo
        try:
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcripts.find_transcript(['pl'])
            transcript_text = "\n".join([entry["text"] for entry in transcript.fetch()])
            sanitized_title = re.sub(r'[/*?"<>|:]', "", title)
            output_filename = f"{sanitized_title}.txt"
            output_path = os.path.join(output_dir, output_filename)
            with open(output_path, "w", encoding="utf-8") as file:
                file.write(transcript_text)
            self.status_label.setText(f"Transkrypcja zapisana: {output_filename}")
        except Exception as e:
            self.status_label.setText(f"Błąd pobierania transkrypcji: {e}")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = YouTubeTranscriptApp()
    window.show()
    sys.exit(app.exec_())
