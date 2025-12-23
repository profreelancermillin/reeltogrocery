import streamlit as st
import yt_dlp
from google import genai
from google.genai import types
import os
import time

# 1. Setup Page
st.set_page_config(page_title="ReelToGrocery", layout="centered")

# 2. Setup Gemini (New SDK)
if "GEMINI_API_KEY" in st.secrets:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Missing GEMINI_API_KEY in Streamlit Secrets.")
    st.stop()

def download_audio(video_url):
    """Downloads audio with Anti-Bot protections."""
    output_filename = "temp_audio"
    # Clean up old files
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
            # ANTI-BOT SETTINGS
            'quiet': False,
            'no_warnings': False,
            'nocheckcertificate': True,
            # Impersonate a real browser
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return f"{output_filename}.mp3"
    except Exception as e:
        st.error(f"Download Error: {e}")
        return None

def analyze_with_gemini(audio_path):
    try:
        # Upload file (New SDK Syntax)
        file_upload = client.files.upload(path=audio_path)
        
        # Wait for processing
        while file_upload.state.name == "PROCESSING":
            time.sleep(1)
            file_upload = client.files.get(name=file_upload.name)

        # Generate Content
        prompt = """
        Listen to this cooking video.
        1. Extract the dish name.
        2. Create a shopping list of ingredients.
        3. If measurements are missing, estimate them (e.g., '1 cup').
        4. Categorize by aisle (Produce, Dairy, etc).
        """
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=[file_upload, prompt]
        )
        return response.text
    except Exception as e:
        return f"AI Error: {e}"

# 3. UI
st.title("🛒 ReelToGrocery")
st.markdown("Paste a YouTube Short link (e.g., https://www.youtube.com/shorts/...)")

video_url = st.text_input("Video Link:")

if st.button("Generate List"):
    if video_url:
        with st.spinner("Downloading audio... (This takes 10s)"):
            audio_file = download_audio(video_url)
            
        if audio_file:
            with st.spinner("AI is analyzing the recipe..."):
                result = analyze_with_gemini(audio_file)
                st.markdown("### 📝 Shopping List")
                st.markdown(result)
                
                # Affiliate Link
                st.markdown("""
                <a href="https://www.amazon.com/fresh" target="_blank">
                    <button style="background-color:#FF9900; color:white; padding:10px 20px; border:none; border-radius:5px; font-weight:bold;">
                        👉 Order on Amazon Fresh
                    </button>
                </a>
                """, unsafe_allow_html=True)
                
                # Cleanup
                if os.path.exists(audio_file):
                    os.remove(audio_file)
