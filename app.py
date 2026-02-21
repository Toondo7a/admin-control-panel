import streamlit as st
import pandas as pd
import PyPDF2
from PIL import Image
from supabase import create_client, Client
from google import genai
import io

st.set_page_config(page_title="Scout AI Control Panel", layout="wide")

# --- SECRETS & LOGIN ---
try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"Missing Secret Key: {e}")
    st.stop()

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    pwd = st.text_input("Enter Admin Password", type="password")
    if pwd == ADMIN_PASSWORD:
        st.session_state.logged_in = True
        st.rerun()
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

st.title("⚜️ Scout AI - Ultimate Control Panel V3")

# --- FETCH DYNAMIC DATA ---
def get_categories():
    try:
        data = supabase.table("categories").select("name").execute().data
        return [item["name"] for item in data]
    except: return ["General"]

def get_kb_data():
    try:
        return supabase.table("knowledge_base").select("*").order("id").execute().data
    except: return []

categories_list = get_categories()

# --- DASHBOARD TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📄 Add Content", "🗂️ Manage Knowledge Base", "🏷️ Categories", "🤖 AI Persona", "💬 Test Bot"
])

# ==========================================
# TAB 1: ADD CONTENT (Uploads & FAQs)
# ==========================================
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.header("Upload Files")
        upload_category = st.selectbox("Category:", categories_list, key="up_cat")
        uploaded_files = st.file_uploader("Upload PDF, CSV, TXT, or Images", accept_multiple_files=True)
        if st.button("Process & Save Uploads"):
            if uploaded_files:
                with st.spinner("Saving to database..."):
                    for file in uploaded_files:
                        kb_text = ""
                        if file.name.endswith('.pdf'):
                            for page in PyPDF2.PdfReader(file).pages:
                                if page.extract_text(): kb_text += page.extract_text() + "\n"
                        elif file.name.endswith('.txt'):
                            kb_text += file.getvalue().decode('utf-8') + "\n"
                        if kb_text:
                            supabase.table("knowledge_base").insert({"content": kb_text, "category": upload_category, "source_type": "Document"}).execute()
                    st.success("✅ Files saved!")
    
    with col2:
        st.header("Add Manual FAQ / Rule")
        faq_category = st.selectbox("Category:", categories_list, key="faq_cat")
        faq_q = st.text_input("Question / Topic:")
        faq_a = st.text_area("Answer / Details:")
        if st.button("Save Manual Entry"):
            if faq_q and faq_a:
                supabase.table("knowledge_base").insert({"content": f"Q: {faq_q}\nA: {faq_a}", "category": faq_category, "source_type": "FAQ"}).execute()
                st.success("✅ FAQ Added!")

# ==========================================
# TAB 2: MANAGE KNOWLEDGE BASE (Edit/Delete)
# ==========================================
with tab2:
    st.header("Database Editor")
    kb_data = get_kb_data()
    
    if kb_data:
        df = pd.DataFrame(kb_data)
        st.dataframe(df, use_container_width=True)
        
        st.divider()
        st.subheader("Edit or Delete an Entry")
        colA, colB = st.columns(2)
        
        with colA:
            edit_id = st.number_input("Enter ID to Edit:", min_value=0, step=1)
            new_content = st.text_area("New Content for this ID:", height=150)
            if st.button("📝 Update Entry"):
                supabase.table("knowledge_base").update({"content": new_content}).eq("id", edit_id).execute()
                st.success(f"ID {edit_id} updated!")
                st.rerun()
                
        with colB:
            delete_id = st.number_input("Enter ID to Delete:", min_value=0, step=1)
            if st.button("❌ Delete Entry", type="primary"):
                supabase.table("knowledge_base").delete().eq("id", delete_id).execute()
                st.warning(f"ID {delete_id} deleted!")
                st.rerun()
    else:
        st.info("Database is empty.")

# ==========================================
# TAB 3: CATEGORIES
# ==========================================
with tab3:
    st.header("Manage Categories")
    st.write("Current Categories:", ", ".join(categories_list))
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        new_cat = st.text_input("Add New Category:")
        if st.button("Add Category"):
            if new_cat:
                supabase.table("categories").insert({"name": new_cat}).execute()
                st.success("Added!")
                st.rerun()
    with col_c2:
        del_cat = st.selectbox("Delete Category:", categories_list)
        if st.button("Delete Category"):
            supabase.table("categories").delete().eq("name", del_cat).execute()
            st.warning("Deleted!")
            st.rerun()

# ==========================================
# TAB 4: AI PERSONA
# ==========================================
with tab4:
    st.header("Adjust AI Persona")
    try:
        current_persona = supabase.table("bot_config").select("persona_prompt").eq("id", 1).execute().data[0]["persona_prompt"]
    except: current_persona = "You are a helpful assistant."
    
    new_persona = st.text_area("System Prompt:", value=current_persona, height=250)
    if st.button("Update AI Persona"):
        supabase.table("bot_config").update({"persona_prompt": new_persona}).eq("id", 1).execute()
        st.success("✅ Persona Updated!")

# ==========================================
# TAB 5: TEST BOT SIMULATOR
# ==========================================
with tab5:
    st.header("💬 Live Bot Testing")
    st.markdown("Test the bot exactly as it behaves on Telegram, using your live database.")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Ask the scout assistant..."):
        # Add user message to UI
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        # Assemble context from DB
        kb_raw = get_kb_data()
        kb_text = "\n".join([f"[{i['category']}] {i['content']}" for i in kb_raw]) if kb_raw else "No knowledge base data."
        
        try:
            persona = supabase.table("bot_config").select("persona_prompt").eq("id", 1).execute().data[0]["persona_prompt"]
        except: persona = "You are a helpful assistant."

        strict_prompt = f"""
        {persona}
        RULES:
        1. Answer the user's question relying primarily on the Knowledge Base below. 
        2. If the user's question cannot be answered using the Knowledge Base, reply exactly with: "NOT_FOUND_IN_KB".
        3. Always reply in the language the user speaks.
        
        KNOWLEDGE BASE:
        {kb_text}
        
        USER QUESTION: {prompt}
        """

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = client.models.generate_content(model='gemini-2.5-flash', contents=strict_prompt)
                    bot_reply = response.text.strip()
                    
                    if "NOT_FOUND_IN_KB" in bot_reply:
                        st.markdown("*عذراً، لا أملك هذه المعلومة في قاعدة بياناتي. (Simulated Google Search Prompt)*")
                        st.session_state.messages.append({"role": "assistant", "content": "*[Bot triggered Google Search Fallback]*"})
                    else:
                        st.markdown(bot_reply)
                        st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                except Exception as e:
                    st.error(f"Error: {e}")
