import os
import re
import sys
import json
import requests
from PyQt5 import QtWidgets, QtGui, QtCore
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from datetime import datetime


class YouTubeTranscriptApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.youtube_client = None
        self.channel_id = None
        self.channel_title = ""
        self.subscribers = "0"
        self.video_count = "0"
        self.channel_thumbnail_url = ""
        self.video_data = []
        self.transcriptions = {}  # Store transcriptions in memory

        # Load settings
        self.settings = self.load_settings()
        self.init_ui()

    def init_ui(self):
        # Inicjalizacja interfejsu użytkownika
        self.setWindowTitle("YouTubeText - Pobieranie transkrypcji z YouTube")
        self.setGeometry(100, 100, 1300, 900)
        self.setStyleSheet(self.load_stylesheet())

        # Wprowadzanie klucza API
        self.api_key_label = QtWidgets.QLabel("Klucz API YouTube Data v3:", self)
        self.api_key_label.setStyleSheet('font-weight: bold; font-size: 20px; color: #555555;')
        self.api_key_input = QtWidgets.QLineEdit(self)
        self.api_key_input.setFixedHeight(50)
        if 'api_key' in self.settings:
            self.api_key_input.setText(self.settings['api_key'])
        self.save_api_key_button = QtWidgets.QPushButton("Zapisz", self)
        self.save_api_key_button.setFixedHeight(50)
        self.save_api_key_button.setFixedWidth(100)
        self.save_api_key_button.clicked.connect(self.save_api_key)

        # Wprowadzanie URL kanału
        self.channel_url_label = QtWidgets.QLabel("URL kanału YouTube:", self)
        self.channel_url_label.setStyleSheet('font-weight: bold; font-size: 20px; color: #555555;')
        self.channel_url_input = QtWidgets.QLineEdit(self)
        self.channel_url_input.setFixedHeight(50)
        if 'channel_url' in self.settings:
            self.channel_url_input.setText(self.settings['channel_url'])
        self.fetch_channel_button = QtWidgets.QPushButton("Wczytaj", self)
        self.fetch_channel_button.setFixedHeight(50)
        self.fetch_channel_button.setFixedWidth(100)
        self.fetch_channel_button.clicked.connect(self.fetch_channel_info)

        # Informacje o kanale
        self.channel_info_widget = QtWidgets.QWidget(self)
        self.channel_info_layout = QtWidgets.QVBoxLayout(self.channel_info_widget)
        self.channel_thumbnail_label = QtWidgets.QLabel(self)
        self.channel_thumbnail_label.setFixedSize(100, 100)
        self.channel_thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        self.channel_title_label = QtWidgets.QLabel("", self)
        self.channel_title_label.setStyleSheet('font-weight: bold; font-size: 22px; color: #333333;')
        self.channel_details_label = QtWidgets.QLabel("", self)
        self.channel_details_label.setStyleSheet('font-size: 18px; color: #777777;')

        self.channel_info_layout.addWidget(self.channel_thumbnail_label, alignment=QtCore.Qt.AlignCenter)
        self.channel_info_layout.addWidget(self.channel_title_label, alignment=QtCore.Qt.AlignCenter)
        self.channel_info_layout.addWidget(self.channel_details_label, alignment=QtCore.Qt.AlignCenter)

        # Wybór katalogu do zapisu transkrypcji
        self.output_dir_label = QtWidgets.QLabel("Katalog do zapisu transkrypcji:", self)
        self.output_dir_label.setStyleSheet('font-weight: bold; font-size: 20px; color: #555555;')
        self.output_dir_input = QtWidgets.QLineEdit(self)
        self.output_dir_input.setFixedHeight(50)
        self.output_dir_input.setText("transcriptions")
        self.output_dir_button = QtWidgets.QPushButton("Wybierz", self)
        self.output_dir_button.setFixedHeight(50)
        self.output_dir_button.setFixedWidth(100)
        self.output_dir_button.clicked.connect(self.select_output_directory)

        # Tekst statusu
        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setStyleSheet('font-size: 18px;')

        # Widok listy wideo (QListWidget zamiast QTextEdit)
        self.video_list_widget = QtWidgets.QListWidget(self)
        self.video_list_widget.setFixedHeight(400)
        self.video_list_widget.setStyleSheet('font-size: 20px;')

        # Przyciski do pobierania filmów i transkrypcji
        self.fetch_videos_button = QtWidgets.QPushButton("Pobierz listę filmów", self)
        self.fetch_videos_button.setFixedWidth(200)
        self.fetch_videos_button.setFixedHeight(50)
        self.fetch_videos_button.clicked.connect(self.fetch_videos)

        # Dodaj przyciski do eksportu do plików TXT i JSON
        self.export_txt_button = QtWidgets.QPushButton("Zrzuć transkrypcje do plików .txt", self)
        self.export_txt_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.export_txt_button.setFixedHeight(50)
        self.export_txt_button.setEnabled(True)
        self.export_txt_button.clicked.connect(self.export_to_txt)

        self.export_json_button = QtWidgets.QPushButton("Zrzuć transkrypcje do pliku .json", self)
        self.export_json_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.export_json_button.setFixedHeight(50)
        self.export_json_button.setEnabled(True)
        self.export_json_button.clicked.connect(self.export_to_json)

        # Layout
        form_layout = QtWidgets.QGridLayout()

        form_layout.addWidget(self.api_key_label, 0, 0)
        form_layout.addWidget(self.api_key_input, 0, 1)
        form_layout.addWidget(self.save_api_key_button, 0, 2)

        form_layout.addWidget(self.channel_url_label, 1, 0)
        form_layout.addWidget(self.channel_url_input, 1, 1)
        form_layout.addWidget(self.fetch_channel_button, 1, 2)
        form_layout.addWidget(self.channel_info_widget, 2, 0, 1, 3)

        form_layout.addWidget(self.output_dir_label, 3, 0)
        form_layout.addWidget(self.output_dir_input, 3, 1)
        form_layout.addWidget(self.output_dir_button, 3, 2)

        form_layout.addWidget(self.fetch_videos_button, 4, 0)
        form_layout.addWidget(self.video_list_widget, 5, 0, 1, 3)
        form_layout.addWidget(self.export_txt_button, 6, 0, 1, 3)
        form_layout.addWidget(self.export_json_button, 7, 0, 1, 3)
        form_layout.addWidget(self.status_label, 8, 0, 1, 3)

        self.setLayout(form_layout)

    def load_stylesheet(self):
        return """
            QWidget {
                background-color: #f0f0f0;
                color: #000000;
                font-family: 'Segoe UI', sans-serif; font-size: 20px;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                color: #000000;
                padding: 10px;
                font-size: 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:disabled {
                background-color: #dcdcdc;
                color: #aaaaaa;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                font-size: 20px;
                border-radius: 5px;
            }
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                font-size: 20px;
                border-radius: 5px;
            }
            QLabel {
                color: #000000;
                font-size: 20px;
            }
        """

    def save_api_key(self):
        # Zapisz klucz API
        api_key = self.api_key_input.text()
        if api_key:
            try:
                self.youtube_client = build("youtube", "v3", developerKey=api_key)
                self.status_label.setText("🔑 Klucz API zapisano pomyślnie.")
                self.api_key_input.setStyleSheet("background-color: #ccffcc; border: 1px solid #28a745;")  # Zielony po zapisaniu klucza API

                # Save settings to file
                self.settings['api_key'] = api_key
                self.save_settings()
            except Exception as e:
                self.status_label.setText(f"🔐 Błąd zapisu klucza API: {e}")
                self.api_key_input.setStyleSheet("background-color: #ffcccc; border: 1px solid #dc3545;")  # Czerwony, jeśli wystąpił błąd
                self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')

    def fetch_channel_info(self):
        # Pobierz ID kanału YouTube na podstawie URL
        channel_url = self.channel_url_input.text()
        if channel_url:
            # Save settings to file
            self.settings['channel_url'] = channel_url
            self.save_settings()

        if not self.youtube_client:
            self.status_label.setText("🔐 Klucz API nie został zapisany.")
            self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')
            return

        try:
            self.channel_id = self.get_channel_id_from_url(channel_url)
            self.fetch_channel_statistics()
            self.update_channel_info()
        except ValueError as e:
            self.status_label.setText(str(e))
            self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')
        except Exception as e:
            self.status_label.setText(f"Błąd: {e}")
            self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')

    def load_settings(self):
        # Wczytaj ustawienia z pliku settings.json
        if os.path.exists("settings.json"):
            with open("settings.json", "r", encoding="utf-8") as file:
                return json.load(file)
        return {}

    def save_settings(self):
        # Zapisz ustawienia do pliku settings.json
        with open("settings.json", "w", encoding="utf-8") as file:
            json.dump(self.settings, file, indent=4, ensure_ascii=False)

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

    def fetch_channel_statistics(self):
        # Pobierz statystyki kanału, w tym liczbę subskrybentów
        if not self.youtube_client or not self.channel_id:
            return
        try:
            request = self.youtube_client.channels().list(
                part="snippet,statistics",
                id=self.channel_id
            )
            response = request.execute()
            if "items" in response and len(response["items"]) > 0:
                channel_info = response["items"][0]
                self.channel_title = channel_info["snippet"]["title"]
                self.subscribers = channel_info["statistics"].get("subscriberCount", "N/A")
                self.video_count = channel_info["statistics"].get("videoCount", "0")
                self.channel_thumbnail_url = channel_info["snippet"]["thumbnails"]["default"]["url"]
        except Exception as e:
            self.status_label.setText(f"Błąd pobierania statystyk kanału: {e}")
            self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')

    def update_channel_info(self):
        # Aktualizuj informacje o kanale w interfejsie użytkownika
        if self.channel_thumbnail_url:
            image = QtGui.QImage()
            image.loadFromData(self.fetch_image_data(self.channel_thumbnail_url))
            pixmap = QtGui.QPixmap(image)

            # Create a rounded version of the thumbnail image
            rounded_pixmap = QtGui.QPixmap(100, 100)
            rounded_pixmap.fill(QtCore.Qt.transparent)

            painter = QtGui.QPainter(rounded_pixmap)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            path = QtGui.QPainterPath()
            path.addEllipse(0, 0, 100, 100)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, 100, 100, pixmap)
            painter.end()

            self.channel_thumbnail_label.setPixmap(rounded_pixmap)
        self.channel_title_label.setText(self.channel_title)
        self.channel_details_label.setText(
            f"ID Kanału: {self.channel_id}\nLiczba subskrybentów: {self.subscribers}\nLiczba filmów: {self.video_count}"
        )

    def fetch_image_data(self, url):
        # Pobierz dane obrazu z URL
        response = requests.get(url)
        if response.status_code == 200:
            return response.content
        return b""

    def select_output_directory(self):
        # Wybierz katalog do zapisu transkrypcji
        options = QtWidgets.QFileDialog.Options()
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Wybierz katalog do zapisu transkrypcji", "",
                                                               options)
        if directory:
            self.output_dir_input.setText(directory)
            self.status_label.setText(f"Wybrano katalog: {directory}")

    def fetch_videos(self):
        # Pobierz listę wideo z kanału
        if not self.youtube_client or not self.channel_id:
            self.status_label.setText("🔐 Klucz API lub ID kanału nie zostało zapisane.")
            self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')
            return

        self.status_label.setText("Pobieranie listy wideo...")
        self.video_data = []

        # Ustawienia początkowe do stronicowania
        page_token = None
        total_videos = int(self.video_count) if self.video_count.isdigit() else 0
        videos_processed = 0

        while True:
            request = self.youtube_client.search().list(
                part="id,snippet",
                channelId=self.channel_id,
                maxResults=50,
                type="video",
                pageToken=page_token
            )
            response = request.execute()

            items = response.get("items", [])
            for item in items:
                video_id = item["id"].get("videoId")
                if video_id:
                    title = item["snippet"]["title"]
                    publish_date = item["snippet"]["publishedAt"]
                    publish_date_formatted = datetime.strptime(publish_date, "%Y-%m-%dT%H:%M:%SZ").strftime("%d-%m-%Y %H:%M")
                    transcript_available = "Tak" if self.is_transcript_available(video_id) else "Nie"

                    # Dodaj element bezpośrednio do widoku listy
                    duration = self.get_video_duration(video_id)
                    list_item = QtWidgets.QListWidgetItem(f"{publish_date_formatted} - {title} ({duration}) - Transkrypcja: {transcript_available}")
                    self.video_list_widget.addItem(list_item)

                    # Aktualizuj liczbę przetworzonych filmów
                    videos_processed += 1
                    self.status_label.setText(f"Pobrano {videos_processed} z {total_videos} filmów")

                    # Przetwarzanie wydarzeń Qt, aby interfejs był responsywny
                    QtCore.QCoreApplication.processEvents()

            # Sprawdź, czy jest następna strona wyników
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        self.status_label.setText("Pobieranie zakończone.")

    def is_transcript_available(self, video_id):
        # Sprawdź, czy transkrypcja jest dostępna dla wideo
        try:
            YouTubeTranscriptApi.get_transcript(video_id, languages=['pl'])
            return True
        except (TranscriptsDisabled, NoTranscriptFound):
            return False

    def export_to_txt(self):
        # Eksportuj transkrypcje do pojedynczych plików TXT
        output_dir = self.output_dir_input.text()
        if not output_dir:
            self.status_label.setText("Wybierz katalog do zapisu plików TXT.")
            self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')
            return

        for video_id, title, _, _ in self.video_data:
            transcript = self.transcriptions.get(video_id, None)
            if transcript is None:
                self.status_label.setText(f"Pobieranie transkrypcji dla wideo: {title}")
                QtCore.QCoreApplication.processEvents()
                transcript = self.download_transcription_synchronously(video_id)
            if transcript is not None:
                sanitized_title = re.sub(r'[/*?"<>|:]', "", title)
                output_filename = f"{sanitized_title}.txt"
                output_path = os.path.join(output_dir, output_filename)
                with open(output_path, "w", encoding="utf-8") as file:
                    file.write(transcript)
        self.status_label.setText(
            f"Transkrypcje zapisane w plikach TXT w katalogu: {output_dir} (sprawdź czy katalog istnieje i ma prawa do zapisu)")

    def export_to_json(self):
        # Eksportuj transkrypcje do pliku JSON
        output_dir = self.output_dir_input.text()
        if not output_dir:
            self.status_label.setText("Wybierz katalog do zapisu pliku JSON.")
            self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')
            return

        channel_data = {
            "channel_id": self.channel_id,
            "channel_title": self.channel_title,
            "channel_url": f"https://www.youtube.com/channel/{self.channel_id}",
            "subscribers": self.subscribers,
            "total_videos": len(self.video_data),
            "videos": []
        }

        for video_id, title, publish_date, transcript_available in self.video_data:
            transcript = self.transcriptions.get(video_id)
            if not transcript:
                # Jeśli transkrypcja nie była jeszcze pobrana, pobierz ją teraz
                self.status_label.setText(f"Pobieranie transkrypcji dla wideo: {title}")
                QtCore.QCoreApplication.processEvents()
                transcript = self.download_transcription_synchronously(video_id)
            duration = self.get_video_duration(video_id)
            channel_data["videos"].append({
                "video_id": video_id,
                "title": title,
                "publish_date": publish_date,
                "duration": duration,
                "transcript_available": transcript_available,
                "transcript": transcript
            })

        output_path = os.path.join(output_dir, "channel_transcriptions.json")
        with open(output_path, "w", encoding="utf-8") as json_file:
            json.dump(channel_data, json_file, indent=4, ensure_ascii=False)

        self.status_label.setText(f"Transkrypcje zapisane w pliku: {output_path}")

    def download_transcription_synchronously(self, video_id):
        # Pobierz transkrypcję dla pojedynczego wideo w trybie synchronicznym
        try:
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcripts.find_transcript(['pl'])
            transcript_text = "\n".join([entry["text"] for entry in transcript.fetch()])
            self.transcriptions[video_id] = transcript_text  # Store transcription in memory
            return transcript_text
        except Exception as e:
            self.status_label.setText(f"Błąd pobierania transkrypcji: {e}")
            self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')
            return ""

    def get_video_duration(self, video_id):
        # Pobierz długość filmu na podstawie jego ID
        try:
            request = self.youtube_client.videos().list(
                part="contentDetails",
                id=video_id
            )
            response = request.execute()
            if "items" in response and len(response["items"]) > 0:
                duration = response["items"][0]["contentDetails"]["duration"]
                return self.parse_duration(duration)
        except Exception as e:
            return "00:00"

    def parse_duration(self, duration):
        # Parsuj czas trwania w formacie ISO 8601 do formatu czytelnego dla człowieka (HH:MM:SS)
        hours = minutes = seconds = 0
        duration = duration.replace("PT", "")
        if "H" in duration:
            hours = int(duration.split("H")[0])
            duration = duration.split("H")[1]
        if "M" in duration:
            minutes = int(duration.split("M")[0])
            duration = duration.split("M")[1]
        if "S" in duration:
            seconds = int(duration.split("S")[0])
        return f"{hours:02}:{minutes:02}:{seconds:02}"


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = YouTubeTranscriptApp()
    window.show()
    sys.exit(app.exec_())