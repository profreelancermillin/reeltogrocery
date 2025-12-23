import streamlit as st
import yt_dlp
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi
import os
import time

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(page_title="ReelToGrocery", layout="centered")

# Initialize Gemini Client (New 2.0 SDK)
if "GEMINI_API_KEY" in st.secrets:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 Error: Missing GEMINI_API_KEY in Streamlit Secrets.")
    st.stop()

# --- 2. HELPER FUNCTIONS ---

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
    """
    The 'Robocop' Method: 
    Hunts down ANY text attached to the video (Manual, Auto-generated, or Translated).
    """
    try:
        video_id = get_video_id(url)
        
        # 1. Get ALL available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # 2. Try to find English first (Manual or Auto)
        try:
            transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        except:
            # 3. If no English, just grab the FIRST one (Auto-generated in any language)
            transcript = next(iter(transcript_list))

        # 4. Download the text
        transcript_data = transcript.fetch()
        
        # 5. Combine into one string
        full_text = " ".join([t['text'] for t in transcript_data])
        return full_text

    except Exception as e:
        print(f"Transcript Error: {e}") # Log for debugging
        return None

def download_tiktok_audio(url):
    """Downloads audio for TikTok/Instagram (Non-YouTube) with Anti-Bot headers."""
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
            'quiet': True,
            'no_warnings': True,
            # Trick to look like a real browser
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return f"{output_filename}.mp3"
    except Exception as e:
        return None

def ai_process(content, is_audio=False):
    """Sends Text or Audio to Gemini 2.0 Flash."""
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

# --- 3. MAIN APP INTERFACE ---
st.title("🛒 ReelToGrocery")
st.markdown("Paste a YouTube Short, TikTok, or Reel link:")

url = st.text_input("🔗 Video Link")
st.write("OR")
manual_text = st.text_area("Paste recipe text manually (if video has no captions):")

if st.button("Generate List"):
    result = None
    
    # CASE A: USER PASTED TEXT
    if manual_text:
        with st.spinner("Processing manual text..."):
             result = ai_process(manual_text, is_audio=False)
             
    # CASE B: USER PROVIDED A URL
    elif url:
        # STRATEGY 1: YOUTUBE (Text Only - Fast & Unblockable)
        if "youtube.com" in url or "youtu.be" in url:
            with st.status("Fetching YouTube Transcript...", expanded=True):
                transcript_text = get_youtube_transcript(url)
                
                if transcript_text:
                    st.write("✅ Transcript found!")
                    result = ai_process(transcript_text, is_audio=False)
                else:
                    st.error("❌ No text found. Please copy the video description and paste it in the box above!")
        
        # STRATEGY 2: TIKTOK (Audio Download)
        else:
            with st.status("Downloading Audio...", expanded=True):
                audio_file = download_tiktok_audio(url)
                if audio_file:
                    st.write("✅ Audio downloaded!")
                    result = ai_process(audio_file, is_audio=True)
                    os.remove(audio_file)
                else:
                    st.error("❌ Download blocked. Try a different video.")

    # DISPLAY RESULT
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
