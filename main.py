import json
import os
import re
import sys
from datetime import datetime

import requests
from PyQt5 import QtWidgets, QtGui, QtCore
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from pytube import YouTube  # Dodano import pytube

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
        self.transcriptions = {}  # Przechowuj transkrypcje w pamięci

        # Wczytaj ustawienia
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

        # Widok listy wideo
        self.video_list_widget = QtWidgets.QListWidget(self)
        self.video_list_widget.setFixedHeight(400)
        self.video_list_widget.setStyleSheet('font-size: 20px;')
        self.video_list_widget.itemClicked.connect(self.on_video_item_clicked)

        # Przyciski do pobierania filmów
        self.fetch_videos_button = QtWidgets.QPushButton("Pobierz listę filmów", self)
        self.fetch_videos_button.setFixedWidth(200)
        self.fetch_videos_button.setFixedHeight(50)
        self.fetch_videos_button.clicked.connect(self.fetch_videos)

        # Pole do wyświetlania procentu pobierania filmów
        self.download_progress_label = QtWidgets.QLabel("0%", self)
        self.download_progress_label.setStyleSheet('font-size: 22px; color: #555555; font-weight: bold;')

        # Przyciski do eksportu
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
        form_layout.addWidget(self.download_progress_label, 4, 1, 1, 2)
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
                self.api_key_input.setStyleSheet(
                    "background-color: #ccffcc; border: 1px solid #28a745;")  # Zielony po zapisaniu klucza API

                # Zapisz ustawienia do pliku
                self.settings['api_key'] = api_key
                self.save_settings()
            except Exception as e:
                self.status_label.setText(f"🔐 Błąd zapisu klucza API: {e}")
                self.api_key_input.setStyleSheet(
                    "background-color: #ffcccc; border: 1px solid #dc3545;")  # Czerwony, jeśli wystąpił błąd
                self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')

    def fetch_channel_info(self):
        # Pobierz ID kanału YouTube na podstawie URL
        channel_url = self.channel_url_input.text()
        if channel_url:
            # Zapisz ustawienia do pliku
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

            # Stwórz zaokrąglony obraz miniaturki
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
        """
        Zaktualizowana metoda pobierania listy wideo, w tym informacje o dostępności napisów.
        """
        if not self.youtube_client or not self.channel_id:
            self.status_label.setText("🔐 Klucz API lub ID kanału nie zostało zapisane.")
            self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')
            return

        self.status_label.setText("Pobieranie listy wideo...")
        self.video_data = []
        self.video_list_widget.clear()  # Wyczyść listę przed dodaniem nowych elementów

        # Ustawienia początkowe do stronicowania
        page_token = None
        total_videos = int(self.video_count) if self.video_count.isdigit() else 0
        videos_processed = 0

        while True:
            try:
                request = self.youtube_client.search().list(
                    part="id,snippet",
                    channelId=self.channel_id,
                    maxResults=50,
                    type="video",
                    pageToken=page_token,
                    order="date"
                )
                response = request.execute()

                items = response.get("items", [])
                for item in items:
                    video_id = item["id"].get("videoId")
                    if video_id:
                        title = item["snippet"]["title"]
                        publish_date = item["snippet"]["publishedAt"]
                        publish_date_formatted = datetime.strptime(publish_date, "%Y-%m-%dT%H:%M:%SZ").strftime("%d.%m.%Y")

                        # Sprawdzenie, czy transkrypcja jest dostępna
                        transcript_available = "📄" if self.is_transcript_available(video_id) else "📒"

                        # Dodaj element bezpośrednio do widoku listy
                        duration = self.get_video_duration(video_id)
                        list_item = QtWidgets.QListWidgetItem(
                            f"{publish_date_formatted} - {title} ({duration}) {transcript_available}"
                        )
                        list_item.setData(QtCore.Qt.UserRole, (video_id, publish_date_formatted, title))
                        self.video_list_widget.addItem(list_item)

                        # Automatyczne przewijanie listy
                        self.video_list_widget.scrollToItem(list_item)

                        # Aktualizuj liczbę przetworzonych filmów
                        videos_processed += 1
                        percentage_completed = int((videos_processed / total_videos) * 100) if total_videos > 0 else 100
                        self.download_progress_label.setText(f"{percentage_completed}%")
                        self.status_label.setText(f"Pobrano {videos_processed} z {total_videos} filmów")

                        # Przetwarzanie wydarzeń Qt, aby interfejs był responsywny
                        QtCore.QCoreApplication.processEvents()

                # Sprawdź, czy jest następna strona wyników
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            except HttpError as e:
                self.status_label.setText(f"Błąd pobierania filmów: {e}")
                self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')
                break

        self.status_label.setText("Pobieranie zakończone.")
        self.download_progress_label.setText("100%")

    def is_transcript_available(self, video_id):
        try:
            # Spróbuj użyć YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            return True
        except Exception as e:
            print(f"YouTubeTranscriptApi nie może pobrać transkrypcji: {e}")
            # Spróbuj użyć pytube jako alternatywy
            try:
                yt = YouTube(f'https://www.youtube.com/watch?v={video_id}')
                captions = yt.captions
                if captions:
                    return True
                else:
                    return False
            except Exception as e:
                print(f"pytube nie może pobrać transkrypcji: {e}")
                return False

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

    def on_video_item_clicked(self, item):
        # Obsługuje kliknięcie elementu wideo, aby zapisać transkrypcję do pliku txt
        video_id, publish_date, title = item.data(QtCore.Qt.UserRole)
        if "📄" in item.text():  # Tylko jeśli transkrypcja jest dostępna
            output_dir = self.output_dir_input.text()
            suggested_filename = f"{publish_date} - {re.sub(r'[/*?\"<>|:]', '', title)}.txt"
            default_path = os.path.join(output_dir, suggested_filename)

            options = QtWidgets.QFileDialog.Options()
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Zapisz transkrypcję", default_path,
                                                                 "Pliki tekstowe (*.txt)", options=options)
            if file_path:
                transcript = self.transcriptions.get(video_id, None)
                if transcript is None:
                    self.status_label.setText(f"Pobieranie transkrypcji dla wideo...")
                    QtCore.QCoreApplication.processEvents()
                    transcript = self.download_transcription_synchronously(video_id)
                if transcript is not None:
                    with open(file_path, "w", encoding="utf-8") as file:
                        file.write(transcript)
                    self.status_label.setText(f"Transkrypcja zapisana do pliku: {file_path}")
                else:
                    self.status_label.setText(f"Błąd pobierania transkrypcji dla wideo: {item.text()}")
                    self.status_label.setStyleSheet('color: #dc3545; font-weight: bold;')

    def download_transcription_synchronously(self, video_id):
        # Pobierz transkrypcję za pomocą YouTubeTranscriptApi lub pytube
        transcript_text = None
        try:
            # Spróbuj użyć YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            # Spróbuj znaleźć transkrypcję ręcznie dodaną
            try:
                transcript = transcript_list.find_manually_created_transcript(['pl', 'en'])
            except NoTranscriptFound:
                # Jeśli nie znaleziono, spróbuj znaleźć transkrypcję automatycznie wygenerowaną
                transcript = transcript_list.find_generated_transcript(['pl', 'en'])
            # Pobierz dane transkrypcji
            transcript_data = transcript.fetch()
            # Konwertuj dane transkrypcji do tekstu
            transcript_text = '\n'.join([entry['text'] for entry in transcript_data])
        except Exception as e:
            print(f"YouTubeTranscriptApi nie może pobrać transkrypcji: {e}")
            # Spróbuj użyć pytube jako alternatywy
            try:
                yt = YouTube(f'https://www.youtube.com/watch?v={video_id}')
                captions = yt.captions
                if captions:
                    # Wybierz napisy w preferowanym języku
                    caption = captions.get_by_language_code('pl') or captions.get_by_language_code('en')
                    if caption:
                        # Generuj napisy w formacie SRT
                        srt_captions = caption.generate_srt_captions()
                        # Konwertuj SRT do czystego tekstu
                        transcript_text = self.srt_to_text(srt_captions)
                    else:
                        print("Napisy w wybranym języku nie są dostępne.")
                else:
                    print("Brak dostępnych napisów.")
            except Exception as e:
                print(f"pytube nie może pobrać transkrypcji: {e}")

        if transcript_text:
            # Zapisz transkrypcję w pamięci
            self.transcriptions[video_id] = transcript_text
            return transcript_text
        else:
            return None

    def srt_to_text(self, srt_captions):
        # Konwertuj napisy SRT do czystego tekstu
        import re
        lines = srt_captions.strip().split('\n')
        text_lines = []
        for line in lines:
            # Pomijaj numery sekwencji i znaczniki czasu
            if re.match(r'^\d+$', line) or re.match(r'^\d{2}:\d{2}:\d{2},\d{3}', line):
                continue
            else:
                text_lines.append(line.strip())
        # Połącz linie w jeden tekst
        transcript_text = ' '.join(text_lines)
        return transcript_text

    def export_to_txt(self):
        # Implementacja eksportu transkrypcji do plików TXT
        output_dir = self.output_dir_input.text()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        total_items = self.video_list_widget.count()
        for index in range(total_items):
            item = self.video_list_widget.item(index)
            video_id, publish_date, title = item.data(QtCore.Qt.UserRole)
            if "📄" in item.text():  # Tylko jeśli transkrypcja jest dostępna
                transcript = self.transcriptions.get(video_id, None)
                if transcript is None:
                    self.status_label.setText(f"Pobieranie transkrypcji dla wideo: {title}")
                    QtCore.QCoreApplication.processEvents()
                    transcript = self.download_transcription_synchronously(video_id)
                if transcript is not None:
                    filename = f"{publish_date} - {re.sub(r'[/*?\"<>|:]', '', title)}.txt"
                    file_path = os.path.join(output_dir, filename)
                    with open(file_path, "w", encoding="utf-8") as file:
                        file.write(transcript)
                    self.status_label.setText(f"Transkrypcja zapisana do pliku: {file_path}")
                    QtCore.QCoreApplication.processEvents()
        self.status_label.setText("Eksport transkrypcji do plików TXT zakończony.")

    def export_to_json(self):
        # Implementacja eksportu transkrypcji do pliku JSON
        output_dir = self.output_dir_input.text()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        json_data = {}
        total_items = self.video_list_widget.count()
        for index in range(total_items):
            item = self.video_list_widget.item(index)
            video_id, publish_date, title = item.data(QtCore.Qt.UserRole)
            if "📄" in item.text():  # Tylko jeśli transkrypcja jest dostępna
                transcript = self.transcriptions.get(video_id, None)
                if transcript is None:
                    self.status_label.setText(f"Pobieranie transkrypcji dla wideo: {title}")
                    QtCore.QCoreApplication.processEvents()
                    transcript = self.download_transcription_synchronously(video_id)
                if transcript is not None:
                    json_data[title] = {
                        "video_id": video_id,
                        "publish_date": publish_date,
                        "transcript": transcript
                    }
                    self.status_label.setText(f"Transkrypcja dla wideo {title} dodana do JSON.")
                    QtCore.QCoreApplication.processEvents()
        json_file_path = os.path.join(output_dir, "transcripts.json")
        with open(json_file_path, "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, indent=4, ensure_ascii=False)
        self.status_label.setText(f"Transkrypcje zapisane do pliku JSON: {json_file_path}")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = YouTubeTranscriptApp()
    window.show()
    sys.exit(app.exec_())
