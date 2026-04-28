# import streamlit as st
# import json
# import os
# import re
# from langchain_groq import ChatGroq
# from langchain_core.prompts import ChatPromptTemplate

# # ----------------------------
# # SET YOUR GROQ API KEY
# # ----------------------------


# llm = ChatGroq(
#     model_name="llama-3.3-70b-versatile",
#     temperature=0.2
# )

# # ----------------------------
# # INITIAL RESUME STRUCTURE
# # ----------------------------
# if "resume" not in st.session_state:
#     st.session_state.resume = {
#         "name": "",
#         "email": "",
#         "phone": "",
#         "summary": "",
#         "skills": "",
#         "experience": "",
#         "projects": "",
#         "education": ""
#     }

# # ----------------------------
# # PROMPT
# # ----------------------------
# prompt = ChatPromptTemplate.from_messages([
#     ("system",
#      "You are a resume editing assistant. "
#      "Return ONLY raw JSON. "
#      "No markdown. "
#      "No explanation. "
#      "Valid JSON only. "
#      "Extract which section the user wants to update "
#      "and return JSON with keys: section and content. "
#      "Do NOT invent information."
#     ),
#     ("human",
#      "Current Resume:\n{resume}\n\nUser Message:\n{message}"
#     )
# ])

# chain = prompt | llm

# # ----------------------------
# # PAGE LAYOUT
# # ----------------------------
# st.set_page_config(layout="wide")
# left, right = st.columns(2)

# # ----------------------------
# # LEFT SIDE - CHAT
# # ----------------------------
# with left:
#     st.title("Resume Chat Editor")

#     user_input = st.text_area("Talk to your resume:")

#     if st.button("Update Resume"):
#         if user_input.strip() == "":
#             st.warning("Please enter something.")
#         else:
#             response = chain.invoke({
#                 "resume": json.dumps(st.session_state.resume),
#                 "message": user_input
#             })

#             raw_output = response.content.strip()

#             # Remove markdown if model adds it
#             raw_output = re.sub(r"```json", "", raw_output)
#             raw_output = re.sub(r"```", "", raw_output)

#             try:
#                 parsed = json.loads(raw_output)

#                 section = parsed.get("section")
#                 content = parsed.get("content")

#                 if section in st.session_state.resume:
#                     st.session_state.resume[section] = content
#                     st.success(f"{section} updated successfully!")
#                 else:
#                     st.error("Invalid section returned by model.")
#                     st.code(raw_output)

#             except Exception as e:
#                 st.error("Could not process update.")
#                 st.code(raw_output)

# # ----------------------------
# # RIGHT SIDE - LIVE RESUME VIEW
# # ----------------------------
# with right:
#     st.title("Live Resume Preview")

#     resume = st.session_state.resume

#     st.markdown(f"## {resume['name']}")
#     st.markdown(f"**Email:** {resume['email']}")
#     st.markdown(f"**Phone:** {resume['phone']}")

#     st.markdown("---")

#     st.markdown("### Summary")
#     st.write(resume["summary"])

#     st.markdown("### Skills")
#     st.write(resume["skills"])

#     st.markdown("### Experience")
#     st.write(resume["experience"])

#     st.markdown("### Projects")
#     st.write(resume["projects"])

#     st.markdown("### Education")
#     st.write(resume["education"])


import streamlit as st
import os
import re
from langchain_groq import ChatGroq
import json
import sqlite3
import markdown
from langchain_core.prompts import ChatPromptTemplate
import streamlit.components.v1 as components
from dotenv import load_dotenv
load_dotenv() # This loads the key from your .env file
# ----------------------------
# 1. CONFIGURATION & SECRETS
# ----------------------------
# Set your API key securely via environment variables or Streamlit secrets
# e.g., os.environ["GROQ_API_KEY"] = "your_secure_key"

api_key = os.getenv("GROQ_API_KEY")

llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0.1, # Lowered temperature slightly for more deterministic routing/formatting
    groq_api_key=api_key
)

