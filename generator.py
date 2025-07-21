import requests
import json
import gzip
import os
import time
from io import BytesIO
from cloudscraper import CloudScraper
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Live channels token
KABLO_BEARER_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbnYiOiJMSVZFIiwiaXBiIjoiMCIsImNnZCI6IjA5M2Q3MjBhLTUwMmMtNDFlZC1hODBmLTJiODE2OTg0ZmI5NSIsImNzaCI6IlRSS1NUIiwiZGN0IjoiM0VGNzUiLCJkaSI6ImE2OTliODNmLTgyNmItNGQ5OS05MzYxLWM4YTMxMzIxOGQ0NiIsInNnZCI6Ijg5NzQxZmVjLTFkMzMtNGMwMC1hZmNkLTNmZGFmZTBiNmEyZCIsInNwZ2QiOiIxNTJiZDUzOS02MjIwLTQ0MjctYTkxNS1iZjRiZDA2OGQ3ZTgiLCJpY2giOiIwIiwiaWRtIjoiMCIsImlhIjoiOjpmZmZmOjEwLjAuMC4yMDYiLCJhcHYiOiIxLjAuMCIsImFibiI6IjEwMDAiLCJuYmYiOjE3NDUxNTI4MjUsImV4cCI6MTc0NTE1Mjg4NSwiaWF0IjoxNzQ1MTUyODI1fQ.OSlafRMxef4EjHG5t6TqfAQC7y05IiQjwwgf6yMUS9E"

# VOD token
VOD_BEARER_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbnYiOiJMSVZFIiwiaXBiIjoiMCIsImNnZCI6IjA5M2Q3MjBhLTUwMmMtNDFlZC1hODBmLTJiODE2OTg0ZmI5NSIsImNzaCI6IlRSS1NUIiwiZGN0IjoiM0VGNzUiLCJkaSI6IjMwYTM5YzllLWE4ZDYtNGEwMC05NDBmLTFjMTE4NDgzZDcxMiIsInNnZCI6ImJkNmUyNmY5LWJkMzYtNDE2ZC05YWQzLTYzNjhlNGZkYTMyMiIsInNwZ2QiOiJjYjZmZGMwMi1iOGJlLTQ3MTYtYTZjYi1iZTEyYTg4YjdmMDkiLCJpY2giOiIwIiwiaWRtIjoiMCIsImlhIjoiOjpmZmZmOjEwLjAuMC4yMDYiLCJhcHYiOiIxLjAuMCIsImFibiI6IjEwMDAiLCJuYmYiOjE3NTE3MDMxODQsImV4cCI6MTc1MTcwMzI0NCwiaWF0IjoxNzUxNzAzMTg0fQ.SGC_FfT7cU1RVM4E5rMYO2IsA4aYUoYq2SXl51-PZwM"

VOD_ID_FILE = "vod_ids.txt"

def format_datetime_for_xmltv(date_str):
    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
        return dt.strftime("%Y%m%d%H%M%S +0300")
    except:
        return ""

