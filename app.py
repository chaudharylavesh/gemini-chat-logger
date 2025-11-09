import streamlit as st
import gspread
import google.generativeai as genai
from google.oauth2.service_account import Credentials
from datetime import datetime


# -----------------------------------------------------------------
# 1. SETUP - Page Config and Secrets
# -----------------------------------------------------------------

# Set the page configuration
st.set_page_config(
    page_title="Dr. Huberman AI",
    page_icon="🧠",
    layout="centered"
)

# Load secrets from Streamlit's secrets manager
# These keys are set in your Streamlit Cloud app settings
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SERVICE_ACCOUNT_JSON = st.secrets["SERVICE_ACCOUNT_JSON"]
    SHEET_NAME = st.secrets["SHEET_NAME"]
except KeyError:
    st.error("ERROR: Missing secrets (GEMINI_API_KEY, SERVICE_ACCOUNT_JSON, or SHEET_NAME).")
    st.stop()

# Define the system prompt for the chatbot
SYSTEM_PROMPT = """You are Dr. Huberman AI.
You give science-backed, practical, concise explanations about neuroscience, psychology, health, and behavior.
Avoid pseudoscience, cite mechanisms when relevant, and sound calm and confident."""

# -----------------------------------------------------------------
# 2. BACKEND FUNCTIONS - Google Sheets & Gemini
# -----------------------------------------------------------------

@st.cache_resource
def setup_google_sheets_client():
    """Sets up and returns an authorized gspread client."""
    try:
        # Define the scopes (permissions) we need
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file"
        ]
        
        creds = Credentials.from_service_account_info(
            SERVICE_ACCOUNT_JSON,
            scopes=scopes  # Pass the scopes list here
        )
        # ---------------------
        
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Failed to authorize Google Sheets: {e}")
        return None

def log_chat_to_sheet(client, user_message, bot_response):
    """Logs a single chat exchange to the Google Sheet."""
    if client is None:
        st.warning("Google Sheets client not initialized. Skipping log.")
        return
    try:
        sheet = client.open(SHEET_NAME).sheet1
        timestamp = datetime.now().isoformat()
        # Append a new row
        sheet.append_row([timestamp, user_message, bot_response])
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: Spreadsheet '{SHEET_NAME}' not found. Check name and sharing.")
    except Exception as e:
        st.error(f"Error logging to Google Sheet: {e}")

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

# Initialize the gspread client and Gemini model
gs_client = setup_google_sheets_client()
gemini_model = get_gemini_model()

# Initialize chat history in session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display previous messages from history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Get new user input
if prompt := st.chat_input("Ask about neuroscience, habits, or health:"):
    
    # Stop if backend services failed to load
    if gemini_model is None or gs_client is None:
        st.error("Backend services not initialized. Cannot process request.")
        st.stop()

    # Add user message to history and display it
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate the bot's response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Format the prompt for the model
                full_prompt = f"{SYSTEM_PROMPT}\n\nUser: {prompt}\nAssistant:"
                
                # Generate response
                response = gemini_model.generate_content(full_prompt)
                bot_response = response.text
                
                # Display and save the bot's response
                st.markdown(bot_response)
                st.session_state.chat_history.append({"role": "assistant", "content": bot_response})
                
                # Log the conversation to Google Sheets
                log_chat_to_sheet(gs_client, prompt, bot_response)
                
            except Exception as e:
                st.error(f"Error generating response from Gemini: {e}")