# ----------------------------
# 2. STATE & ALLOWED SECTIONS
# ----------------------------
ALLOWED_SECTIONS = [
    "name", "email", "phone", "linkedin", "github", 
    "summary", "skills", "experience", "projects", 
    "education", "achievements", "extracurriculars"
]

if "resume" not in st.session_state:
    st.session_state.resume = {sec: "" for sec in ALLOWED_SECTIONS}


# ----------------------------
# 2.5 DATABASE MANAGEMENT (SQLite)
# ----------------------------
DB_FILE = "resumes_manager.db"

def init_db():
    """Initializes the database schema if it does not exist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # We dynamically create columns based on your ALLOWED_SECTIONS.
    # profile_name is our unique identifier for different resumes.
    columns_def = ", ".join([f"{sec} TEXT" for sec in ALLOWED_SECTIONS])
    
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_name TEXT UNIQUE,
            {columns_def}
        )
    ''')
    conn.commit()
    conn.close()

def save_resume_to_db(profile_name, resume_data):
    """Inserts a new resume or updates an existing one using SQLite UPSERT."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    columns = ['profile_name'] + ALLOWED_SECTIONS
    placeholders = ', '.join(['?'] * len(columns))
    
    # Prepare the update logic for existing records
    updates = ', '.join([f"{sec} = excluded.{sec}" for sec in ALLOWED_SECTIONS])
    
    values = [profile_name] + [resume_data.get(sec, "") for sec in ALLOWED_SECTIONS]
    
    # SQLite UPSERT logic (ON CONFLICT)
    query = f'''
        INSERT INTO resumes ({', '.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(profile_name) DO UPDATE SET {updates}
    '''
    
    c.execute(query, values)
    conn.commit()
    conn.close()

