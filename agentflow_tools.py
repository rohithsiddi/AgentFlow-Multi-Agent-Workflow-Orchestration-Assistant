import os
import requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv(override=True)

from playwright.async_api import async_playwright
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain.agents import Tool
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit, FileManagementToolkit
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_experimental.tools import PythonREPLTool
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings 
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pypdf import PdfReader
import tiktoken

# Pushover setup via .env
pushover_token = os.getenv("PUSHOVER_TOKEN")
pushover_user = os.getenv("PUSHOVER_USER")
pushover_url = "https://api.pushover.net/1/messages.json"
serper = GoogleSerperAPIWrapper()

async def playwright_tools():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
    return toolkit.get_tools(), browser, playwright


def push(text: str) -> str:
    """Send a push notification via Pushover"""
    requests.post(pushover_url, data={"token": pushover_token, "user": pushover_user, "message": text})
    return "success"


def get_file_tools():
    toolkit = FileManagementToolkit(root_dir=os.getenv("FILE_TOOL_ROOT", "reports"))
    return toolkit.get_tools()

async def other_tools() -> list[Tool]:
    push_tool = Tool(
        name="send_push_notification",
        func=push,
        description="Send a push notification via Pushover"
    )
    file_tools = get_file_tools()
    search_tool = Tool(
        name="search",
        func=serper.run,
        description="Run a Google Serper web search"
    )
    wikipedia = WikipediaAPIWrapper()
    wiki_tool = WikipediaQueryRun(api_wrapper=wikipedia)
    python_repl = PythonREPLTool()
    return file_tools + [push_tool, search_tool, python_repl, wiki_tool]

# --- Google Calendar integration ---

def _get_calendar_service():
    creds = Credentials.from_authorized_user_file(
        os.getenv("GOOGLE_TOKEN_PATH", "token.json"),
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    return build("calendar", "v3", credentials=creds)


def create_calendar_event(summary: str, start_iso: str, end_iso: str, description: str = "", calendar_id: str = None) -> str:
    cal_id = calendar_id or os.getenv("GOOGLE_CALENDAR_ID", "primary")
    service = _get_calendar_service()
    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_iso},
        "end":   {"dateTime": end_iso},
    }
    created = service.events().insert(calendarId=cal_id, body=event).execute()
    return f"Event created: {created.get('htmlLink')}"


def list_upcoming_events(calendar_id: str = None, max_results: int = 5) -> str:
    cal_id = calendar_id or os.getenv("GOOGLE_CALENDAR_ID", "primary")
    service = _get_calendar_service()
    now = datetime.utcnow().isoformat() + "Z"
    events_result = (
        service.events()
        .list(calendarId=cal_id, timeMin=now, maxResults=max_results, singleEvents=True, orderBy="startTime")
        .execute()
    )
    events = events_result.get("items", [])
    if not events:
        return "No upcoming events found."
    lines = []
    for evt in events:
        start = evt["start"].get("dateTime", evt["start"].get("date"))
        lines.append(f"{start} — {evt['summary']}")
    return "\n".join(lines)


def calendar_tools() -> list[Tool]:
    return [
        Tool(
            name="create_calendar_event",
            func=create_calendar_event,
            description="Schedule an event: summary, start_iso (RFC3339), end_iso (RFC3339), [description], [calendar_id]"
        ),
        Tool(
            name="list_upcoming_events",
            func=list_upcoming_events,
            description="List upcoming events on the specified or primary calendar."
        ),
    ]
rag_faiss_db = None
rag_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
rag_text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

def ingest_pdf_for_rag(pdf_path: str) -> str:
    global rag_faiss_db
    reader = PdfReader(pdf_path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    docs = rag_text_splitter.create_documents([text])
    if rag_faiss_db is None:
        rag_faiss_db = FAISS.from_documents(docs, rag_embeddings)
    else:
        rag_faiss_db.add_documents(docs)
    return f"PDF '{os.path.basename(pdf_path)}' ingested for RAG."

def rag_retrieve(query: str, k: int = 4) -> str:
    if rag_faiss_db is None:
        return "No PDF data ingested yet."
    docs = rag_faiss_db.similarity_search(query, k=k)
    return "\n\n".join(d.page_content for d in docs)

def rag_tools():
    return [
        Tool(
            name="ingest_pdf_for_rag",
            func=ingest_pdf_for_rag,
            description="Ingest a PDF file for RAG. Input: path to PDF file."
        ),
        Tool(
            name="rag_retrieve",
            func=rag_retrieve,
            description="Retrieve relevant context from ingested PDFs for a query. Input: query string."
        ),
    ]
