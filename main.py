import os
import re
import googleapiclient.discovery
from youtube_transcript_api import YouTubeTranscriptApi
import flet as ft
import asyncio


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
            return response["items"][0]["snippet"]["channelId"]
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


# Pobierz informacje o kanale
def get_channel_details(youtube_client, channel_id):
    request = youtube_client.channels().list(
        part="snippet,statistics",
        id=channel_id
    )
    response = request.execute()
    if "items" in response and len(response["items"]) > 0:
        channel_info = response["items"][0]
        title = channel_info["snippet"]["title"]
        subscriber_count = channel_info["statistics"].get("subscriberCount", "Brak danych")
        video_count = channel_info["statistics"].get("videoCount", "Brak danych")
        avatar_url = channel_info["snippet"].get("thumbnails", {}).get("default", {}).get("url", None)
        return title, subscriber_count, video_count, avatar_url
    raise ValueError("Nie udało się pobrać informacji o kanale.")


# Pobierz wszystkie ID wideo oraz tytuły z kanału
def get_channel_video_ids_and_titles(youtube_client, channel_id, status_text, video_list_view):
    video_data = []
    request = youtube_client.search().list(
        part="id,snippet",
        channelId=channel_id,
        maxResults=50,
        type="video"
    )

    while request:
        status_text.value = "Pobieranie listy wideo..."
        status_text.update()
        response = request.execute()
        for item in response.get("items", []):
            video_id = item["id"].get("videoId")
            if video_id:
                title = item["snippet"]["title"]
                publish_date = item["snippet"]["publishedAt"][:10]  # Wyodrębnij tylko część daty (YYYY-MM-DD)
                video_data.append((video_id, title, publish_date))
                # Aktualizuj listę filmów na bieżąco
                video_item = ft.Row(
                    controls=[
                        ft.Text(f"{title} ({publish_date})"),
                        ft.Text(f"Transkrypcja: Nieznana"),
                        ft.ElevatedButton(text="Pobierz",
                                          on_click=lambda _e, v_id=video_id: on_download_transcription_click(v_id,
                                                                                                             output_dir_input,
                                                                                                             status_text))
                    ]
                )
                video_list_view.controls.append(video_item)
                video_list_view.update()
        request = youtube_client.search().list_next(request, response)

    status_text.value = "Pobieranie zakończone."
    status_text.update()
    return video_data


# Pobierz transkrypcję dla wideo
def get_video_transcription(video_id):
    try:
        # Preferuj transkrypcję w języku polskim, jeśli jest dostępna, w przeciwnym razie wybierz dowolną
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None
        try:
            transcript = transcripts.find_transcript(['pl'])
        except Exception:
            try:
                transcript = transcripts.find_generated_transcript(['pl'])
            except Exception:
                try:
                    transcript = transcripts.find_transcript(
                        [lang for lang in transcripts._manually_created_transcripts.keys()])
                except Exception:
                    transcript = transcripts.find_transcript(
                        [lang for lang in transcripts._generated_transcripts.keys()])

        if transcript is None:
            raise Exception("Brak dostępnej transkrypcji")

        transcript_text = "\n".join([entry["text"] for entry in transcript.fetch()])
        is_auto_generated = transcript.is_generated
        return transcript_text, is_auto_generated
    except Exception as e:
        print(f"Nie udało się pobrać transkrypcji dla wideo {video_id}: {e}")
        return None, False


# Funkcja pobierania transkrypcji
def on_download_transcription_click(video_id, output_dir_input, status_text):
    output_dir = output_dir_input.value
    status_text.value = f"Pobieranie transkrypcji dla wideo ID: {video_id}"
    status_text.update()
    transcription, is_auto_generated = get_video_transcription(video_id)
    if transcription:
        sanitized_title = re.sub(r'[/*?"<>|:]', "", video_id)  # Użyj ID wideo, aby zapewnić unikalną nazwę
        auto_tag = " [auto]" if is_auto_generated else ""
        output_filename = f"{sanitized_title}{auto_tag}.txt"
        output_path = os.path.join(output_dir, output_filename)
        try:
            with open(output_path, "w", encoding="utf-8") as file:
                file.write(transcription)
            status_text.value = f"Transkrypcja zapisana: {output_filename}"
            status_text.update()
        except OSError as e:
            status_text.value = f"Błąd zapisu transkrypcji: {e}"
            status_text.update()
    else:
        status_text.value = f"Transkrypcja niedostępna dla wideo ID: {video_id}"
        status_text.update()


