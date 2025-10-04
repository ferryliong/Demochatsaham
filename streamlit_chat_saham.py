# Import the necessary libraries
import streamlit as st # For creating the web app interface
from google import genai # For interacting with the Google Gemini API
import pandas as pd # Import Pandas for CSV handling
import io # Import io for reading file content
import numpy as np


# --- 1. Page Configuration and Title ---

# Set the title and a caption for the web page
st.title("💬 Cek saham dengan .csv (gemini csv analysis)")
st.caption(" * untuk dapat di perhatikan analysis ini berdasarkan data yang di input")

# --- 2. Sidebar for Settings ---

# Create a sidebar section for app settings using 'with st.sidebar:'
with st.sidebar:
    # Add a subheader to organize the settings
    st.subheader("Settings")
    
    # Create a text input field for the Google AI API Key.
    google_api_key = st.text_input("Masukan Goggle API key anda", type="password")
    
    # Add File Uploader for CSV
    st.subheader("Upload Data CSV")
    # File uploader widget that accepts CSV files
    uploaded_file = st.file_uploader(
        "bisa menggunkan data .csv dari investing.com (Maks 10MB)", 
        type=["csv"],
        help="Data CSV akan dikirimkan ke Gemini sebagai tabel teks."
    )
    
    # Create a button to reset the conversation.
    reset_button = st.button("Reset Conversation", help="Clear all messages and start fresh")
    
    # --- Tambahan untuk Menampilkan Total Token yang Digunakan ---
    if "total_tokens_used" not in st.session_state:
        st.session_state.total_tokens_used = 0
    
    # Tampilkan total token yang digunakan di sidebar
    st.markdown("---")
    st.subheader("Penggunaan Token")
    st.info(f"Total Token Digunakan: **{st.session_state.total_tokens_used}**")
    # -----------------------------------------------------------


# --- 3. API Key and Client Initialization ---

if not google_api_key:
    st.info("Masukan API KEY Gemini Kalian, Lalu di enter", icon="🗝️")
    st.stop()

# --- Initialization Logic ---
if ("genai_client" not in st.session_state) or (getattr(st.session_state, "_last_key", None) != google_api_key):
    try:
        st.session_state.genai_client = genai.Client(api_key=google_api_key)
        st.session_state._last_key = google_api_key
        st.session_state.pop("chat", None)
        st.session_state.pop("messages", None)
        # Tambahkan pembersihan data CSV di session state
        st.session_state.pop("data_csv", None)
        # Reset token counter saat API key baru diinput
        st.session_state.total_tokens_used = 0 
    except Exception as e:
        st.error(f"Invalid API Key: {e}")
        st.stop()


# --- 4. Data Processing (New) ---

csv_data_string = ""

# Check if a file was uploaded AND it hasn't been processed yet
if uploaded_file and ("data_csv" not in st.session_state or st.session_state.data_csv != uploaded_file.name):
    try:
        # Read the uploaded CSV file into a Pandas DataFrame
        df = pd.read_csv(uploaded_file, encoding='utf-8')

        # Limit to the first 10 rows and 8 columns to save tokens and prevent massive inputs
        max_rows = 30
        max_cols = 20
        if df.shape[0] > max_rows or df.shape[1] > max_cols:
            st.warning(f"File terlalu besar. Hanya mengambil {max_rows} baris pertama dan {max_cols} kolom pertama.")
            df_display = df.iloc[:max_rows, :max_cols]
        else:
            df_display = df
            
        # Convert the DataFrame to a Markdown table string
        csv_markdown = df_display.to_markdown(index=False)
        
        # Store the prepared string and filename in session state
        st.session_state.data_csv_string = csv_markdown
        st.session_state.data_csv = uploaded_file.name
        
        st.success(f"File **{uploaded_file.name}** berhasil dimuat! Data akan dianalisis saat Anda mengirim pesan.")
        
    except Exception as e:
        st.error(f"Gagal memproses file CSV: {e}")
        st.session_state.pop("data_csv", None)
        st.session_state.pop("data_csv_string", None)

