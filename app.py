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

st.title("⚜️ Scout AI - Ultimate Control Panel V4.1")

# --- FETCH DATA ---
def get_categories():
    try: return [item["name"] for item in supabase.table("categories").select("name").execute().data]
    except: return ["General"]

def get_kb_data():
    try: return supabase.table("knowledge_base").select("*").order("id").execute().data
    except: return []

categories_list = get_categories()

# --- DASHBOARD TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📄 Add Content", "🗂️ Manage Data", "🤖 AI & Greeting", "🎛️ Interactive Menus", "💬 Test Bot"
])

# ==========================================
# TAB 1 & 2: CONTENT UPLOAD & DB EDITOR
# ==========================================
with tab1:
    st.header("Upload Files & FAQs")
    col1, col2 = st.columns(2)
    with col1:
        upload_category = st.selectbox("Category:", categories_list)
        uploaded_files = st.file_uploader("Upload PDF, TXT, Images", accept_multiple_files=True)
        if st.button("Save Uploads") and uploaded_files:
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
        faq_q = st.text_input("FAQ Question:")
        faq_a = st.text_area("FAQ Answer:")
        if st.button("Save FAQ") and faq_q and faq_a:
            supabase.table("knowledge_base").insert({"content": f"Q: {faq_q}\nA: {faq_a}", "category": upload_category, "source_type": "FAQ"}).execute()
            st.success("✅ FAQ Added!")

with tab2:
    st.header("Database Editor")
    kb_data = get_kb_data()
    if kb_data:
        st.dataframe(pd.DataFrame(kb_data), use_container_width=True)
        colA, colB = st.columns(2)
        with colA:
            edit_id = st.number_input("ID to Edit:", min_value=0, step=1)
            new_content = st.text_area("New Content:", height=100)
            if st.button("📝 Update Entry"):
                supabase.table("knowledge_base").update({"content": new_content}).eq("id", edit_id).execute()
                st.rerun()
        with colB:
            delete_id = st.number_input("ID to Delete:", min_value=0, step=1)
            if st.button("❌ Delete Entry", type="primary"):
                supabase.table("knowledge_base").delete().eq("id", delete_id).execute()
                st.rerun()

# ==========================================
# TAB 3: AI PERSONA & GREETING
# ==========================================
with tab3:
    st.header("Bot Configuration")
    try:
        config_data = supabase.table("bot_config").select("*").eq("id", 1).execute().data[0]
        curr_persona = config_data.get("persona_prompt", "")
        curr_greet = config_data.get("greeting_message", "")
    except: 
        curr_persona, curr_greet = "", ""
    
    new_greet = st.text_area("Greeting Message (Sent when user clicks /start):", value=curr_greet, height=100)
    new_persona = st.text_area("AI System Prompt:", value=curr_persona, height=200)
    
    if st.button("Update Bot Settings"):
        supabase.table("bot_config").update({"greeting_message": new_greet, "persona_prompt": new_persona}).eq("id", 1).execute()
        st.success("✅ Settings Updated!")

