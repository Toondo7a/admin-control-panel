import streamlit as st
import pandas as pd
import PyPDF2
from PIL import Image
from supabase import create_client, Client
from google import genai
import io

# --- SECRETS (STREAMLIT NATIVE WAY) ---
# This safely checks if your secrets exist in the Advanced Settings
try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"❌ Missing Secret Key: {e}. Please check your Streamlit Advanced Settings!")
    st.stop()

# --- LOGIN ---
if "logged_in" not in st.session_state: 
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.warning("🔒 Secure Admin Panel")
    pwd = st.text_input("Enter Admin Password", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.session_state.logged_in = True
        st.rerun()
    elif pwd:
        st.error("Incorrect Password")
    st.stop()

# --- INITIALIZE CLIENTS ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

st.title("⚙️ Admin Knowledge Base Panel")

# --- UPLOAD SECTION ---
st.header("Upload Files (PDF, CSV, TXT, Images)")
uploaded_files = st.file_uploader("Upload files here", accept_multiple_files=True)

if st.button("Process & Save to Database"):
    if not uploaded_files:
        st.warning("Please upload a file first.")
    else:
        with st.spinner("Extracting and saving..."):
            for file in uploaded_files:
                kb_text = ""
                if file.name.endswith('.pdf'):
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted: kb_text += extracted + "\n"
                elif file.name.endswith('.csv'):
                    df = pd.read_csv(file)
                    kb_text += df.to_string() + "\n"
                elif file.name.endswith('.txt'):
                    kb_text += file.getvalue().decode('utf-8') + "\n"
                elif file.name.endswith(('.png', '.jpg', '.jpeg')):
                    image = Image.open(file)
                    response = client.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=["Describe this image in high detail for a database.", image]
                    )
                    kb_text += f"[Image Description: {response.text}]\n"
                
                if kb_text:
                    supabase.table("knowledge_base").insert({"content": kb_text}).execute()
            st.success("✅ Saved permanently to Supabase!")

st.divider()

# --- VIEW DATABASE SECTION ---
if st.button("Refresh Database View"):
    try:
        data = supabase.table("knowledge_base").select("*").execute().data
        if data:
            st.dataframe(pd.DataFrame(data))
        else:
            st.info("Database is empty.")
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        
    if st.button("⚠️ DELETE ALL DATA"):
        supabase.table("knowledge_base").delete().neq("id", 0).execute()
        st.success("Database wiped.")
        st.rerun()
