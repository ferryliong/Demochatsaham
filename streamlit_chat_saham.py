# Import the necessary libraries
import streamlit as st 
from google import genai
import io
from PIL import Image 
import os 

# --- 0. Page Configuration and Title ---
st.set_page_config(page_title="Gemini Stock Analisis", layout="wide")
st.title("💬 chat untuk Cek dan Analisis Saham dengan Capture Chart")
st.caption("capture screen chart saham yang kalian inginkan upload lalu tanyakan analisis nya")

# --- 1. Sidebar for Settings ---
with st.sidebar:
    st.subheader("Settings")
    google_api_key = st.text_input("Masukan Google AI API Key kalian", type="password")
    reset_button = st.button("Reset Conversation", help="Clear all messages and start fresh")
    st.markdown("---")
    
    # Tambahkan tampilan token di sidebar
    # Jika total_tokens_used ada di session_state, tampilkan
    if "total_tokens_used" in st.session_state:
        st.info(f"Token Digunakan (Sesi Ini): **{st.session_state.total_tokens_used}**")


# --- 2. API Key and Client Initialization (Minimal Change) ---
if not google_api_key:
    st.warning("Please add your Google AI API key in the sidebar to start chatting.", icon="🗝️")
    st.stop()

# --- Initialization Logic ---
if ("genai_client" not in st.session_state) or (getattr(st.session_state, "_last_key", None) != google_api_key):
    try:
        st.session_state.genai_client = genai.Client(api_key=google_api_key)
        st.session_state._last_key = google_api_key
        st.session_state.pop("chat_session", None) 
        st.session_state.pop("messages", None)
        st.session_state.pop("total_tokens_used", None) # Hapus total token saat key berubah
    except Exception as e:
        st.error(f"Invalid API Key: {e}")
        st.stop()

# --- 3. Chat Session and History Management ---

# Kami tidak lagi bergantung pada st.session_state.chat_session untuk mengirim pesan.
# Kami hanya menggunakannya untuk mendapatkan model
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "total_tokens_used" not in st.session_state:
    st.session_state.total_tokens_used = 0


# Handle the reset button click.
if reset_button:
    # Hanya hapus messages dan token, tidak perlu chat_session karena kita menggunakan generate_content
    st.session_state.pop("messages", None)
    st.session_state.pop("total_tokens_used", None)
    st.rerun()

# --- 4. Display Past Messages ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "text" in msg and msg["text"]: 
            st.markdown(msg["text"])
        if "image" in msg:
            st.image(msg["image"], caption=msg.get("caption", "User Upload"))

# --- 5. Handle User Input and API Communication ---
prompt = st.chat_input(
    "Enter your message and/or upload an image...", 
    accept_file="multiple",
    file_type=["jpg", "jpeg", "png"]
)

if prompt:
    
    # 1. Prepare content list for the API call (Hanya input user baru)
    user_content_parts = []
    
    # 2. Process Uploaded Files (Images)
    if prompt.files:
        for uploaded_file in prompt.files:
            image = Image.open(io.BytesIO(uploaded_file.read()))
            user_content_parts.append(image)
            st.session_state.messages.append(
                {"role": "user", "image": image, "caption": uploaded_file.name}
            )

    # 3. Process Text Input
    if prompt.text:
        user_content_parts.append(prompt.text)
        st.session_state.messages.append({"role": "user", "text": prompt.text})

    if not user_content_parts:
        st.warning("Please enter text or upload a file.")
        st.stop()
        
    # --- START: Logic PENGHITUNGAN TOKEN BARU ---
    
    # 4. Konversi riwayat chat ke format 'Contents' yang dibutuhkan generate_content
    api_history = []
    
    # Transformasi riwayat yang sudah ada
    for msg in st.session_state.messages:
        
        # NOTE ON RERUN: Since you use st.rerun(), the new user input is already 
        # in st.session_state.messages. The API call logic handles
        # the duplication, so we just focus on correct formatting here.
        
        # Only process messages that have content
        if "text" in msg or "image" in msg:
            parts = []
            
            # --- FIX FOR PYDANTIC VALIDATION ERROR ---
            
            # 1. Add Text Part
            if "text" in msg and msg["text"]:
                # Text (str) is automatically converted to a TextPart
                parts.append(msg["text"])
            
            # 2. Add Image Part
            if "image" in msg and isinstance(msg["image"], Image.Image):
                # The PIL Image object is stored in session state.
                # We append the PIL Image object. The genai.types.Content constructor 
                # (via Pydantic) should convert the PIL Image into a Part.
                # This direct appending usually works and is the cleanest way.
                parts.append(msg["image"])
            # --- END OF FIX ---
            
            # Append only if parts is not empty
            if parts:
                api_history.append(
                    # This line is where the validation failed before
                    genai.types.Content(role=msg["role"], parts=parts)
                )
    # Tambahkan input user yang baru (sudah ada di user_content_parts)
    # Kami akan menggunakan generate_content, bukan send_message

    # Hapus input user yang baru saja ditambahkan ke st.session_state.messages 
    # agar tidak diduplikasi saat history loop dijalankan
    # Cukup tampilkan kontennya di chat box
    with st.chat_message("user"):
        for part in user_content_parts:
            if isinstance(part, str):
                st.markdown(part)
            else:
                st.image(part, caption="User Upload")
    
    # Panggil generate_content (BUKAN send_message)
    try:
        # Gunakan riwayat chat yang sudah diubah formatnya (api_history) + input baru
        response = st.session_state.genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=api_history[:-len(user_content_parts)] + [
                genai.types.Content(role="user", parts=user_content_parts)
            ]
        )
        
        # 5. Dapatkan penggunaan token
        # Pastikan response.usage_metadata ada
        if response.usage_metadata:
            total_tokens = response.usage_metadata.total_token_count
            
            # Tambahkan ke total token yang sudah digunakan di sesi ini
            st.session_state.total_tokens_used += total_tokens
            
        else:
            total_tokens = 0
            
        # 6. Dapatkan jawaban
        if hasattr(response, "text"):
            answer = response.text
        else:
            answer = "The model returned a non-text response. Please try a text-only query."

    except Exception as e:
        answer = f"An API Error occurred: {e}"

    # 7. Display and Store the assistant's response.
    with st.chat_message("assistant"):
        st.markdown(answer)
        
    # Hanya simpan jawaban asisten (text) ke riwayat
    st.session_state.messages.append({"role": "assistant", "text": answer})
    
    st.rerun()
