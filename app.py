import streamlit as st
import yt_dlp
from google import genai
import os
import time
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="ReelToGrocery", layout="centered")

if "GEMINI_API_KEY" in st.secrets:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 Error: Missing GEMINI_API_KEY in Secrets.")
    st.stop()

# --- HELPER FUNCTIONS ---

def get_best_transcript_via_ytdlp(url):
    """
    NUCLEAR OPTION: Uses yt-dlp to download the subtitle file directly.
    Bypasses the 'youtube-transcript-api' blocks.
    """
    output_filename = "temp_subs"
    # Clean up old files
    if os.path.exists(f"{output_filename}.en.vtt"):
        os.remove(f"{output_filename}.en.vtt")

    try:
        ydl_opts = {
            'skip_download': True,      # Don't download video (too fast!)
            'writesubtitles': True,     # Grab manual subs
            'writeautomaticsub': True,  # Grab auto-generated subs (The Savior)
            'subtitleslangs': ['en.*','en'], # Get any English
            'outtmpl': output_filename,
            'quiet': True,
            'no_warnings': True,
            # ANTI-BOT HEADERS (Tricks YouTube)
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # yt-dlp saves as "temp_subs.en.vtt" usually. Let's find it.
        for file in os.listdir("."):
            if file.startswith("temp_subs") and file.endswith(".vtt"):
                # Read the file
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                # Clean up (Delete file)
                os.remove(file)
                return content
                
        return None

    except Exception as e:
        print(f"Transcript Error: {e}")
        return None

def download_audio(url):
    """Fallback: Downloads audio if text fails."""
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
    """Sends content to Gemini 2.0."""
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
            file_upload = client.files.upload(path=content)
            while file_upload.state.name == "PROCESSING":
                time.sleep(1)
                file_upload = client.files.get(name=file_upload.name)
            
            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=[file_upload, prompt]
            )
        else:
            # Clean VTT timestamps if using text (optional, Gemini usually ignores them)
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

# Manual Fallback Box
with st.expander("Or paste text manually (if video fails)"):
    manual_text = st.text_area("Paste description/recipe here:")

if st.button("Generate List"):
    result = None
    
    # 1. Manual Text Priority
    if manual_text:
        with st.spinner("Processing text..."):
             result = ai_process(manual_text, is_audio=False)
             
    # 2. Video URL Processing
    elif url:
        # Step A: Try fetching Text (Fastest)
        with st.status("Trying to get recipe...", expanded=True) as status:
            st.write("Attempting to download subtitles...")
            transcript = get_best_transcript_via_ytdlp(url)
            
            if transcript:
                st.write("✅ Subtitles found!")
                result = ai_process(transcript, is_audio=False)
                status.update(label="Success!", state="complete", expanded=False)
            
            # Step B: Fallback to Audio (If subtitles blocked)
            else:
                st.write("⚠️ No subtitles. Switching to Audio Listen mode...")
                audio_file = download_audio(url)
                
                if audio_file:
                    st.write("✅ Audio downloaded! Listening...")
                    result = ai_process(audio_file, is_audio=True)
                    os.remove(audio_file)
                    status.update(label="Success!", state="complete", expanded=False)
                else:
                    status.update(label="Failed", state="error", expanded=False)
                    st.error("❌ Could not access video. It might be private or heavily blocked.")

    # 3. Display
    if result:
        st.markdown("---")
        st.markdown("### 📝 Shopping List")
        st.markdown(result)
        st.markdown("""
        <a href="https://www.amazon.com/fresh" target="_blank">
            <button style="width:100%; background-color:#FF9900; color:white; padding:15px; border:none; border-radius:10px; font-weight:bold; cursor:pointer;">
                👉 Order on Amazon
            </button>
        </a>
        """, unsafe_allow_html=True)
