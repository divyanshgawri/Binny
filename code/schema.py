# import os
# import csv

# def generate_inventory_report(directory="/home/divyansh/Desktop/Binny/onet_kaggle/db_29_0_text", output_csv="onet_inventory_report.csv"):
#     """
#     Extracts headers and counts data rows for all .txt files.
#     Saves a professional inventory report to CSV.
#     """
#     report_data = []
    
#     # Target only text files
#     files = [f for f in os.listdir(directory) if f.endswith('.txt')]
    
#     if not files:
#         print("Error: No .txt files found in the current directory.")
#         return

#     print(f"Analyzing {len(files)} files. Please wait...")

#     for filename in files:
#         file_path = os.path.join(directory, filename)
#         try:
#             with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
#                 # 1. Extract Schema
#                 first_line = f.readline().strip()
#                 if not first_line:
#                     continue
                
#                 delimiter = '\t' if '\t' in first_line else ','
#                 columns = [col.strip() for col in first_line.split(delimiter)]
                
#                 # 2. Efficiently count remaining rows (data rows only)
#                 # This generator expression avoids loading the full file into memory
#                 row_count = sum(1 for line in f)
                
#                 report_data.append({
#                     "File Name": filename,
#                     "Data Rows": row_count,
#                     "Column Count": len(columns),
#                     "Schema": " | ".join(columns)
#                 })
#                 print(f"Processed: {filename} ({row_count} rows)")
                
#         except Exception as e:
#             print(f"Skipping {filename} due to error: {e}")

#     # Sort files by size (largest first) - helps in prioritizing processing
#     report_data.sort(key=lambda x: x["Data Rows"], reverse=True)

#     # Save to CSV
#     if report_data:
#         keys = report_data[0].keys()
#         with open(output_csv, 'w', newline='', encoding='utf-8') as output_file:
#             dict_writer = csv.DictWriter(output_file, fieldnames=keys)
#             dict_writer.writeheader()
#             dict_writer.writerows(report_data)
#         print(f"\n[SUCCESS] Inventory saved to: {output_csv}")
#     else:
#         print("[ERROR] No data was extracted.")

# if __name__ == "__main__":
#     generate_inventory_report()


import os
import shutil
import sqlite3
import datetime
import uuid
import streamlit as st
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnablePassthrough,RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory

# --- CONFIGURATION ---
# Replace with your actual key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Get current directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Point this to the folder where you saved your 1000+ job .txt files
DATA_PATH = os.path.join(BASE_DIR, "job_data_files_clean") 

DB_FAISS_PATH = os.path.join(BASE_DIR, "faiss_career_index")
DB_SQL_PATH = os.path.join(BASE_DIR, "chat_history.db")

st.set_page_config(page_title="AI Career Advisor", layout="wide", page_icon="asd")

# --- 1. DATABASE MANAGER (SQLite for Chat History) ---
def get_db_connection():
    return sqlite3.connect(DB_SQL_PATH, check_same_thread=False)