def create_epg_xml(kablo_data, output_file="kablo_epg.xml"):
    tv = ET.Element("tv")
    tv.set("source-info-url", "https://kablowebtv.com")
    tv.set("source-info-name", "Kablo TV")
    tv.set("generator-info-name", "Xtream Codes EPG Generator")
    
    if not kablo_data.get('IsSucceeded') or not kablo_data.get('Data', {}).get('AllChannels'):
        print("❌ Invalid Kablo TV data for EPG generation!")
        return False
    
    channels_data = kablo_data['Data']['AllChannels']
    processed_channels = set()
    program_count = 0
    
    for channel_data in channels_data:
        channel_uid = channel_data.get('UId')
        channel_name = channel_data.get('Name', 'Unknown Channel')
        channel_description = channel_data.get('Description', '')
        logo_url = channel_data.get('PrimaryLogoImageUrl', '')
        remote_number = channel_data.get('RemoteNumber', '')
        categories = channel_data.get('Categories', [])
        
        if not channel_uid:
            continue
            
        if categories and categories[0].get('Name') == "Bilgilendirme":
            continue
        
        if channel_uid not in processed_channels:
            channel_elem = ET.SubElement(tv, "channel")
            channel_elem.set("id", channel_uid)
            
            display_name = ET.SubElement(channel_elem, "display-name")
            display_name.text = channel_name
            
            if remote_number:
                display_name_num = ET.SubElement(channel_elem, "display-name")
                display_name_num.text = str(remote_number)
            
            if channel_description:
                desc_elem = ET.SubElement(channel_elem, "desc")
                desc_elem.set("lang", "tr")
                desc_elem.text = channel_description
            
            if logo_url:
                icon_elem = ET.SubElement(channel_elem, "icon")
                icon_elem.set("src", logo_url)
            
            processed_channels.add(channel_uid)
        
        epgs = channel_data.get('Epgs', [])
        
        for epg in epgs:
            if not epg.get('StartDateTime') or not epg.get('EndDateTime'):
                continue
                
            programme = ET.SubElement(tv, "programme")
            programme.set("channel", channel_uid)
            programme.set("start", format_datetime_for_xmltv(epg.get('StartDateTime')))
            programme.set("stop", format_datetime_for_xmltv(epg.get('EndDateTime')))
            
            title = ET.SubElement(programme, "title")
            title.set("lang", "tr")
            title.text = epg.get('Title', 'Unknown Program')
            
            description = epg.get('ShortDescription', '')
            if description and description != "Kablo TV platformundaki kanallardan seçmeler...":
                desc = ET.SubElement(programme, "desc")
                desc.set("lang", "tr")
                desc.text = description
            
            genres = epg.get('Genres', [])
            for genre in genres:
                if isinstance(genre, dict) and genre.get('Name'):
                    category = ET.SubElement(programme, "category")
                    category.set("lang", "tr")
                    category.text = genre['Name']
            
            program_count += 1
    
    rough_string = ET.tostring(tv, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")
    
    lines = [line for line in pretty_xml.split('\n') if line.strip()]
    lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    lines.insert(1, '<!DOCTYPE tv SYSTEM "xmltv.dtd">')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"✅ EPG XML created: {output_file}")
    print(f"📺 Channels: {len(processed_channels)}")
    print(f"📋 Programs: {program_count}")
    
    return True

def get_kablo_data():
    url = "https://core-api.kablowebtv.com/api/channels"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://tvheryerde.com",
        "Origin": "https://tvheryerde.com",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Accept-Encoding": "gzip",
        "Authorization": KABLO_BEARER_TOKEN
    }
    
    try:
        print("📡 Kablo TV API'den veri alınıyor...")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        try:
            with gzip.GzipFile(fileobj=BytesIO(response.content)) as gz:
                content = gz.read().decode('utf-8')
        except:
            content = response.content.decode('utf-8')
        
        data = json.loads(content)
        
        if not data.get('IsSucceeded') or not data.get('Data', {}).get('AllChannels'):
            print("❌ Kablo TV API'den geçerli veri alınamadı!")
            return None
        
        channels = data['Data']['AllChannels']
        print(f"✅ Kablo TV: {len(channels)} kanal bulundu")
        return data
        
    except Exception as e:
        print(f"❌ Kablo TV Hatası: {e}")
        return None

def get_rectv_data():
    try:
        session = CloudScraper()
        response = session.post(
            url="https://firebaseremoteconfig.googleapis.com/v1/projects/791583031279/namespaces/firebase:fetch",
            headers={
                "X-Goog-Api-Key": "AIzaSyBbhpzG8Ecohu9yArfCO5tF13BQLhjLahc",
                "X-Android-Package": "com.rectv.shot",
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12)",
            },
            json={
                "appBuild": "81",
                "appInstanceId": "evON8ZdeSr-0wUYxf0qs68",
                "appId": "1:791583031279:android:1",
            }
        )
        
        main_url = response.json().get("entries", {}).get("api_url", "")
        base_domain = main_url.replace("/api/", "")
        print(f"🟢 RecTV domain alındı: {base_domain}")
        
        all_channels = []
        page = 0
        
        while True:
            url = f"{base_domain}/api/channel/by/filtres/0/0/{page}/4F5A9C3D9A86FA54EACEDDD635185/c3c5bd17-e37b-4b94-a944-8a3688a30452"
            response = requests.get(url)
            
            if response.status_code != 200:
                break
                
            data = response.json()
            if not data:
                break
                
            all_channels.extend(data)
            page += 1
        
        print(f"✅ RecTV: {len(all_channels)} kanal bulundu")
        return all_channels
        
    except Exception as e:
        print(f"❌ RecTV Hatası: {e}")
        return []

