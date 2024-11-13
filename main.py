import os
import re
import sys
import threading
import json
import sqlite3
from PyQt5 import QtWidgets, QtGui, QtCore
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi


class YouTubeTranscriptApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.youtube_client = None
        self.channel_id = None
        self.channel_title = ""
        self.subscribers = "0"
        self.video_data = []
        self.transcriptions = {}  # Store transcriptions in memory
        self.init_ui()
        self.init_db()

    def init_ui(self):
        # Inicjalizacja interfejsu użytkownika
        self.setWindowTitle("YouTubeText - Pobieranie transkrypcji z YouTube")
        self.setGeometry(100, 100, 900, 600)
        self.setStyleSheet(self.load_stylesheet())

        # Wprowadzanie klucza API
        self.api_key_label = QtWidgets.QLabel("Klucz API YouTube Data v3:", self)
        self.api_key_label.setStyleSheet('font-weight: bold; font-size: 20px; color: #555555;')
        self.api_key_input = QtWidgets.QLineEdit(self)
        self.api_key_input.setFixedHeight(50)
        self.save_api_key_button = QtWidgets.QPushButton("Zapisz", self)
        self.save_api_key_button.setFixedHeight(50)
        self.save_api_key_button.setFixedWidth(100)
        self.save_api_key_button.clicked.connect(self.save_api_key)

        # Wprowadzanie URL kanału
        self.channel_url_label = QtWidgets.QLabel("URL kanału YouTube:", self)
        self.channel_url_label.setStyleSheet('font-weight: bold; font-size: 20px; color: #555555;')
        self.channel_url_input = QtWidgets.QLineEdit(self)
        self.channel_url_input.setFixedHeight(50)
        self.fetch_channel_button = QtWidgets.QPushButton("Wczytaj", self)
        self.fetch_channel_button.setFixedHeight(50)
        self.fetch_channel_button.setFixedWidth(100)
        self.fetch_channel_button.clicked.connect(self.fetch_channel_info)
        self.channel_id_label = QtWidgets.QLabel("", self)
        self.channel_id_label.setStyleSheet('font-size: 18px; color: #777777;')

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

        # Widok listy wideo
        self.video_list_text = QtWidgets.QTextEdit(self)
        self.video_list_text.setReadOnly(True)
        self.video_list_text.setFixedHeight(200)

        # Przyciski do pobierania filmów i transkrypcji
        self.fetch_videos_button = QtWidgets.QPushButton("Pobierz listę filmów", self)
        self.fetch_videos_button.setFixedWidth(200)
        self.fetch_videos_button.setFixedHeight(50)
        self.fetch_videos_button.clicked.connect(lambda: threading.Thread(target=self.fetch_videos).start())

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
        form_layout.addWidget(self.channel_id_label, 2, 1, 1, 2)

        form_layout.addWidget(self.output_dir_label, 3, 0)
        form_layout.addWidget(self.output_dir_input, 3, 1)
        form_layout.addWidget(self.output_dir_button, 3, 2)

        form_layout.addWidget(self.fetch_videos_button, 4, 0, 1, 3)
        form_layout.addWidget(self.video_list_text, 5, 0, 1, 3)
        form_layout.addWidget(self.export_txt_button, 6, 0, 1, 3)
        form_layout.addWidget(self.export_json_button, 7, 0, 1, 3)
        form_layout.addWidget(self.status_label, 8, 0, 1, 3)

        self.setLayout(form_layout)

    def init_db(self):
        # Inicjalizacja bazy danych SQLite
        self.conn = sqlite3.connect("youtube_transcripts.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                publish_date TEXT,
                transcript TEXT
            )
        ''')
        self.conn.commit()

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
            QTextEdit {
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
                self.status_label.setText("🔑 Zapisano klucz API.")
            except Exception as e:
                self.status_label.setText(f"🔐 Błąd klucza API: {e}")

    def fetch_channel_info(self):
        # Pobierz ID kanału YouTube na podstawie URL
        if not self.youtube_client:
            self.status_label.setText("🔐 Klucz API nie został zapisany.")
            return

        channel_url = self.channel_url_input.text()
        try:
            self.channel_id = self.get_channel_id_from_url(channel_url)
            self.fetch_channel_statistics()
            self.channel_id_label.setText(f"ID Kanału: {self.channel_id}, Subskrybenci: {self.subscribers}")
        except ValueError as e:
            self.status_label.setText(str(e))
        except Exception as e:
            self.status_label.setText(f"Błąd: {e}")

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
        except Exception as e:
            self.status_label.setText(f"Błąd pobierania statystyk kanału: {e}")

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
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Wybierz katalog do zapisu transkrypcji", "",
                                                               options)
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
                publish_date = item["snippet"]["publishedAt"]  # Pobierz datę publikacji
                self.video_data.append((video_id, title, publish_date))
                # Zapisz do bazy danych
                self.cursor.execute('''
                    INSERT OR IGNORE INTO videos (video_id, title, publish_date)
                    VALUES (?, ?, ?)
                ''', (video_id, title, publish_date))
                # Pobierz transkrypcję
                threading.Thread(target=self.download_transcription, args=(video_id, title, self.output_dir_input.text())).start()

        self.conn.commit()

        self.video_list_text.clear()
        for video_id, title, publish_date in self.video_data:
            self.video_list_text.append(f"{title} (ID: {video_id}, Data: {publish_date})")

        # Aktywuj przyciski eksportu po pobraniu transkrypcji
        self.export_txt_button.setEnabled(True)
        self.export_json_button.setEnabled(True)

        self.status_label.setText("Pobieranie zakończone.")

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
            self.transcriptions[video_id] = transcript_text  # Store transcription in memory
            # Zapisz do bazy danych
            self.cursor.execute('''
                UPDATE videos SET transcript = ? WHERE video_id = ?
            ''', (transcript_text, video_id))
            self.conn.commit()
            self.status_label.setText(f"Transkrypcja zapisana: {output_filename}")
        except Exception as e:
            self.status_label.setText(f"Błąd pobierania transkrypcji: {e}")

    def export_to_txt(self):
        # Eksportuj transkrypcje do pojedynczych plików TXT
        output_dir = self.output_dir_input.text()
        if not output_dir:
            self.status_label.setText("Wybierz katalog do zapisu plików TXT.")
            return

        for video_id, title, publish_date in self.video_data:
            transcript = self.transcriptions.get(video_id)
            if transcript:
                sanitized_title = re.sub(r'[/*?"<>|:]', "", title)
                output_filename = f"{sanitized_title}.txt"
                output_path = os.path.join(output_dir, output_filename)
                with open(output_path, "w", encoding="utf-8") as file:
                    file.write(transcript)
        self.status_label.setText(f"Transkrypcje zapisane w plikach TXT w katalogu: {output_dir}")

    def export_to_json(self):
        # Eksportuj transkrypcje do pliku JSON
        output_dir = self.output_dir_input.text()
        if not output_dir:
            self.status_label.setText("Wybierz katalog do zapisu pliku JSON.")
            return

        channel_data = {
            "channel_id": self.channel_id,
            "channel_title": self.channel_title,
            "channel_url": f"https://www.youtube.com/channel/{self.channel_id}",
            "subscribers": self.subscribers,
            "total_videos": len(self.video_data),
            "videos": []
        }

        for video_id, title, publish_date in self.video_data:
            self.cursor.execute('''
                SELECT transcript FROM videos WHERE video_id = ?
            ''', (video_id,))
            transcript = self.cursor.fetchone()[0]
            duration = self.get_video_duration(video_id)  # Pobierz długość filmu
            channel_data["videos"].append({
                "video_id": video_id,
                "title": title,
                "publish_date": publish_date,
                "duration": duration,
                "transcript": transcript
            })

        output_path = os.path.join(output_dir, "channel_transcriptions.json")
        with open(output_path, "w", encoding="utf-8") as json_file:
            json.dump(channel_data, json_file, indent=4, ensure_ascii=False)

        self.status_label.setText(f"Transkrypcje zapisane w pliku: {output_path}")

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
