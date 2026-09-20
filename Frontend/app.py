import streamlit as st
import requests
import json
import os
import uuid
import time

# Set Google-inspired color theme
GOOGLE_COLORS = {
    "black": "#000000",
    "red": "#EA4335",
    "yellow": "#FBBC05",
    "green": "#34A853",
    "background": "#FAF6E9",
    "card": "#DDEB9D",
}

# Set page config with Google colors
st.set_page_config(
    page_title="CO2Ops Agent Chat",
    page_icon="🌱",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Inject Google-inspired CSS
st.markdown(
    f"""
    <style>
    :root {{
        --primary: {GOOGLE_COLORS['black']};
        --background: {GOOGLE_COLORS['background']};
        --card: {GOOGLE_COLORS['card']};
        --assistant-bubble: #E8F0FE;
        --user-bubble: {GOOGLE_COLORS['black']};
    }}
    
    .stApp {{
        background-color: var(--background);
        color: var(--primary);
    }}
    
    .stChatInput {{
        bottom: 20px;
    }}

    .stBottom > div {{
        background: var(--background) !important;
    }}
    
    .stChatInput input {{
        border: 2px solid var(--primary) !important;
        border-radius: 24px !important;
        padding: 12px 20px !important;
    }}
    
    .stChatInput button {{
        background: var(--primary) !important;
        border-radius: 20px !important;
    }}
    
    [data-testid="stSidebar"] {{
        background-color: var(--card) !important;
        border-right: 1px solid #e0e0e0;
        color: black;
    }}
    
    .stChatMessage {{
        padding: 8px 16px;
    }}
    
    [data-testid="stChatMessage-user"] {{
        background-color: var(--user-bubble);
        color: white;
        border-radius: 18px 18px 0 18px;
        margin-left: 25%;
    }}
    
    [data-testid="stChatMessage-assistant"] {{
        background-color: var(--assistant-bubble);
        border-radius: 18px 18px 18px 0;
        margin-right: 25%;
    }}
    
    [data-testid="stBaseButton-secondary"] {{
        background-color: #A0C878;
    }}

    #root > div > div > div > div > section > div > div > div > div > div > div > div > div > div > div > div > p {{
        color: black;
    }}

    [data-testid="stAlertContainer"] {{
        background-color: #F9C0AB;
        color: black;
    }}

    [aria-label="Chat message from assistant"] {{
        color: black;
    }}
    
    .thinking-indicator {{
        display: flex;
        align-items: center;
        color: #5f6368;
        font-style: italic;
        padding: 8px 25px;
    }}
    
    .dot-flashing {{
        position: relative;
        width: 10px;
        height: 10px;
        border-radius: 5px;
        background-color: var(--primary);
        color: var(--primary);
        animation: dotFlashing 1s infinite linear alternate;
        animation-delay: .5s;
        margin-right: 26px;
    }}
    
    .dot-flashing::before, .dot-flashing::after {{
        content: '';
        display: inline-block;
        position: absolute;
        top: 0;
        width: 10px;
        height: 10px;
        border-radius: 5px;
        background-color: var(--primary);
        color: var(--primary);
    }}
    
    .dot-flashing::before {{
        left: -15px;
        animation: dotFlashing 1s infinite alternate;
        animation-delay: 0s;
    }}
    
    .dot-flashing::after {{
        left: 15px;
        animation: dotFlashing 1s infinite alternate;
        animation-delay: 1s;
    }}
    
    @keyframes dotFlashing {{
        0% {{ opacity: 0.6; transform: translateY(2px); }}
        100% {{ opacity: 1; transform: translateY(-2px); }}
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# Constants
API_BASE_URL = os.environ.get("CO2OPS_API_URL", "http://127.0.0.1:8080")
APP_NAME = "co2ops_agent"

# Initialize session state variables
if "user_id" not in st.session_state:
    st.session_state.user_id = f"user-{uuid.uuid4()}"
    
if "session_id" not in st.session_state:
    st.session_state.session_id = None
    
if "messages" not in st.session_state:
    st.session_state.messages = []

if "thinking" not in st.session_state:
    st.session_state.thinking = False

def create_session():
    session_id = f"session-{int(time.time())}"
    response = requests.post(
        f"{API_BASE_URL}/apps/{APP_NAME}/users/{st.session_state.user_id}/sessions/{session_id}",
        headers={"Content-Type": "application/json"},
        data=json.dumps({})
    )
    
    if response.status_code == 200:
        st.session_state.session_id = session_id
        st.session_state.messages = []
        st.rerun()
        return True
    else:
        st.error(f"Failed to create session: {response.text}")
        return False

def send_message(message):
    if not st.session_state.session_id:
        st.error("No active session. Please create a session first.")
        return None

    # Send message to API
    response = requests.post(
        f"{API_BASE_URL}/run",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "app_name": APP_NAME,
            "user_id": st.session_state.user_id,
            "session_id": st.session_state.session_id,
            "new_message": {
                "role": "user",
                "parts": [{"text": message}]
            }
        })
    )

    # st.session_state.thinking = False

    if response.status_code != 200:
        st.error(f"Error: {response.text}")
        return None

    # Process the response
    events = response.json()
    assistant_message = ""
    for item in events:
        parts = item.get("content", {}).get("parts", [])
        for part in parts:
            if not part.get("functionResponse") and part.get("text"):
                assistant_message += part.get("text")

    return assistant_message


# UI Components
st.title("🌱 CO2Ops Agent Chat")
st.caption("Sustainable Cloud Operations powered by Google ADK")

# Sidebar for session management
with st.sidebar:
    st.header("Session Management")
    st.markdown(f"**User ID:** `{st.session_state.user_id[:8]}...`")
    
    if st.session_state.session_id:
        st.warning(f"**Active Session:** `{st.session_state.session_id}`")
        if st.button("🔄 New Session", use_container_width=True):
            create_session()
    else:
        st.warning("No active session")
        if st.button("➕ Create Session", use_container_width=True):
            create_session()
    
    st.divider()
    st.caption("Powered by Google Agent Development Kit")
    st.caption("Reduce cloud costs and carbon emissions through AI-driven optimization")

# Display chat messages
for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "🌱"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# Handle user input
if st.session_state.session_id:
    prompt = st.chat_input("Ask about cost savings or carbon reduction...")
    if prompt:
        # Immediately show user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Queue message for backend call in next run
        st.session_state.pending_message = prompt
        st.session_state.thinking = True
        st.rerun()
else:
    st.info("👈🏾 Create a session to start chatting with CO2Ops")

# Step 1: Show thinking animation while message is pending
if "pending_message" in st.session_state and st.session_state.get("thinking", False):
    with st.chat_message("assistant", avatar="🌱"):
        st.markdown(
            '<div class="thinking-indicator">'
            '<div class="dot-flashing"></div>'
            'Working on your request...'
            '</div>',
            unsafe_allow_html=True
        )
    # Set a short delay to render the animation
    time.sleep(1)
    # Now trigger the actual call
    st.session_state.thinking = False  # Let next run do the processing
    st.rerun()

# Step 2: Send message to backend and show response
if "pending_message" in st.session_state and not st.session_state.get("thinking", False):
    user_msg = st.session_state.pending_message
    del st.session_state.pending_message

    assistant_response = send_message(user_msg)
    if assistant_response:
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})

    st.rerun()


# Add Google-style footer
st.markdown(
    """
    <div style="text-align: center; padding: 16px; color: #5f6368; font-size: 0.8rem;position: fixed;bottom: 0;">
        Google Cloud Sustainability | Agent Development Kit | CO2Ops v1.0
    </div>
    """,
    unsafe_allow_html=True
)