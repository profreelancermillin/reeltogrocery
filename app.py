import streamlit as st
import yt_dlp
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi
import os
import time
import re

# 1. Setup
st.set_page_config(page_title="ReelToGrocery", layout="centered")

if "GEMINI_API_KEY" in st.secrets:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Missing GEMINI_API_KEY in Secrets.")
    st.stop()

# --- HELPER FUNCTIONS ---

def get_video_id(url):
    """Extracts Video ID from various YouTube URL formats."""
    video_id = None
    if "youtu.be" in url:
        video_id = url.split("/")[-1].split("?")[0]
    elif "youtube.com/shorts" in url:
        video_id = url.split("shorts/")[1].split("?")[0]
    elif "v=" in url:
        video_id = url.split("v=")[1].split("&")[0]
    return video_id

def get_youtube_transcript(url):
    """Gets the text transcript directly (No download needed)."""
    try:
        video_id = get_video_id(url)
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        # Combine all lines into one string
        full_text = " ".join([t['text'] for t in transcript])
        return full_text
    except Exception as e:
        # Fallback if no transcript exists
        return None

def download_tiktok_audio(url):
    """Downloads audio for TikTok/Instagram (Non-YouTube)."""
    output_filename = "temp_audio"
    if os.path.exists(f"{output_filename}.mp3"):
        os.remove(f"{output_filename}.mp3")
    
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_filename,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return f"{output_filename}.mp3"
    except Exception as e:
        return None

def ai_process(content, is_audio=False):
    """Sends Text or Audio to Gemini."""
    try:
        prompt = """
        You are a Chef Assistant. 
        Extract a shopping list of ingredients from this recipe.
        1. Name the dish.
        2. List ingredients with measurements (estimate if missing).
        3. Group by aisle (Produce, Dairy, etc).
        4. Return clear Markdown.
        """
        
        if is_audio:
            # Upload file for Gemini to listen
            file_upload = client.files.upload(path=content)
            while file_upload.state.name == "PROCESSING":
                time.sleep(1)
                file_upload = client.files.get(name=file_upload.name)
            
            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=[file_upload, prompt]
            )
        else:
            # Just read the text
            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=[prompt + f"\n\nTRANSCRIPT:\n{content}"]
            )
            
        return response.text
    except Exception as e:
        return f"AI Error: {e}"

# --- MAIN UI ---
st.title("🛒 ReelToGrocery")
st.markdown("Paste a YouTube Short, TikTok, or Reel link:")

url = st.text_input("🔗 Video Link")

if st.button("Generate List"):
    if url:
        result = None
        
        # STRATEGY 1: CHECK IF YOUTUBE (Use Text - Unblockable)
        if "youtube.com" in url or "youtu.be" in url:
            with st.status("Reading YouTube Transcript...", expanded=True):
                transcript_text = get_youtube_transcript(url)
                
                if transcript_text:
                    st.write("Transcript found! Analyzing text...")
                    result = ai_process(transcript_text, is_audio=False)
                else:
                    st.error("No transcript found for this video. (Creator didn't enable captions).")
        
        # STRATEGY 2: TIKTOK/OTHER (Use Audio Download)
        else:
            with st.status("Downloading Audio...", expanded=True):
                audio_file = download_tiktok_audio(url)
                
                if audio_file:
                    st.write("Listening to audio...")
                    result = ai_process(audio_file, is_audio=True)
                    os.remove(audio_file) # Clean up
                else:
                    st.error("Could not download video. Link might be private or blocked.")

        # DISPLAY RESULT
        if result:
            st.markdown("### 📝 Shopping List")
            st.markdown(result)
            
            # Money Button
            st.markdown("""
            <a href="https://www.amazon.com/fresh" target="_blank">
                <button style="width:100%; background-color:#FF9900; color:white; padding:15px; border:none; border-radius:10px; font-weight:bold; cursor:pointer;">
                    👉 Order on Amazon
                </button>
            </a>
            """, unsafe_allow_html=True)
