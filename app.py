import streamlit as st
import pandas as pd
import PyPDF2
from PIL import Image
from supabase import create_client, Client
from google import genai
import io

# --- SECRETS ---
try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"Missing Secret Key: {e}")
    st.stop()

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

st.title("⚙️ AI Design Center - Control Panel V2")

# --- DASHBOARD TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📄 Upload Files", "❓ Add FAQs", "🤖 AI Persona Setup", "🗄️ Database View"])

# --- TAB 1: UPLOAD FILES ---
with tab1:
    st.header("Upload Documents & Assets")
    upload_category = st.selectbox("Select Category for Upload:", ["Livestreaming App", "Design Assets", "General Data", "Technical Rules"])
    uploaded_files = st.file_uploader("Upload PDF, CSV, TXT, or Images", accept_multiple_files=True)

    if st.button("Process & Save Uploads"):
        if uploaded_files:
            with st.spinner("Extracting and saving..."):
                for file in uploaded_files:
                    kb_text = ""
                    if file.name.endswith('.pdf'):
                        for page in PyPDF2.PdfReader(file).pages:
                            if page.extract_text(): kb_text += page.extract_text() + "\n"
                    elif file.name.endswith('.csv'):
                        kb_text += pd.read_csv(file).to_string() + "\n"
                    elif file.name.endswith('.txt'):
                        kb_text += file.getvalue().decode('utf-8') + "\n"
                    elif file.name.endswith(('.png', '.jpg', '.jpeg')):
                        response = client.models.generate_content(
                            model='gemini-2.5-flash', 
                            contents=["Describe this image in high detail.", Image.open(file)]
                        )
                        kb_text += f"[Image Description: {response.text}]\n"
                    
                    if kb_text:
                        supabase.table("knowledge_base").insert({
                            "content": kb_text, 
                            "category": upload_category,
                            "source_type": "Document"
                        }).execute()
                st.success("✅ Files saved successfully!")

# --- TAB 2: MANUAL FAQs ---
with tab2:
    st.header("Add Custom FAQ")
    st.markdown("Use this to manually type specific rules or answers you want the bot to know perfectly.")
    faq_category = st.selectbox("FAQ Category:", ["Livestreaming App", "Design Assets", "General Data", "Technical Rules"])
    faq_q = st.text_input("Question:")
    faq_a = st.text_area("Answer:")
    
    if st.button("Save FAQ to Database"):
        if faq_q and faq_a:
            combined_faq = f"Q: {faq_q}\nA: {faq_a}"
            supabase.table("knowledge_base").insert({
                "content": combined_faq,
                "category": faq_category,
                "source_type": "FAQ"
            }).execute()
            st.success("✅ FAQ Added!")
        else:
            st.warning("Please fill out both the question and answer.")

# --- TAB 3: AI PERSONA ---
with tab3:
    st.header("Adjust AI Behavior")
    st.markdown("Give the AI instructions on how to talk, what language to use, and how strict it should be.")
    
    # Fetch current persona
    current_persona = supabase.table("bot_config").select("persona_prompt").eq("id", 1).execute().data[0]["persona_prompt"]
    
    new_persona = st.text_area("System Prompt / Persona:", value=current_persona, height=200)
    
    if st.button("Update AI Persona"):
        supabase.table("bot_config").update({"persona_prompt": new_persona}).eq("id", 1).execute()
        st.success("✅ AI Behavior Updated! The bot will now follow these instructions.")

# --- TAB 4: DATABASE VIEW ---
with tab4:
    st.header("Current Knowledge Base")
    if st.button("Refresh Database View"):
        data = supabase.table("knowledge_base").select("*").execute().data
        if data:
            st.dataframe(pd.DataFrame(data))
        else:
            st.info("Database is empty.")