# ==========================================
# TAB 4: INTERACTIVE MENU BUILDER 
# ==========================================
with tab4:
    st.header("Build & Edit Bot Menus")
    st.markdown("Create nested buttons with 3 options: Submenu, AI Generation, or Specific Text.")
    
    try:
        menus_response = supabase.table("bot_menus").select("*").order("id").execute()
        menus = menus_response.data if menus_response.data else []
        
        if menus:
            st.dataframe(pd.DataFrame(menus), use_container_width=True)
        else:
            st.info("No menus found. Create your first Main Menu button below!")
            
        st.divider()
        colM1, colM2 = st.columns(2)
        
        menu_options = {"0": "None (Main Menu)"}
        for m in menus: menu_options[str(m["id"])] = f"ID: {m['id']} - {m['button_text']}"
        
        with colM1:
            st.subheader("➕ Add New Button")
            parent_sel = st.selectbox("Select Parent Menu:", options=list(menu_options.keys()), format_func=lambda x: menu_options[x], key="add_parent")
            btn_text = st.text_input("Button Text:", key="add_text")
            
            # The 3 Options!
            act_type = st.radio("When user clicks this button:", ["Open Submenu (submenu)", "Generate AI Answer (ai_reply)", "Send Specific Text (static_text)"], key="add_act")
            
            reply_prmpt = ""
            if "ai_reply" in act_type:
                reply_prmpt = st.text_area("Hidden AI Prompt:", key="add_prmpt")
            elif "static_text" in act_type:
                reply_prmpt = st.text_area("Exact Text to Send:", key="add_static")
            
            if st.button("➕ Add Button", type="primary"):
                if btn_text:
                    parent_val = int(parent_sel) if parent_sel != "0" else None
                    if "submenu" in act_type: action_val = "submenu"
                    elif "ai_reply" in act_type: action_val = "ai_reply"
                    else: action_val = "static_text"
                    
                    supabase.table("bot_menus").insert({
                        "parent_id": parent_val, "button_text": btn_text, 
                        "action_type": action_val, "reply_prompt": reply_prmpt
                    }).execute()
                    st.rerun()
        
        with colM2:
            st.subheader("✏️ Edit Existing Button")
            if menus:
                edit_id = st.selectbox("Select ID to Edit:", [m["id"] for m in menus], key="edit_id")
                curr_menu = next((m for m in menus if m["id"] == edit_id), None)
                
                if curr_menu:
                    curr_parent_str = str(curr_menu["parent_id"]) if curr_menu["parent_id"] else "0"
                    parent_opts_list = list(menu_options.keys())
                    p_idx = parent_opts_list.index(curr_parent_str) if curr_parent_str in parent_opts_list else 0
                    
                    new_parent_sel = st.selectbox("New Parent Menu:", options=parent_opts_list, format_func=lambda x: menu_options[x], index=p_idx, key="edit_parent")
                    new_btn_text = st.text_input("New Button Text:", value=curr_menu["button_text"], key="edit_text")
                    
                    # Logic to highlight the correct option when editing
                    a_idx = 0
                    if curr_menu["action_type"] == "ai_reply": a_idx = 1
                    elif curr_menu["action_type"] == "static_text": a_idx = 2
                        
                    new_act_type = st.radio("New Action Type:", ["Open Submenu (submenu)", "Generate AI Answer (ai_reply)", "Send Specific Text (static_text)"], index=a_idx, key="edit_act")
                    
                    new_reply_prmpt = ""
                    if "ai_reply" in new_act_type:
                        new_reply_prmpt = st.text_area("New Hidden AI Prompt:", value=curr_menu.get("reply_prompt") or "", key="edit_prmpt")
                    elif "static_text" in new_act_type:
                        new_reply_prmpt = st.text_area("Exact Text to Send:", value=curr_menu.get("reply_prompt") or "", key="edit_static")
                    
                    if st.button("📝 Save Changes"):
                        p_val = int(new_parent_sel) if new_parent_sel != "0" else None
                        if "submenu" in new_act_type: a_val = "submenu"
                        elif "ai_reply" in new_act_type: a_val = "ai_reply"
                        else: a_val = "static_text"
                        
                        supabase.table("bot_menus").update({
                            "parent_id": p_val, "button_text": new_btn_text,
                            "action_type": a_val, "reply_prompt": new_reply_prmpt
                        }).eq("id", edit_id).execute()
                        st.success("✅ Button Updated!")
                        st.rerun()
                
                st.divider()
                st.subheader("❌ Delete Button")
                del_menu_id = st.selectbox("Select ID to Delete:", [m["id"] for m in menus], key="del_id")
                if st.button("Delete Selected Button"):
                    supabase.table("bot_menus").delete().eq("id", del_menu_id).execute()
                    st.rerun()

    except Exception as e:
        st.error(f"Error loading menus: {e}")

# ==========================================
# TAB 5: TEST BOT SIMULATOR
# ==========================================
with tab5:
    st.header("💬 Live Bot Testing")
    if "messages" not in st.session_state: st.session_state.messages = []
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if prompt := st.chat_input("Ask the scout assistant..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        kb_raw = get_kb_data()
        kb_text = "\n".join([f"[{i['category']}] {i['content']}" for i in kb_raw]) if kb_raw else "No data."
        strict_prompt = f"{curr_persona}\nKNOWLEDGE BASE:\n{kb_text}\nUSER QUESTION: {prompt}"

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = client.models.generate_content(model='gemini-2.5-flash', contents=strict_prompt)
                    st.markdown(response.text.strip())
                    st.session_state.messages.append({"role": "assistant", "content": response.text.strip()})
                except Exception as e:
                    st.error(f"Error: {e}")
