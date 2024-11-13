import os
import re
import googleapiclient.discovery
import youtube_dl
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import requests


# Ustaw klienta API YouTube
def get_youtube_client(api_key):
    return googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)


# Pobierz ID kanału z linku
def get_channel_id_from_url(youtube_client, channel_url):
    if "channel/" in channel_url:
        # Jeśli URL zawiera ID kanału
        return channel_url.split("channel/")[1]
    elif "@" in channel_url:
        # Jeśli URL zawiera nazwę użytkownika (np. @nazwa)
        username = channel_url.split("@")[1]
        request = youtube_client.search().list(
            part="snippet",
            q=username,
            type="channel",
            maxResults=1
        )
        response = request.execute()
        if "items" in response and len(response["items"]) > 0:
            return response["items"][0]["id"]["channelId"]
    else:
        # Jeśli URL zawiera nazwę użytkownika w starym formacie
        request = youtube_client.channels().list(
            part="id",
            forUsername=channel_url.split("/")[-1]
        )
        response = request.execute()
        if "items" in response and len(response["items"]) > 0:
            return response["items"][0]["id"]
    raise ValueError("Nie udało się znaleźć ID kanału dla podanego URL.")


# Pobierz wszystkie ID wideo oraz tytuły z kanału
def get_channel_video_ids_and_titles(youtube_client, channel_id):
    video_data = []
    request = youtube_client.search().list(
        part="id,snippet",
        channelId=channel_id,
        maxResults=50,
        type="video"
    )

    while request:
        response = request.execute()
        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            publish_date = item["snippet"]["publishedAt"][:10]  # Wyodrębnij tylko część daty (YYYY-MM-DD)
            video_data.append((video_id, title, publish_date))
        request = youtube_client.search().list_next(request, response)

    return video_data


# Pobierz transkrypcję dla wideo
def get_video_transcription(video_id):
    try:
        # Preferuj transkrypcję w języku polskim, jeśli jest dostępna, w przeciwnym razie wybierz dowolną
        transcript = None
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        if "pl" in transcripts._manually_created_transcripts:
            transcript = transcripts.find_manually_created_transcript(["pl"])
        elif "pl" in transcripts._generated_transcripts:
            transcript = transcripts.find_generated_transcript(["pl"])
        elif transcripts._manually_created_transcripts:
            transcript = transcripts.find_transcript(transcripts._manually_created_transcripts.keys())
        elif transcripts._generated_transcripts:
            transcript = transcripts.find_transcript(transcripts._generated_transcripts.keys())

        if transcript is None:
            raise Exception("Brak dostępnej transkrypcji")

        transcript_text = "\n".join([entry["text"] for entry in transcript.fetch()])
        is_auto_generated = transcript.is_generated
        return transcript_text, is_auto_generated
    except Exception as e:
        print(f"Nie udało się pobrać transkrypcji dla wideo {video_id}: {e}")
        return None, False


# Główna funkcja do pobierania transkrypcji
def download_transcriptions(api_key, channel_url, output_dir):
    # Upewnij się, że katalog wyjściowy oraz podkatalog 'transkrypcje' istnieją
    transcriptions_dir = os.path.join(output_dir, 'transkrypcje')
    if not os.path.exists(transcriptions_dir):
        os.makedirs(transcriptions_dir)

    # Pobierz klienta YouTube oraz ID kanału
    youtube_client = get_youtube_client(api_key)
    channel_id = get_channel_id_from_url(youtube_client, channel_url)

    # Pobierz dane wideo
    video_data = get_channel_video_ids_and_titles(youtube_client, channel_id)

    # Iteruj przez dane wideo, aby pobrać transkrypcje
    for video_id, title, publish_date in video_data:
        print(f"Analizowanie wideo: {title} (ID: {video_id})")
        transcription, is_auto_generated = get_video_transcription(video_id)
        if transcription:
            # Usuń nieprawidłowe znaki z tytułu, aby stworzyć prawidłową nazwę pliku
            sanitized_title = re.sub(r'[\/*?"<>|:]', "", title)  # Usuń nieprawidłowe znaki
            sanitized_title = "_".join(sanitized_title.split())  # Zamień spacje na podkreślenia
            auto_tag = " [auto]" if is_auto_generated else ""
            output_filename = f"{sanitized_title} ({publish_date}){auto_tag}.txt"
            output_path = os.path.join(transcriptions_dir, output_filename)
            try:
                with open(output_path, "w", encoding="utf-8") as file:
                    file.write(transcription)
                print(f"Transkrypcja zapisana dla wideo {video_id}: {output_filename}")
            except OSError as e:
                print(f"Błąd zapisu transkrypcji dla wideo {video_id}: {e}")
        else:
            print(f"Pominięto wideo {video_id} - brak dostępnej transkrypcji lub wystąpił błąd.")


if __name__ == "__main__":
    API_KEY = input("Podaj klucz API YouTube Data v3: ")  # Zapytaj o klucz API YouTube Data v3
    CHANNEL_URL = input("Podaj URL kanału YouTube: ")  # Zapytaj o URL kanału YouTube
    OUTPUT_DIR = "transcriptions"  # Katalog do zapisu transkrypcji

    download_transcriptions(API_KEY, CHANNEL_URL, OUTPUT_DIR)
