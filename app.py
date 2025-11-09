import streamlit as st
import gspread
import google.generativeai as genai
from google.oauth2.service_account import Credentials
from datetime import datetime

# -----------------------------------------------------------------
# 1. SETUP - Page Config and Secrets
# -----------------------------------------------------------------

st.set_page_config(
    page_title="Dr. Huberman AI",
    page_icon="🧠",
    layout="centered"
)

# Load secrets from Streamlit's secrets manager
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SERVICE_ACCOUNT_JSON = st.secrets["SERVICE_ACCOUNT_JSON"]
    SHEET_ID = st.secrets["SHEET_ID"] # <-- We are now using the ID
    
    # We still keep SHEET_NAME as a fallback and for the error message
    SHEET_NAME = st.secrets.get("SHEET_NAME", "ChatLogs") 

except KeyError as e:
    st.error(f"ERROR: Missing secret: {e}. Please add it in your app's Settings -> Secrets.")
    st.info("You must have GEMINI_API_KEY, SERVICE_ACCOUNT_JSON, and SHEET_ID.")
    st.stop()

# Define the system prompt for the chatbot
SYSTEM_PROMPT = """You are Dr. Huberman AI...""" # (Your prompt)

# -----------------------------------------------------------------
# 2. BACKEND FUNCTIONS - Google Sheets & Gemini
# -----------------------------------------------------------------

@st.cache_resource
def setup_google_sheets_client():
    """Sets up and returns an authorized gspread client."""
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file"
        ]
        creds = Credentials.from_service_account_info(
            SERVICE_ACCOUNT_JSON,
            scopes=scopes
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Failed to authorize Google Sheets: {e}")
        return None

def log_chat_to_sheet(client, user_message, bot_response):
    """Logs a single chat exchange to the Google Sheet."""
    if client is None:
        return
    try:
        # --- THIS IS THE NEW LOGIC ---
        # Try to open by the unique ID first
        sheet = client.open_by_key(SHEET_ID).sheet1
        
    except Exception as e:
        st.error(f"Error opening sheet by ID. Trying by name... Error: {e}")
        try:
            # Fallback to opening by name if ID fails
            sheet = client.open(SHEET_NAME).sheet1
        except gspread.exceptions.SpreadsheetNotFound:
            st.error(f"Error: Spreadsheet '{SHEET_NAME}' not found. Check name and sharing.")
            return
        except Exception as e_name:
            st.error(f"Error opening sheet by name: {e_name}")
            return

    # If successful, append the row
    try:
        timestamp = datetime.now().isoformat()
        sheet.append_row([timestamp, user_message, bot_response])
    except Exception as e_append:
        st.error(f"Error appending row to sheet: {e_append}")

@st.cache_resource
def get_gemini_model():
    """Configures and returns the Gemini generative model."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("models/gemini-pro-latest")
        return model
    except Exception as e:
        st.error(f"Error setting up Gemini model: {e}")
        return None

# -----------------------------------------------------------------
# 3. STREAMLIT APP UI - Chat Interface
# -----------------------------------------------------------------

st.title("🧠 Dr. Huberman AI")

# --- DEBUG INFO BOX ---
# This will print the exact email the app is using.
try:
    APP_EMAIL = SERVICE_ACCOUNT_JSON['client_email']
    st.info(f"App is running as: **{APP_EMAIL}**\n\nPlease verify this *exact* email is an **Editor** on your Google Sheet.", icon="ℹ️")
except Exception as e:
    st.error(f"Could not read client_email from secrets: {e}")

# Initialize the gspread client and Gemini model
gs_client = setup_google_sheets_client()
gemini_model = get_gemini_model()

# Initialize chat history in session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# (Rest of the chat UI code is identical)
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about neuroscience, habits, or health:"):
    
    if gemini_model is None or gs_client is None:
        st.error("Backend services not initialized. Cannot process request.")
        st.stop()

    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                full_prompt = f"{SYSTEM_PROMPT}\n\nUser: {prompt}\nAssistant:"
                response = gemini_model.generate_content(full_prompt)
                bot_response = response.text
                
                st.markdown(bot_response)
                st.session_state.chat_history.append({"role": "assistant", "content": bot_response})
                
                # Log the conversation
                log_chat_to_sheet(gs_client, prompt, bot_response)
                
            except Exception as e:
                st.error(f"Error generating response from Gemini: {e}")