def export_live_channels(kablo_data, rectv_channels):
    print("💾 Exporting live channels for Xtream API...")
    
    export_data = {
        "categories": [
            {"category_id": 1, "category_name": "Spor", "parent_id": 0, "category_type": "live"},
            {"category_id": 2, "category_name": "Haber", "parent_id": 0, "category_type": "live"},
            {"category_id": 3, "category_name": "Ulusal", "parent_id": 0, "category_type": "live"},
            {"category_id": 4, "category_name": "Sinema", "parent_id": 0, "category_type": "live"},
            {"category_id": 5, "category_name": "Belgesel", "parent_id": 0, "category_type": "live"},
            {"category_id": 6, "category_name": "Müzik", "parent_id": 0, "category_type": "live"},
            {"category_id": 7, "category_name": "Genel", "parent_id": 0, "category_type": "live"},
            {"category_id": 8, "category_name": "Bilgilendirme", "parent_id": 0, "category_type": "live"},
            {"category_id": 9, "category_name": "Diğer", "parent_id": 0, "category_type": "live"}
        ],
        "streams": [],
        "last_updated": datetime.now().isoformat()
    }
    
    category_mapping = {
        "Spor": 1, "Haber": 2, "Ulusal": 3, "Sinema": 4,
        "Belgesel": 5, "Müzik": 6, "Genel": 7, "Bilgilendirme": 8, "Diğer": 9
    }
    
    stream_id = 1
    
    # Kablo TV channels
    if kablo_data and kablo_data.get('IsSucceeded'):
        channels = kablo_data['Data']['AllChannels']
        
        for channel in channels:
            name = channel.get('Name')
            stream_data = channel.get('StreamData', {})
            channel_uid = channel.get('UId')
            logo = channel.get('PrimaryLogoImageUrl', '')
            description = channel.get('Description', '')
            categories_list = channel.get('Categories', [])
            audio_tracks = channel.get('AudioTracks', [])
            remote_number = channel.get('RemoteNumber', '')
            
            # Get stream URL - prefer HLS, fallback to DASH, then Default
            stream_url = (stream_data.get('HlsStreamUrl') or 
                         stream_data.get('DashStreamUrl') or 
                         stream_data.get('DefaultStreamUrl'))
            
            if not name or not stream_url:
                continue
            
            group = categories_list[0].get('Name', 'Genel') if categories_list else 'Genel'
            category_id = category_mapping.get(group, 9)
            
            # Prepare audio tracks info
            audio_info = []
            for track in audio_tracks:
                track_info = {
                    "code": track.get('Code', ''),
                    "label": track.get('Label', ''),
                    "is_default": track.get('IsDefault', False)
                }
                audio_info.append(track_info)
            
            export_data["streams"].append({
                "stream_id": stream_id,
                "name": name,
                "stream_type": "live",
                "category_id": category_id,
                "stream_icon": logo,
                "stream_url": stream_url,
                "epg_channel_id": channel_uid or str(stream_id),
                "thumbnail": "",
                "description": description,
                "remote_number": remote_number,
                "audio_tracks": audio_info,
                "source": "kablo"
            })
            stream_id += 1
    
    # RecTV channels
    for channel in rectv_channels:
        title = channel.get("title", "Bilinmeyen")
        logo = channel.get("image", "")
        channel_id = str(channel.get("id", ""))
        categories_list = channel.get("categories", [])
        group_title = categories_list[0]["title"] if categories_list else "Diğer"
        
        category_id = category_mapping.get(group_title, 9)
        
        sources = channel.get("sources", [])
        for source in sources:
            url = source.get("url")
            if url and url.endswith(".m3u8"):
                quality = source.get("quality")
                quality_str = f" [{quality}]" if quality and quality.lower() != "none" else ""
                
                export_data["streams"].append({
                    "stream_id": stream_id,
                    "name": f"{title}{quality_str}",
                    "stream_type": "live",
                    "category_id": category_id,
                    "stream_icon": logo,
                    "stream_url": url,
                    "epg_channel_id": channel_id,
                    "thumbnail": "",
                    "description": "",
                    "remote_number": "",
                    "audio_tracks": [],
                    "source": "rectv"
                })
                stream_id += 1
    
    with open('live_channels_export.json', 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Live channels export: live_channels_export.json")
    print(f"📺 Live Streams: {len(export_data['streams'])}")

# ============================================================================
# VOD FUNCTIONS
# ============================================================================

def load_vod_ids(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"❌ {filename} bulunamadı. Lütfen dosyayı oluşturun.")
        return []

def get_film_detail(vod_id):
    url = "https://core-api.kablowebtv.com/api/vod/detail"
    headers = {
        "Authorization": VOD_BEARER_TOKEN,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://tvheryerde.com",
        "Origin": "https://tvheryerde.com"
    }
    
    try:
        res = requests.get(url, headers=headers, params={"VodUId": vod_id}, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("IsSucceeded") and data.get("Data"):
            return data["Data"][0]
    except Exception as e:
        print(f"❌ Hata: {vod_id} → {e}")
    return None

def export_vod_data(films):
    print("💾 Exporting VOD movies for Xtream API...")
    
    export_data = {
        "categories": [
            {"category_id": 101, "category_name": "Aksiyon Filmleri", "parent_id": 0, "category_type": "vod"},
            {"category_id": 102, "category_name": "Komedi Filmleri", "parent_id": 0, "category_type": "vod"},
            {"category_id": 103, "category_name": "Drama Filmleri", "parent_id": 0, "category_type": "vod"},
            {"category_id": 104, "category_name": "Korku Filmleri", "parent_id": 0, "category_type": "vod"},
            {"category_id": 105, "category_name": "Bilim Kurgu", "parent_id": 0, "category_type": "vod"},
            {"category_id": 106, "category_name": "Romantik Filmler", "parent_id": 0, "category_type": "vod"},
            {"category_id": 107, "category_name": "Gerilim Filmleri", "parent_id": 0, "category_type": "vod"},
            {"category_id": 108, "category_name": "Animasyon", "parent_id": 0, "category_type": "vod"},
            {"category_id": 109, "category_name": "Belgesel", "parent_id": 0, "category_type": "vod"},
            {"category_id": 110, "category_name": "Fantastik", "parent_id": 0, "category_type": "vod"},
            {"category_id": 111, "category_name": "Diğer Filmler", "parent_id": 0, "category_type": "vod"}
        ],
        "streams": [],
        "last_updated": datetime.now().isoformat()
    }
    
    genre_mapping = {
        "aksiyon": 101, "action": 101, "savaş": 101, "war": 101,
        "komedi": 102, "comedy": 102,
        "drama": 103, "dram": 103,
        "korku": 104, "horror": 104, "gerilim": 107, "thriller": 107,
        "bilim kurgu": 105, "sci-fi": 105, "science fiction": 105,
        "romantik": 106, "romance": 106, "aşk": 106,
        "animasyon": 108, "animation": 108, "çizgi film": 108,
        "belgesel": 109, "documentary": 109,
        "fantastik": 110, "fantasy": 110
    }
    
    stream_id = 1001
    
    for film in films:
        title = film.get("Title", "Bilinmeyen")
        uid = film.get("UId")
        description = film.get("Description", "")
        original_title = film.get("OriginalTitle", "")
        year = film.get("ReleaseYear", "")
        duration = film.get("Duration", 0)
        
        # Get poster (LISTING type is best for icons)
        logo = ""
        thumbnail = ""
        for poster in film.get("Posters", []):
            poster_type = poster.get("Type", "").upper()
            if poster_type == "LISTING":
                logo = poster.get("ImageUrl", "")
            elif poster_type == "PREVIEW":
                thumbnail = poster.get("ImageUrl", "")
        
        # Get stream URL - prefer DASH, fallback to HLS
        stream = film.get("StreamData", {})
        stream_url = stream.get("DashStreamUrl") or stream.get("HlsStreamUrl")
        
        # No DRM check - support everything
        if not stream_url:
            continue
        
        # Get audio tracks
        audio_tracks = []
        for track in film.get("AudioTracks", []):
            audio_tracks.append({
                "code": track.get("Code", ""),
                "label": track.get("Label", "")
            })
        
        # Get text tracks (subtitles)
        text_tracks = []
        for track in film.get("TextTracks", []):
            text_tracks.append({
                "code": track.get("Code", ""),
                "label": track.get("Label", "")
            })
        
        # Determine category from genres
        category_id = 111  # Default to "Diğer Filmler"
        genres = film.get("Genres", [])
        categories = film.get("Categories", [])
        
        # Check both Genres and Categories
        all_genre_names = []
        for genre in genres:
            if isinstance(genre, dict) and genre.get("Name"):
                all_genre_names.append(genre["Name"].lower())
        for category in categories:
            if isinstance(category, dict) and category.get("Name"):
                all_genre_names.append(category["Name"].lower())
        
        # Find matching category
        for genre_name in all_genre_names:
            for key, cat_id in genre_mapping.items():
                if key in genre_name:
                    category_id = cat_id
                    break
            if category_id != 111:
                break
        
        # Get cast info for additional metadata
        director = ""
        cast = []
        for person in film.get("Cast", []):
            if person.get("Type") == "DIRECTOR":
                director = person.get("Name", "")
            elif person.get("Type") == "ACTOR":
                cast.append(person.get("Name", ""))
        
        export_data["streams"].append({
            "stream_id": stream_id,
            "name": title,
            "stream_type": "movie",
            "category_id": category_id,
            "stream_icon": logo,
            "stream_url": stream_url,
            "description": description,
            "original_title": original_title,
            "year": year,
            "duration": duration,
            "director": director,
            "cast": ", ".join(cast[:5]),  # Limit to first 5 actors
            "audio_tracks": audio_tracks,
            "text_tracks": text_tracks,
            "thumbnail": thumbnail,
            "added": int(time.time()),
            "source": "kablo_vod"
        })
        stream_id += 1
    
    with open('vod_export.json', 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ VOD export: vod_export.json")
    print(f"🎬 VOD Streams: {len(export_data['streams'])}")

def main():
    print("🚀 Xtream Codes Data Generator")
    print("=" * 50)
    
    # Step 1: Live channels
    print("\n📡 Getting live channels...")
    kablo_data = get_kablo_data()
    rectv_channels = get_rectv_data()
    
    if kablo_data or rectv_channels:
        export_live_channels(kablo_data, rectv_channels)
    
    # Step 2: EPG
    print("\n📺 Creating EPG...")
    if kablo_data:
        create_epg_xml(kablo_data)
    
    # Step 3: VOD
    print("\n🎬 Getting VOD movies...")
    vod_ids = load_vod_ids(VOD_ID_FILE)
    
    if vod_ids:
        print(f"Processing {len(vod_ids)} movies...")
        collected = []
        
        for i, vid in enumerate(vod_ids):
            print(f"[{i+1}/{len(vod_ids)}] Getting: {vid}")
            detail = get_film_detail(vid)
            if detail and detail.get("StreamData", {}).get("DashStreamUrl"):
                collected.append(detail)
            time.sleep(0.5)
        
        if collected:
            export_vod_data(collected)
    
    print("\n🎉 Done! Files created:")
    if os.path.exists('live_channels_export.json'):
        print("📺 live_channels_export.json")
    if os.path.exists('vod_export.json'):
        print("🎬 vod_export.json")
    if os.path.exists('kablo_epg.xml'):
        print("📋 kablo_epg.xml")

if __name__ == "__main__":
    main()
