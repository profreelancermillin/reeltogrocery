import streamlit as st
import yt_dlp
import google.generativeai as genai
import os
import time

# 1. Setup Page
st.set_page_config(page_title="ReelToGrocery", layout="centered")

# 2. Setup Gemini
# We use st.secrets so your key isn't public on GitHub
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Wait! You need to put your API Key in Streamlit Secrets.")
    st.stop()

def download_audio(video_url):
    """Downloads audio with anti-bot headers."""
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
            # --- NEW: ANTI-BOT HEADERS ---
            'quiet': False, # Let us see errors in logs
            'no_warnings': False,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'referer': 'https://www.google.com/',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return f"{output_filename}.mp3"
        
    except Exception as e:
        # --- NEW: PRINT THE REAL ERROR ---
        st.error(f"Detailed Error: {e}") 
        return None

def analyze_with_gemini(audio_path):
    try:
        # Upload audio to Gemini
        video_file = genai.upload_file(path=audio_path)
        
        # Wait for processing
        while video_file.state.name == "PROCESSING":
            time.sleep(1)
            video_file = genai.get_file(video_file.name)

        # The Prompt
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        prompt = """
        You are a Chef Assistant. Listen to this audio.
        1. Identify the name of the dish.
        2. Extract a shopping list of ingredients.
        3. If measurements are missing, ESTIMATE them (e.g., "1 onion", "2 tbsp oil").
        4. Group them by aisle (Produce, Dairy, Spices).
        """
        response = model.generate_content([video_file, prompt])
        return response.text
    except Exception as e:
        return f"Error: {e}"

# 3. The Interface
st.title("🛒 ReelToGrocery")
st.write("Paste a TikTok, Instagram Reel, or YouTube Short link:")

video_url = st.text_input("🔗 Video Link")

if st.button("📝 Generate Shopping List"):
    if video_url:
        with st.status("👩‍🍳 Chef is working...", expanded=True) as status:
            st.write("Downloading audio...")
            audio_file = download_audio(video_url)
            
            if audio_file:
                st.write("Listening to recipe...")
                result = analyze_with_gemini(audio_file)
                status.update(label="Done!", state="complete", expanded=False)
                
                st.markdown("### Your Shopping List")
                st.markdown(result)
                
                # --- MONETIZATION BUTTON ---
                amazon_link = "https://www.amazon.com/fresh" # Replace with your Affiliate Link later
                st.markdown(f"""
                    <a href="{amazon_link}" target="_blank">
                        <button style="width:100%; background-color:#FF9900; color:white; padding:15px; border:none; border-radius:10px; font-size:18px; font-weight:bold; cursor:pointer;">
                            🛒 Add All to Amazon Cart
                        </button>
                    </a>
                """, unsafe_allow_html=True)
                
            else:

                st.error("Could not download video. Make sure the link is public!")
