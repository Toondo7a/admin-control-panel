import streamlit as st
import pandas as pd
import PyPDF2
from PIL import Image
from supabase import create_client, Client
from google import genai
import os
import io

# --- SECRETS ---
ADMIN_PASSWORD = "mysecretpassword123"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- LOGIN ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    pwd = st.text_input("Enter Admin Password", type="password")
    if pwd == ADMIN_PASSWORD:
        st.session_state.logged_in = True
        st.rerun()
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

st.title("⚙️ Admin Knowledge Base Panel")

st.header("Upload Files (PDF, CSV, TXT, Images)")
uploaded_files = st.file_uploader("Upload files here", accept_multiple_files=True)

if st.button("Process & Save to Database"):
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
if st.button("Refresh Database View"):
    data = supabase.table("knowledge_base").select("*").execute().data
    st.dataframe(pd.DataFrame(data))
    if st.button("⚠️ DELETE ALL DATA"):
        supabase.table("knowledge_base").delete().neq("id", 0).execute()
        st.rerun()
