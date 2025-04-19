#Copyright @ISmartDevs
#Channel t.me/TheSmartDev
import os
import logging
from pathlib import Path
from typing import Optional
import yt_dlp
import asyncio
import aiofiles
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
import re
import math
import time
import requests
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from moviepy import VideoFileClip
from config import COMMAND_PREFIX, YT_COOKIES_PATH

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    TEMP_DIR = Path("temp")
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Referer': 'https://www.youtube.com',
    }

Config.TEMP_DIR.mkdir(exist_ok=True)

executor = ThreadPoolExecutor()

def sanitize_filename(title: str) -> str:
    """
    Sanitize file name by removing invalid characters.
    """
    title = re.sub(r'[<>:"/\\|?*]', '', title)
    title = title.replace(' ', '_')
    return f"{title[:50]}_{int(time.time())}"

def validate_url(url: str) -> bool:
    """
    Validate if the provided URL is a valid YouTube link.
    """
    return url.startswith(('https://www.youtube.com/', 'https://youtube.com/', 'https://youtu.be/'))

def format_size(size_bytes: int) -> str:
    """
    Format file size into human-readable string.
    """
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def format_duration(seconds: int) -> str:
    """
    Format video duration into human-readable string.
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def get_video_duration_moviepy(video_path: str) -> float:
    """
    Get video duration using MoviePy.
    Returns duration in seconds.
    """
    try:
        # Load the video file
        clip = VideoFileClip(video_path)
        duration = clip.duration  # Get duration in seconds
        clip.close()  # Close the video file
        return duration
    except Exception as e:
        logger.error(f"Error getting video duration: {e}")
        return 0.0

async def progress_bar(current, total, status_message, start_time, last_update_time):
    """
    Display a progress bar for uploads.
    """
    elapsed_time = time.time() - start_time
    percentage = (current / total) * 100
    progress = "▓" * int(percentage // 5) + "░" * (20 - int(percentage // 5))
    speed = current / elapsed_time / 1024 / 1024  # Speed in MB/s
    uploaded = current / 1024 / 1024  # Uploaded size in MB
    total_size = total / 1024 / 1024  # Total size in MB

    # Throttle updates: Only update if at least 2 seconds have passed since the last update
    if time.time() - last_update_time[0] < 2:
        return
    last_update_time[0] = time.time()  # Update the last update time

    text = (
        f"**📥 Upload Progress 📥**\n\n"
        f"{progress}\n\n"
        f"**🚧 Percentage:** {percentage:.2f}%\n"
        f"**⚡️ Speed:** {speed:.2f} MB/s\n"
        f"**📶 Uploaded:** {uploaded:.2f} MB of {total_size:.2f} MB"
    )
    try:
        await status_message.edit(text)
    except Exception as e:
        logger.error(f"Error updating progress: {e}")

def get_ydl_opts(output_filename: str) -> dict:
    """
    Return yt-dlp options.
    """
    return {
        'format': 'bestvideo[height<=720][width=1280][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': output_filename,
        'cookiefile': YT_COOKIES_PATH,
        'quiet': True,
        'noprogress': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
    }

def get_audio_opts(output_filename: str) -> dict:
    """
    Return yt-dlp options for audio download.
    """
    return {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_filename}.%(ext)s',
        'cookiefile': YT_COOKIES_PATH,
        'quiet': True,
        'noprogress': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    }

def download_video_sync(url: str) -> tuple:
    """
    Download a video using yt-dlp, along with its thumbnail.
    This function is synchronous and can be run in an executor.
    """
    if not validate_url(url):
        return None, "Invalid YouTube URL"

    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'cookiefile': YT_COOKIES_PATH}) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return None, "Could not fetch video information"

        title = info.get('title', 'Unknown Title')
        views = info.get('view_count', 0)
        duration = info.get('duration', 0)
        duration_str = format_duration(duration)
        thumbnail_url = info.get('thumbnail', None)

        safe_title = sanitize_filename(title)
        output_path = f"temp_media/{safe_title}.mp4"
        os.makedirs("temp_media", exist_ok=True)

        opts = get_ydl_opts(output_path)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        if not os.path.exists(output_path):
            return None, "Download failed: File not created"

        file_size = os.path.getsize(output_path)
        if file_size > 2_000_000_000:
            os.remove(output_path)
            return None, "Video file exceeds Telegram's 2GB limit."

        # Get duration using MoviePy
        duration = get_video_duration_moviepy(output_path)
        duration_str = format_duration(int(duration))
        
        # Download and prepare thumbnail
        thumbnail_path = None
        if thumbnail_url:
            thumbnail_path = prepare_thumbnail_sync(thumbnail_url, output_path)

        metadata = {
            'file_path': output_path,
            'title': title,
            'views': views,
            'duration': duration_str,
            'file_size': format_size(file_size),
            'thumbnail_path': thumbnail_path
        }

        logger.info(f"Video Metadata: {metadata}")
        print(f"Video Metadata: {metadata}")  # Print metadata to the terminal
        return metadata, None

    except yt_dlp.utils.DownloadError:
        logger.error("Download failed: Video unavailable or restricted")
        return None, "Download failed: Video unavailable or restricted"
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None, f"An unexpected error occurred: {e}"

def download_audio_sync(url: str) -> tuple:
    """
    Download audio from YouTube using yt-dlp.
    This function is synchronous and can be run in an executor.
    """
    if not validate_url(url):
        return None, "Invalid YouTube URL"

    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'cookiefile': YT_COOKIES_PATH}) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return None, "Could not fetch video information"

        title = info.get('title', 'Unknown Title')
        views = info.get('view_count', 0)
        duration = info.get('duration', 0)
        duration_str = format_duration(duration)

        safe_title = sanitize_filename(title)
        base_path = f"temp_media/{safe_title}"
        os.makedirs("temp_media", exist_ok=True)

        opts = get_audio_opts(base_path)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        output_path = f"{base_path}.mp3"
        if not os.path.exists(output_path):
            possible_files = [f for f in os.listdir("temp_media") if f.startswith(safe_title)]
            if possible_files:
                original_file = os.path.join("temp_media", possible_files[0])
                if os.path.exists(original_file):
                    return None, f"File exists but conversion failed: {original_file}"
            return None, "Download failed: File not created"

        file_size = os.path.getsize(output_path)
        if file_size > 2_000_000_000:
            os.remove(output_path)
            return None, "Audio file exceeds Telegram's 2GB limit."

        metadata = {
            'file_path': output_path,
            'title': title,
            'views': views,
            'duration': duration_str,
            'file_size': format_size(file_size),
            'thumbnail_path': prepare_thumbnail_sync(info['thumbnail'], output_path) if 'thumbnail' in info else None
        }

        logger.info(f"Audio Metadata: {metadata}")
        print(f"Audio Metadata: {metadata}")  # Print metadata to the terminal
        return metadata, None

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download failed: {e}")
        return None, f"Download failed: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None, f"An unexpected error occurred: {e}"

def prepare_thumbnail_sync(thumbnail_url: str, output_path: str) -> str:
    """
    Download and prepare the thumbnail image.
    This function is synchronous and can be run in an executor.
    """
    try:
        response = requests.get(thumbnail_url)
        if response.status_code == 200:
            thumbnail_temp_path = f"{output_path}_thumbnail.jpg"
            with open(thumbnail_temp_path, 'wb') as f:
                f.write(response.content)

            thumbnail_resized_path = f"{output_path}_thumb.jpg"
            with Image.open(thumbnail_temp_path) as img:
                img = img.convert('RGB')
                img.save(thumbnail_resized_path, "JPEG", quality=85)

            os.remove(thumbnail_temp_path)
            return thumbnail_resized_path
    except Exception as e:
        logger.error(f"Error preparing thumbnail: {e}")
    return None

async def search_youtube(query: str) -> Optional[str]:
    """
    Search YouTube for the first video result matching the query.
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'default_search': 'ytsearch1:',
        'nooverwrites': True,
        'cookiefile': YT_COOKIES_PATH,
        'no_warnings': True,
        'quiet': True,
        'no_color': True,
        'simulate': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.get_event_loop().run_in_executor(executor, ydl.extract_info, query, False)
            if 'entries' in info and info['entries']:
                return info['entries'][0]['webpage_url']
    except Exception as e:
        logger.error(f"YouTube search error: {e}")

    return None