# 4.1 Set the csv data string for the current run if it exists in session state
if "data_csv_string" in st.session_state:
    csv_data_string = st.session_state.data_csv_string
    # Tampilkan pratinjau data yang dimuat
    with st.expander(f"Pratinjau Data CSV ({st.session_state.data_csv})"):
        st.code(csv_data_string, language="markdown")
        

# --- 5. Chat History Management ---

# Initialize the chat session if it doesn't already exist in memory.
if "chat" not in st.session_state:
    # Create a new chat instance using the 'gemini-2.5-flash' model.
    st.session_state.chat = st.session_state.genai_client.chats.create(model="gemini-2.5-flash")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Handle the reset button click.
if reset_button:
    st.session_state.pop("chat", None)
    st.session_state.pop("messages", None)
    st.session_state.pop("data_csv", None) # Clear data state
    st.session_state.pop("data_csv_string", None) # Clear data string
    st.session_state.total_tokens_used = 0 # Reset token counter
    st.rerun()

# --- 6. Display Past Messages ---

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # Tambahkan tampilan token di bawah pesan asisten
        st.markdown(msg["content"])
        if "token_info" in msg:
            st.caption(msg["token_info"])


# --- 7. Handle User Input and API Communication (MODIFIKASI DI SINI) ---

prompt = st.chat_input("Type your message here...")

if prompt:
    
    full_prompt = prompt
    
    # 1. Prepend CSV data to the prompt if available
    if csv_data_string:
        # Construct the instruction and include the data string
        data_header = (
            f"Anda memiliki data CSV bernama **{st.session_state.data_csv}** berikut:\n\n"
            f"```csv_table\n{csv_data_string}\n```\n\n"
            f"Berdasarkan data di atas, tolong jawab pertanyaan pengguna ini: "
        )
        full_prompt = data_header + prompt

    # 2. Add the user's message to our message history list (only the prompt they typed)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 3. Display the user's message on the screen immediately
    with st.chat_message("user"):
        st.markdown(prompt)

    # 4. Get the assistant's response.
    try:
        
        # --- Token Counter (Input) ---
        # Menghitung token untuk prompt saat ini sebelum dikirim
        try:
            input_token_count_response = st.session_state.genai_client.models.count_tokens(
                model="gemini-2.5-flash",
                contents=[{"role": "user", "parts": [{"text": full_prompt}]}]
            )
            input_token_count = input_token_count_response.total_tokens
        except Exception as e:
            input_token_count = "N/A"
            st.warning(f"Gagal menghitung token input: {e}")
        # -----------------------------

        # Send the FULL_PROMPT (which may include the CSV data) to the Gemini API.
        response = st.session_state.chat.send_message(full_prompt)
        
        if hasattr(response, "text"):
            answer = response.text
        else:
            answer = str(response)

        # --- Token Counter (Output & Total) ---
        # Dapatkan informasi penggunaan token dari respons
        usage_metadata = response.usage_metadata
        
        prompt_tokens = usage_metadata.prompt_token_count
        completion_tokens = usage_metadata.candidates_token_count
        total_tokens = usage_metadata.total_token_count
        
        # Update total token yang digunakan di session state
        st.session_state.total_tokens_used += total_tokens
        
        # Buat string informasi token
        token_info = (
            f"**Token Usage:** Input: {prompt_tokens}, Output: {completion_tokens}, Total: {total_tokens}"
        )
        # -------------------------------------


    except Exception as e:
        answer = f"An error occurred: {e}"
        token_info = "Token information not available due to error."


    # 5. Display the assistant's response.
    with st.chat_message("assistant"):
        st.markdown(answer)
        st.caption(token_info) # Tampilkan informasi token di bawah pesan asisten
    
    # 6. Add the assistant's response to the message history list.
    # Simpan informasi token bersama dengan pesan asisten
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "token_info": token_info
    })
    
    # Rerun untuk memperbarui tampilan total token di sidebar
    st.rerun()