def load_resume_from_db(profile_name):
    """Retrieves a specific resume from the database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Query specific columns to ensure dict mapping is exact
    columns = ", ".join(ALLOWED_SECTIONS)
    c.execute(f"SELECT {columns} FROM resumes WHERE profile_name = ?", (profile_name,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {ALLOWED_SECTIONS[i]: (row[i] if row[i] else "") for i in range(len(ALLOWED_SECTIONS))}
    return None

def get_all_profile_names():
    """Fetches all saved resume profile names for the UI dropdown."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT profile_name FROM resumes")
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def delete_resume_from_db(profile_name):
    """Deletes a resume profile."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM resumes WHERE profile_name = ?", (profile_name,))
    if c.fetchone():
        c.execute("DELETE FROM resumes WHERE profile_name = ?", (profile_name,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

# Initialize the database on script run
init_db()
# ----------------------------
# 3. PROMPTS (ROUTER & EXTRACTOR)
# ----------------------------

# The Router: ONLY decides the section. Strictly locked down.
# The Bulletproof Intent Router
router_prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are a strict Intent Classification Router for a resume application.\n\n"

     "TASK:\n"
     "Identify which resume sections the user wants to ADD, UPDATE, REMOVE, or MODIFY.\n\n"

     f"ALLOWED SECTIONS:\n{', '.join(ALLOWED_SECTIONS)}\n\n"

     "SECTION DEFINITIONS:\n"
     "- name: full name of person\n"
     "- email: email address\n"
     "- phone: phone number\n"
     "- summary: about me, profile, career objective\n"
     "- skills: technologies, tools, programming languages\n"
     "- education: degrees, colleges, academic history\n"
     "- experience: jobs, internships, work history\n"
     "- projects: personal or professional projects\n"
     "- github: github username or profile\n"
     "- achievements: awards, certifications, rankings\n"
     "- extracurriculars: activities, leadership, clubs\n\n"

     "CRITICAL RULES:\n"
     "1. Focus on INTENT, not keywords.\n"
     "2. Ignore negations completely.\n"
     "3. MULTI-INTENT: Return ALL valid sections if multiple are present.\n"
     "4. UNSTRUCTURED INPUT: Extract ALL detectable sections from raw text.\n"
     "5. DO NOT guess missing sections.\n"
     "6. If nothing matches, return: unknown\n\n"

     "STRICT OUTPUT FORMAT:\n"
     "- lowercase only\n"
     "- only allowed section names\n"
     "- no duplicates\n"
     "- comma + single space separated\n"
     "- no explanation\n\n"

     "VALID OUTPUT EXAMPLES:\n"
     "skills\n"
     "email, phone\n"
     "experience, projects\n"
     "unknown\n\n"

     "INVALID OUTPUT EXAMPLES:\n"
     "Skills\n"
     "skills,projects\n"
     "The answer is skills\n"
    ),
    ("human", "{message}")
])

# Section-specific formatting guidelines to guarantee professional output
SECTION_GUIDELINES = {
    "name": "Output ONLY the full name. No prefixes.",
    "email": "Output ONLY the email address.",
    "phone": "Output ONLY the phone number.",
    "summary": "Write a highly concise, 2-sentence professional summary.",
    "skills": "Output a single, comma-separated list of skills (e.g., Python, C++, Pandas). DO NOT use bullet points or newlines.",
    "experience": "Format strictly using Markdown. \nLine 1: **Job Title** | *Company*\nNext lines: Use `- ` for bullet points. \nCRITICAL: DO NOT start with the word 'Experience'.",
    "projects": "Format strictly using Markdown. \nLine 1: **Project Title**\nNext lines: Use `- ` for bullet points detailing tech stack and impact. \nCRITICAL: DO NOT start with the word 'Projects'.",
    "education": "Format strictly using Markdown: **Degree**, Institution, Year. If the institution or year is missing, just format what you have (e.g., **Degree**).",
    "github": "Extract the GitHub ID or URL. Output ONLY a clean URL format (e.g., github.com/username). Do not include https://.",
    "achievements": "Format strictly using Markdown. Use `- ` for bullet points describing awards, competition rankings (e.g., hackathons, coding platforms), or certifications. CRITICAL: DO NOT start with the section name.",
    "extracurriculars": "Format strictly using Markdown. Use `- ` for bullet points describing roles, organizations, and impact. CRITICAL: DO NOT start with the section name."
}
reviewer_prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are a strict QA Auditor for the '{section}' section.\n\n"

     "Your job is to VERIFY and CLEAN the generated draft.\n\n"

     "CRITICAL RULES:\n"

     "1. IDENTITY FIELDS (name, email, phone, github, linkedin):\n"
     "- Always ACCEPT replacement\n"
     "- Return the draft EXACTLY as is\n\n"

     "2. CONTENT FIELDS:\n"
     "- NEVER delete existing valid content\n"
     "- Ensure new content is relevant to the section\n\n"

     "3. HALLUCINATION CHECK:\n"
     "- Remove ANY detail not present in user input\n"
     "- Remove fake metrics, dates, tools\n\n"

     "4. STRICT VALIDATION:\n"
     "- If new input does NOT belong to this section → return NO_CHANGE\n"
     "- If draft adds nothing meaningful → return NO_CHANGE\n\n"

     "5. OUTPUT RULES:\n"
     "- Return ONLY final cleaned content OR NO_CHANGE\n"
     "- No explanation\n"
    ),
    ("human", 
     "Section: {section}\n\n"
     "Existing Content:\n{current_content}\n\n"
     "User Input:\n{message}\n\n"
     "Generated Draft:\n{draft}"
    )
])
reviewer_chain = reviewer_prompt | llm
extractor_prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are a strict resume section editor for the '{section}' section.\n\n"

     "FORMATTING RULE:\n{guideline}\n\n"

     "CRITICAL RULES:\n"

     "1. IDENTITY FIELDS (name, email, phone, github, linkedin):\n"
     "- Completely REPLACE existing content\n"
     "- Extract ONLY the exact value from user input\n"
     "- Do NOT merge or infer\n\n"

     "2. CONTENT FIELDS (skills, experience, projects, summary, etc.):\n"
     "- PRESERVE all existing content\n"
     "- ADD new information only if clearly provided\n"
     "- Do NOT remove old content unless explicitly asked\n\n"

     "3. NO HALLUCINATION:\n"
     "- Do NOT add dates, metrics, tools, or details not mentioned\n"
     "- Do NOT improve or exaggerate content\n\n"

     "4. STRICT EDITING:\n"
     "- Only modify what the user asked\n"
     "- If input is irrelevant, return the original content unchanged\n\n"

     "5. OUTPUT RULES:\n"
     "- No section headers\n"
     "- No explanation\n"
     "- Clean final formatted text only\n"
    ),
    ("human", 
     "Current Content:\n{current_content}\n\nUser Input:\n{message}"
    )
])
extractor_chain = extractor_prompt | llm

router_chain = router_prompt | llm


# ----------------------------
# 4. PAGE LAYOUT
# ----------------------------
st.set_page_config(layout="wide", page_title="AI Resume Editor")
left, right = st.columns(2)

with st.sidebar:
    st.title("Database Management")
    st.write("Manage multiple tailored resumes.")
    
    st.divider()
    
    # --- SAVE LOGIC ---
    st.subheader("Save Current Resume")
    profile_name_input = st.text_input("Profile Name (e.g., 'Backend Dev')", key="save_name")
    
    if st.button("Save to Database"):
        if profile_name_input.strip() == "":
            st.error("Please provide a profile name to save.")
        else:
            save_resume_to_db(profile_name_input.strip(), st.session_state.resume)
            st.success(f"Resume '{profile_name_input}' saved successfully.")
            
    st.divider()
    
    # --- LOAD/DELETE LOGIC ---
    st.subheader("Load / Delete Resume")
    available_profiles = get_all_profile_names()
    
    if available_profiles:
        selected_profile = st.selectbox("Select a profile", available_profiles)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Load Profile"):
                loaded_data = load_resume_from_db(selected_profile)
                if loaded_data:
                    st.session_state.resume = loaded_data
                    st.success(f"Loaded '{selected_profile}'!")
        
        with col2:
            if st.button("Delete Profile"):
                success = delete_resume_from_db(selected_profile)
                if success:
                    st.success(f"Deleted '{selected_profile}'.")
                    st.rerun() # Refresh the page to update the selectbox
    else:
        st.info("No resumes saved in the database yet.")
            
    st.divider()
    
    # --- CLEAR LOGIC ---
    if st.button("Clear Current Editor", type="primary"):
        st.session_state.resume = {sec: "" for sec in ALLOWED_SECTIONS}
        st.warning("Editor cleared. (Data in database remains safe).")
        
# ----------------------------
# LEFT SIDE - CHAT / LOGIC
# ----------------------------
with left:
    st.title("Resume Chat Editor")
    user_input = st.text_area("Talk to your resume (e.g., 'Add Python and AWS to my skills'):")

    if st.button("Update Resume"):
        if not api_key:
            st.error("API Key missing. Please set GROQ_API_KEY environment variable.")
        elif user_input.strip() == "":
            st.warning("Please enter something.")
        else:
            # STEP 1: Route Intents
            with st.spinner("Analyzing intent..."):
                router_response = router_chain.invoke({"message": user_input}).content.strip().lower()
                raw_sections = [s.strip() for s in router_response.split(',')]
                
                sections_to_update = [re.sub(r'[^a-z]', '', s) for s in raw_sections if re.sub(r'[^a-z]', '', s) in ALLOWED_SECTIONS]

            # STEP 2: Extract & Verify
            if sections_to_update:
                updated_any = False
                for section in sections_to_update:
                    with st.spinner(f"Drafting and Fact-Checking your **{section.title()}**..."):
                        
                        guideline = SECTION_GUIDELINES[section]
                        if section == "education":
                            guideline += " Expand acronyms accurately."

                        # Agent 1: The Drafter
                        draft_content = extractor_chain.invoke({
                            "section": section,
                            "guideline": guideline,
                            "current_content": st.session_state.resume[section],
                            "message": user_input
                        }).content.strip()

                        # Agent 2: The Fact-Checker
                        final_content = reviewer_chain.invoke({
                            "section": section,
                            "current_content": st.session_state.resume[section], 
                            "message": user_input,
                            "draft": draft_content
                        }).content.strip()

                        # Catch our new strict fail-safes
                        if "NO_CHANGE" in final_content or final_content == "REJECT":
                            continue # Skip updating this section
                            
                        # Catch lingering chatty behavior just in case
                        if final_content.startswith("Since the") or final_content.startswith("There is no"):
                            continue

                        # Strip stray markdown blocks just in case
                        final_content = re.sub(r"^```[a-zA-Z]*\n", "", final_content)
                        final_content = re.sub(r"\n```$", "", final_content)

                        # Only update if it passes the audit
                        st.session_state.resume[section] = final_content
                        updated_any = True
                
                if updated_any:
                    st.success(f"Successfully processed your request!")
                else:
                    st.warning("No valid resume updates were found in your text based on the sections analyzed.")

# ----------------------------
# RIGHT SIDE - LIVE PREVIEW (A4 PDF STYLE)
# ----------------------------
with right:
    st.title("📄 Live PDF Preview")
    
    resume = st.session_state.resume

    # 1. Build the Contact Header
    contact_parts = []
    if resume.get('email'): contact_parts.append(resume['email'])
    if resume.get('phone'): contact_parts.append(resume['phone'])
    if resume.get('linkedin'): contact_parts.append(resume['linkedin'])
    if resume.get('github'): contact_parts.append(resume['github'])
    contact_str = " | ".join(contact_parts)

    # 2. Build the FULL HTML Document (CSS + Structure)
    # We use a media query (@media print) to hide the print button and background when saving!
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    body {{
        background-color: #525659;
        margin: 0;
        padding: 20px;
        display: flex;
        justify-content: center;
        font-family: 'Times New Roman', Times, serif;
    }}
    .resume-wrapper {{
        display: flex;
        flex-direction: column;
        align-items: center;
    }}
    .a4-page {{
        background: white;
        color: black;
        width: 210mm;
        min-height: 297mm;
        padding: 20mm;
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);
        box-sizing: border-box;
    }}
    h1 {{
        text-align: center; 
        margin-bottom: 5px; 
        font-size: 24pt; 
        text-transform: uppercase;
        color: black;
    }}
    .contact {{
        text-align: center; 
        font-size: 11pt; 
        margin-bottom: 20px; 
        color: black;
    }}
    h3 {{
        border-bottom: 1px solid black; 
        margin-top: 15px; 
        margin-bottom: 10px; 
        font-size: 14pt; 
        text-transform: uppercase;
        color: black;
    }}
    p, li {{ font-size: 11pt; line-height: 1.4; color: black; }}
    ul {{ margin-top: 5px; margin-bottom: 5px; padding-left: 20px; }}
    
    /* This makes sure the PDF output is perfectly clean */
    @media print {{
        body {{ background-color: white; padding: 0; }}
        .a4-page {{ box-shadow: none; width: 100%; min-height: auto; padding: 0; margin: 0; }}
        .no-print {{ display: none; }}
    }}
    </style>
    </head>
    <body>
    
    <div class="resume-wrapper">
        <div style="margin-bottom: 15px;" class="no-print">
            <button onclick="window.print()" style="background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold;">
                🖨️ Save as PDF
            </button>
        </div>
        
        <div class="a4-page">
            <h1>{resume.get('name') or 'YOUR NAME'}</h1>
            <div class="contact">{contact_str}</div>
    """

    # 3. Convert LLM Markdown to HTML and inject it
    body_sections = [
        "summary", "skills", "experience", "projects", 
        "education", "achievements", "extracurriculars"
    ]
    
    for sec in body_sections:
        if resume.get(sec):
            html_body = markdown.markdown(resume[sec])
            full_html += f"<h3>{sec.title()}</h3>\n{html_body}\n"

    # Close the HTML tags
    full_html += """
        </div>
    </div>
    </body>
    </html>
    """

    # 4. Render the isolated web page inside Streamlit
    components.html(full_html, height=850, scrolling=True)  