async def handle_download_request(client: Client, message: Message, query: str):
    search_message = await client.send_message(
        chat_id=message.chat.id,
        text="**Searching The Video**",
        parse_mode=ParseMode.MARKDOWN
    )

    if not validate_url(query):
        video_url = await search_youtube(query)
        if not video_url:
            await search_message.edit_text(
                text="**❌No Video Matched To Your Search**"
            )
            return
    else:
        video_url = query

    try:
        loop = asyncio.get_event_loop()
        result, error = await loop.run_in_executor(executor, download_video_sync, video_url)
        if error:
            await search_message.edit(
                text=f"**Incomplete or invalid YouTube URL**",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        await search_message.edit(
            text="**Found ☑️ Downloading...**",
            parse_mode=ParseMode.MARKDOWN
        )

        video_path = result['file_path']
        title = result['title']
        views = result['views']
        duration = result['duration']
        file_size = result['file_size']
        thumbnail_path = result.get('thumbnail_path')

        logger.info(f"Video Downloaded: {title}, Views: {views}, Duration: {duration}, Size: {file_size}")

        if message.from_user:
            user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
            user_info = f"[{user_full_name}](tg://user?id={message.from_user.id})"
        else:
            group_name = message.chat.title or "this group"
            group_url = f"https://t.me/{message.chat.username}" if message.chat.username else "this group"
            user_info = f"[{group_name}]({group_url})"

        video_caption = (
            f"🎵 **Title:** **{title}**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👁️‍🗨️ **Views:** **{views}** views\n"
            f"🔗 [Watch On YouTube]({video_url})\n"
            f"⏱️ **Duration:** **{duration}**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡️ **Downloaded By** {user_info}"
        )

        last_update_time = [0]
        start_time = time.time()

        await client.send_video(
            chat_id=message.chat.id,
            video=video_path,
            caption=video_caption,
            parse_mode=ParseMode.MARKDOWN,
            supports_streaming=True,
            thumb=thumbnail_path,
            height=720,
            width=1280,
            duration=int(get_video_duration_moviepy(video_path)),
            progress=progress_bar,
            progress_args=(search_message, start_time, last_update_time)
        )

        # Cleanup
        if os.path.exists(video_path):
            os.remove(video_path)
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)

        await search_message.delete()

    except Exception as e:
        logger.error(f"An unexpected error occurred during video download: {e}")
        await search_message.edit(
            text=f"**YouTube Downloader API Dead **",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_audio_request(client: Client, message: Message, query: str):
    status_message = await client.send_message(
        chat_id=message.chat.id,
        text="**Searching For The Song**",
        parse_mode=ParseMode.MARKDOWN
    )

    if not validate_url(query):
        video_url = await search_youtube(query)
        if not video_url:
            await status_message.edit_text(
                text="**❌ No Song Matched To Your Search**"
            )
            return
    else:
        video_url = query

    try:
        loop = asyncio.get_event_loop()
        result, error = await loop.run_in_executor(executor, download_audio_sync, video_url)
        if error:
            await status_message.edit(
                text=f"**Incomplete or invalid YouTube URL**",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        await status_message.edit(
            text="**Found ☑️ Downloading...**",
            parse_mode=ParseMode.MARKDOWN
        )

        audio_path = result['file_path']
        title = result['title']
        views = result['views']
        duration = result['duration']
        file_size = result['file_size']
        thumbnail_path = result.get('thumbnail_path')

        logger.info(f"Audio Downloaded: {title}, Views: {views}, Duration: {duration}, Size: {file_size}")

        if message.from_user:
            user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
            user_info = f"[{user_full_name}](tg://user?id={message.from_user.id})"
        else:
            group_name = message.chat.title or "this group"
            group_url = f"https://t.me/{message.chat.username}" if message.chat.username else "this group"
            user_info = f"[{group_name}]({group_url})"

        audio_caption = (
            f"🎵 **Title:** **{title}**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👁️‍🗨️ **Views:** **{views}** views\n"
            f"🔗 [Listen On YouTube]({video_url})\n"
            f"⏱️ **Duration:** **{duration}**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡️ **Downloaded By** {user_info}"
        )

        last_update_time = [0]
        start_time = time.time()

        await client.send_audio(
            chat_id=message.chat.id,
            audio=audio_path,
            caption=audio_caption,
            title=title,
            performer="Smart Tools 💥",
            parse_mode=ParseMode.MARKDOWN,
            thumb=thumbnail_path,
            progress=progress_bar,
            progress_args=(status_message, start_time, last_update_time)
        )

        # Cleanup
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)

        await status_message.delete()

    except Exception as e:
        logger.error(f"An unexpected error occurred during audio download: {e}")
        await status_message.edit_text(
            text=f"**YouTube Downloader API Dead **"
        )
        if os.path.exists(audio_path):
            os.remove(audio_path)

def setup_downloader_handler(app: Client):
    # Create a regex pattern from the COMMAND_PREFIX list
    command_prefix_regex = f"[{''.join(map(re.escape, COMMAND_PREFIX))}]"

    @app.on_message(filters.regex(rf"^{command_prefix_regex}(yt|video)(\s+.+)?$"))
    async def video_command(client, message):
        command_parts = message.text.split(maxsplit=1)
        if len(command_parts) == 1 or not command_parts[1]:
            await client.send_message(
                chat_id=message.chat.id,
                text="**Please provide your video name or link❌**",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            url_or_query = command_parts[1]
            await handle_download_request(client, message, url_or_query)

    @app.on_message(filters.regex(rf"^{command_prefix_regex}song(\s+.+)?$"))
    async def song_command(client, message):
        command_parts = message.text.split(maxsplit=1)
        if len(command_parts) == 1 or not command_parts[1]:
            await client.send_message(
                chat_id=message.chat.id,
                text="**Please provide a Music Name Or Link❌**",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            url_or_query = command_parts[1]
            await handle_audio_request(client, message, url_or_query)