# Interfejs użytkownika z Flet
def main(page: ft.Page):
    page.title = "YouTubeText - Pobieranie transkrypcji z YouTube"
    page.vertical_alignment = ft.MainAxisAlignment.START

    api_key_input = ft.TextField(label="Klucz API YouTube Data v3", width=400)
    save_api_key_button = ft.ElevatedButton(text="Zapisz", on_click=lambda _e: on_save_api_key_click())
    channel_url_input = ft.TextField(label="URL kanału YouTube", width=400)
    fetch_channel_id_button = ft.ElevatedButton(text="Pobierz ID Kanału",
                                                on_click=lambda _e: on_fetch_channel_id_click())
    channel_id_text = ft.Text(value="", width=400)
    channel_details_text = ft.Text(value="", width=600)
    video_list_view = ft.ListView(expand=True, height=400)
    output_dir_input = ft.TextField(label="Katalog do zapisu transkrypcji", value="transcriptions", width=400)
    status_text = ft.Text(value="", width=600)

    youtube_client = None
    channel_id = None
    video_data = []
    api_key = None

    def on_save_api_key_click():
        nonlocal api_key, youtube_client
        api_key = api_key_input.value
        api_key_input.disabled = True
        api_key_input.update()
        try:
            youtube_client = get_youtube_client(api_key)
            # Sprawdzenie poprawności klucza
            youtube_client.channels().list(part="id", id="UC_x5XG1OV2P6uZZ5FSM9Ttw").execute()
            status_text.value = "Zapisano klucz API."
            api_key_input.disabled = True
        except Exception as e:
            api_key_input.disabled = False
            status_text.value = f"Błąd klucza API: {e}"
        status_text.update()

    def on_fetch_channel_id_click():
        nonlocal channel_id
        if youtube_client is None:
            status_text.value = "Klucz API nie został zapisany."
            status_text.update()
            return
        channel_url = channel_url_input.value
        try:
            channel_id = get_channel_id_from_url(youtube_client, channel_url)
            channel_id_text.value = f"ID Kanału: {channel_id}"
            channel_id_text.update()
            title, subscriber_count, video_count, avatar_url = get_channel_details(youtube_client, channel_id)
            channel_details_text.value = f"Kanał: {title}, Subskrybenci: {subscriber_count}, Filmy: {video_count}"
            channel_details_text.update()
            if avatar_url:
                avatar_image = ft.Image(src=avatar_url, width=100, height=100)
                page.add(avatar_image)
            else:
                status_text.value = "Brak dostępnego avatara kanału."
            status_text.value = "Zapisano ID kanału."
        except ValueError as e:
            status_text.value = str(e)
        except Exception as e:
            status_text.value = f"Błąd: {e}"
        status_text.update()

    def on_fetch_videos_click(_e):
        nonlocal video_data
        if youtube_client and channel_id:
            video_list_view.controls.clear()
            video_list_view.update()
            video_data = get_channel_video_ids_and_titles(youtube_client, channel_id, status_text, video_list_view)

    def on_download_all_click(_e):
        output_dir = output_dir_input.value
        for video_id, title, _ in video_data:
            status_text.value = f"Pobieranie transkrypcji dla wideo: {title}"
            status_text.update()
            transcription, is_auto_generated = get_video_transcription(video_id)
            if transcription:
                sanitized_title = re.sub(r'[/*?"<>|:]', "", title)
                auto_tag = " [auto]" if is_auto_generated else ""
                output_filename = f"{sanitized_title}{auto_tag}.txt"
                output_path = os.path.join(output_dir, output_filename)
                try:
                    with open(output_path, "w", encoding="utf-8") as file:
                        file.write(transcription)
                    status_text.value = f"Transkrypcja zapisana: {output_filename}"
                    status_text.update()
                except OSError as e:
                    status_text.value = f"Błąd zapisu transkrypcji: {e}"
                    status_text.update()
            else:
                status_text.value = f"Transkrypcja niedostępna dla wideo: {title}"
                status_text.update()

    fetch_videos_button = ft.ElevatedButton(text="Pobierz listę filmów", on_click=on_fetch_videos_click)
    download_all_button = ft.ElevatedButton(text="Pobierz wszystkie dostępne transkrypcje",
                                            on_click=on_download_all_click)

    page.add(
        api_key_input,
        save_api_key_button,
        channel_url_input,
        fetch_channel_id_button,
        channel_id_text,
        channel_details_text,
        fetch_videos_button,
        video_list_view,
        download_all_button,
        output_dir_input,
        status_text
    )


asyncio.run(ft.app_async(target=main))