def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS sessions
                     (id TEXT PRIMARY KEY, name TEXT, created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      session_id TEXT, type TEXT, content TEXT, timestamp TEXT)''')
        conn.commit()

def get_sessions():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name FROM sessions ORDER BY created_at DESC")
        return c.fetchall()

def create_session(name="New Chat"):
    session_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO sessions (id, name, created_at) VALUES (?, ?, ?)", 
                  (session_id, name, datetime.datetime.now().isoformat()))
        conn.commit()
    return session_id

def load_messages(session_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT type, content FROM messages WHERE session_id = ? ORDER BY id", (session_id,))
        rows = c.fetchall()
    return [HumanMessage(content=row[1]) if row[0] == 'human' else AIMessage(content=row[1]) for row in rows]

def save_message(session_id, msg_type, content):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (session_id, type, content, timestamp) VALUES (?, ?, ?, ?)", 
                  (session_id, msg_type, content, datetime.datetime.now().isoformat()))
        conn.commit()

# Initialize DB
init_db()

# --- 2. VECTOR KNOWLEDGE BASE (Job Data) ---
@st.cache_resource
def get_embeddings():
    # Using MiniLM for fast, local embeddings
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def create_vector_db():
    """Builds the vector index from your job .txt files."""
    
    # Check if folder exists
    if not os.path.exists(DATA_PATH):
        os.makedirs(DATA_PATH)
        st.error(f"Folder '{DATA_PATH}' created. Please put your Job .txt files here!")
        return

    # Check if DB already exists
    if not os.path.exists(DB_FAISS_PATH):
        with st.status("🚀 Ingesting Job Market Data...", expanded=True) as status:
            
            # A. Load .txt files
            st.write("Reading job profiles...")
            # We use DirectoryLoader with TextLoader
            loader = DirectoryLoader(DATA_PATH, glob="*.txt", loader_cls=TextLoader)
            documents = loader.load()
            
            if not documents:
                st.warning("No .txt files found. Please generate them first using the previous script.")
                status.update(label="No Data Found", state="error")
                return

            st.write(f"✅ Loaded {len(documents)} job profiles.")

            # B. Split Text (Whole Document Strategy)
            # We use a separator that doesn't exist to force 1 file = 1 chunk
            text_splitter = CharacterTextSplitter(
                separator="\n\n\n",
                chunk_size=500,
                chunk_overlap=0
            )
            docs = text_splitter.split_documents(documents)
            
            # C. Vectorize
            st.write("🧠 Building Vector Index...")
            embeddings = get_embeddings()
            vectorstore = FAISS.from_documents(docs, embeddings)
            vectorstore.save_local(DB_FAISS_PATH)
            
            status.update(label="Career Database Ready!", state="complete", expanded=False)
            st.rerun()

def get_retriever():
    if not os.path.exists(DB_FAISS_PATH):
        return None
    embeddings = get_embeddings()
    # Load the local FAISS index
    vectorstore = FAISS.load_local(DB_FAISS_PATH, embeddings, allow_dangerous_deserialization=True)
    # k=3 retrieves the top 3 most relevant job profiles
    return vectorstore.as_retriever(search_kwargs={"k": 3})

# --- 3. RAG PIPELINE (Career Advisor Persona) ---
def get_rag_chain(retriever):

    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )

    # --- 1. Reformulate question using chat history ---
    reformulation_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a query rewriting assistant for a retrieval system.\n"
        "Your task is to rewrite the user's latest question into a SINGLE, "
        "standalone question that can be understood without chat history.\n\n"
        "Rules:\n"
        "- Preserve the user's original intent exactly\n"
        "- Do NOT add new details, assumptions, or interpretations\n"
        "- Do NOT answer the question\n"
        "- Do NOT include explanations\n"
        "- Output ONLY the rewritten question text\n"
    ),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}")
])


    reformulation_chain = (
        reformulation_prompt
        | llm
        | StrOutputParser()
    )

    # --- 2. Retrieve documents ---
    def retrieve(inputs):
        question = inputs["standalone_question"]
        docs = retriever.invoke(question)
        return {
            "context": docs,
            "question": question,
            "chat_history": inputs["chat_history"],
        }

    retrieval_chain = RunnableLambda(retrieve)

    # --- 3. Answer with persona ---
    qa_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
        You are an expert Career Advisor and Job Market Analyst.

You must follow these rules strictly:

1. If the user's question directly matches one or more specific roles present in the provided job market documents,
   answer ONLY using information from those documents.

2. If the user asks about a broad or umbrella career path
   (for example: "banker", "software engineer", "data scientist")
   and the documents contain related or entry-level roles,
   you MAY provide general, widely accepted career guidance based on industry standards.
   In this case:
   - Use the documents to mention relevant related roles when appropriate.
   - Clearly separate document-based information from general guidance.

3. Clearly label or phrase responses so it is obvious which parts are:
   - derived from the job market documents, and
   - general career guidance.

4. Do NOT invent or assume:
   - salaries
   - companies
   - hiring numbers
   - market statistics
   unless they explicitly appear in the documents.

5. If neither the documents nor general industry knowledge reasonably apply,
   clearly say that you do not have enough information to answer.

6. Be professional, concise, and practical.
   Your goal is to guide the user clearly without speculation.

Job market context:
{context}

        """
    ),
    MessagesPlaceholder("chat_history"),
    ("human", "{question}")
])
    answer_chain = (
        qa_prompt
        | llm
        | StrOutputParser()
    )

    # --- 4. Full RAG pipeline ---
    rag_chain = (
        {
            "standalone_question": reformulation_chain,
            "chat_history": RunnableLambda(lambda x: x["chat_history"]),
        }
        | retrieval_chain
        | {
            "answer": answer_chain,
            "context": RunnableLambda(lambda x: x["context"]),
        }
    )

    return rag_chain


# --- 4. SIDEBAR & SESSION MANAGEMENT ---
with st.sidebar:
    st.title("💼 Career Coach AI")
    
    if st.button("➕ New Consultation"):
        new_id = create_session(f"Consultation {datetime.datetime.now().strftime('%H:%M')}")
        st.session_state.active_session_id = new_id
        st.rerun()

    if st.button("🔄 Refresh Market Data"):
        if os.path.exists(DB_FAISS_PATH):
            shutil.rmtree(DB_FAISS_PATH)
        st.rerun()

    st.markdown("---")
    
    sessions = get_sessions()
    if not sessions:
        first_id = create_session("First Consultation")
        st.session_state.active_session_id = first_id
        st.rerun()

    if "active_session_id" not in st.session_state:
        st.session_state.active_session_id = sessions[0][0]

    session_options = {s[0]: s[1] for s in sessions}
    
    selected_id = st.radio(
        "Consultation History:",
        options=list(session_options.keys()),
        format_func=lambda x: session_options[x],
        index=list(session_options.keys()).index(st.session_state.active_session_id),
    )

    if selected_id != st.session_state.active_session_id:
        st.session_state.active_session_id = selected_id
        st.rerun()

# --- 5. MAIN CHAT INTERFACE ---
st.title(f"💬 {session_options[st.session_state.active_session_id]}")

# Ensure Vector DB exists
create_vector_db()

# Display Chat History
history = load_messages(st.session_state.active_session_id)
for msg in history:
    with st.chat_message("user" if isinstance(msg, HumanMessage) else "assistant"):
        st.markdown(msg.content)

# Handle User Input
if prompt := st.chat_input("Ask about jobs, salaries, or skills..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    save_message(st.session_state.active_session_id, "human", prompt)

    with st.chat_message("assistant"):
        retriever = get_retriever()
        
        if not retriever:
            st.error("⚠️ Database not found. Please ensure the 'job_data_files_clean' folder has data.")
        else:
            with st.spinner("Analyzing market data..."):
                try:
                    rag_chain = get_rag_chain(retriever)
                    response = rag_chain.invoke({
                        "input": prompt, 
                        "chat_history": history
                    })
                    
                    answer_text = response['answer']
                    st.markdown(answer_text)
                    # --- ADD THIS FOR EXAM CREDIT ---
                    with st.expander("View Sources (Proof)"):
                        for doc in response['context']:
                            # This displays the filename (e.g., "0_Chief_Executive.txt")
                            st.write(f"📄 Source: {os.path.basename(doc.metadata['source'])}")
                    # -------------------------------
                    # Save AI Message
                    save_message(st.session_state.active_session_id, "ai", answer_text)
                
                except Exception as e:
                    st.error(f"An error occurred: {e}")