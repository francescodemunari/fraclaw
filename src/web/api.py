import os
import sys
import json
import asyncio
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Fix path to allow direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import socketio
from loguru import logger

from src.agent.orchestrator import Orchestrator
from src.agent.utils import get_client
from src.agent.prompts import get_title_generation_prompt
from src.memory.database import get_connection, init_db
from src.memory.preferences import list_personas, switch_persona, save_conversation_message, sync_memory_to_disk
from src.memory.vector import clear_all_memories
from src.config import config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    try:
        from src.tools.whisper_tool import pre_load_model
        await pre_load_model()
        logger.info("✅ Transcription Model ready and in memory.")
    except Exception as e:
        logger.error(f"❌ Failed to pre-load Whisper: {e}")

    # Wire CronTool for global broadcasts (Web/Mobile)
    try:
        from src.tools.cron_tool import init_broadcast_callback
        
        async def broadcast_notification(message: str):
            await sio.emit('notification', {'message': message})
            logger.info(f"🔔 Notification broadcasted to all clients: {message[:50]}...")

        init_broadcast_callback(broadcast_notification)
    except Exception as e:
        logger.error(f"❌ Failed to wire CronTool: {e}")

    # Ensure DB is initialized
    init_db()
    logger.info("✅ Backend initialization complete.")
    
    yield
    # Shutdown logic
    logger.info("🔚 Backend shutting down...")

# FastAPI Standalone App
app = FastAPI(title="Fraclaw Web API", version="1.0", lifespan=lifespan)

# Enable CORS for frontend and mobile access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Socket.IO async server configuration
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Data directories initialization — all anchored to project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent

UPLOAD_DIR = _PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

WORKSPACE_DIR = _PROJECT_ROOT / "data" / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = _PROJECT_ROOT / "data" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GENERATED_IMAGES_DIR = _PROJECT_ROOT / "data" / "generated_images"
GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Static file serving for browser previews and downloads
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/workspace", StaticFiles(directory=str(WORKSPACE_DIR)), name="workspace")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
app.mount("/generated_images", StaticFiles(directory=str(GENERATED_IMAGES_DIR)), name="generated_images")


# --- API Endpoints ---

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "agent": "Fraclaw Local AI"}

@app.head("/queue")
async def dummy_queue():
    """Dummy endpoint to suppress 404 logs from stale Gradio/Comfy browser tabs."""
    return {}


@app.get("/api/sessions")
async def get_sessions():
    """Returns the list of chat sessions with reliable date formatting."""
    try:
        conn = get_connection()
        rows = conn.execute("SELECT id, title, created_at FROM sessions ORDER BY created_at DESC").fetchall()
        conn.close()
        
        sessions = []
        for r in rows:
            # Safe conversion of SQLite timestamp to ISO8601 for Flutter
            dt = r["created_at"]
            if dt and " " in dt and "T" not in dt:
                dt = dt.replace(" ", "T") + "Z"
            
            sessions.append({
                "id": r["id"],
                "title": r["title"],
                "created_at": dt
            })
            
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return {"error": str(e)}

@app.post("/api/sessions")
async def create_session(title: str = "New Conversation"):
    """Creates a new chat session."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sessions (title) VALUES (?)", (title,))
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"id": session_id, "title": title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: int):
    """Deletes a chat session and cascades all linked messages/attachments."""
    try:
        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if deleted:
            logger.info(f"🗑️ Session {session_id} deleted successfully.")
            return {"status": "success"}
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/memories")
async def get_memories():
    """Returns all recorded user facts."""
    try:
        from src.memory.preferences import get_all_facts
        return {"memories": get_all_facts()}
    except Exception as e:
        return {"error": str(e)}

@app.delete("/api/memories")
async def delete_memory(category: str, key: str):
    """Deletes a specific fact."""
    try:
        from src.memory.preferences import delete_fact
        if delete_fact(category, key):
            return {"status": "success"}
        raise HTTPException(status_code=404, detail="Fact not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: int):
    """Retrieves messages for a specific session with attachments."""
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,)
        ).fetchall()
        
        messages = []
        for row in rows:
            dt = row["timestamp"]
            if dt and " " in dt and "T" not in dt:
                dt = dt.replace(" ", "T") + "Z"
                
            msg_dict = {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "timestamp": dt
            }
            
            # Get attachments... (logic below continues)
            msg_id = row['id']
            # Get attachments for each message
            attachments = conn.execute(
                "SELECT file_path, file_name FROM attachments WHERE message_id = ?",
                (msg_id,)
            ).fetchall()
            
            msg_dict = dict(row)
            msg_dict['files'] = [a['file_path'] for a in attachments]
            messages.append(msg_dict)
            
        conn.close()
        return {"messages": messages}
    except Exception as e:
        logger.error(f"Error fetching messages for session {session_id}: {e}")
        return {"error": str(e)}

@app.get("/api/personas")
async def get_personas():
    """Returns the list of available personas."""
    return {"personas": list_personas()}

@app.post("/api/personas/activate")
async def activate_persona(name: str):
    """Changes the active persona."""
    if switch_persona(name):
        return {"status": "success", "persona": name}
    raise HTTPException(status_code=400, detail="Persona not found or DB error")

@app.post("/api/system/purge")
async def purge_system():
    """Executes a destructive hard reset (history, facts, vector DB)."""
    try:
        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        
        # Atomic wipe of SQL storage
        cursor.execute("DELETE FROM conversations")
        cursor.execute("DELETE FROM sessions")
        cursor.execute("DELETE FROM user_facts")
        cursor.execute("DELETE FROM web_monitors")
        cursor.execute("DELETE FROM sqlite_sequence")
        
        conn.commit()
        conn.close()
        
        # Flush Markdown sync and VectorDB
        sync_memory_to_disk()
        clear_all_memories()
        
        logger.warning("☣️ CRITICAL: FULL SYSTEM PURGE COMPLETED")
        return {"status": "success", "message": "All data wiped including vector and disk memory."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Upload Endpoint ---

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), session_id: Optional[int] = Form(None)):
    """Handles multi-part file uploads with optional audio transcription."""
    try:
        file_path = UPLOAD_DIR / file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"📁 Resource uploaded: {file.filename} (Type: {file.content_type})")
        
        # Trigger Whisper for audio files
        transcription = None
        is_audio = file.content_type.startswith("audio/") or file.filename.lower().endswith(('.m4a', '.wav', '.mp3', '.aac', '.ogg', '.flac'))
        
        if is_audio:
            from src.tools.whisper_tool import transcribe_audio
            res = await transcribe_audio(str(file_path.absolute()))
            if res and "transcript" in res:
                transcription = res["transcript"]
                logger.debug(f"🎙️ Whisper Transcription: {transcription[:100]}...")

        return {
            "status": "success",
            "filename": file.filename,
            "path": str(file_path.absolute()),
            "type": file.content_type,
            "transcription": transcription
        }
    except Exception as e:
        logger.error(f"Upload process failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- AI Title Helper ---

async def generate_chat_title(first_message: str) -> str:
    """Uses the local LLM to summarize the first message into a short title."""
    try:
        client = get_client() # Use centralized factory
        prompt = get_title_generation_prompt(first_message) # Use centralized prompt
        
        response = await client.chat.completions.create(
            model=config.lm_studio_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.3
        )
        return response.choices[0].message.content.strip() or "Untitled Chat"
    except Exception as e:
        logger.warning(f"Title generation failed: {e}")
        return "New Conversation"

# --- Socket.IO Real-time Pipeline ---

@sio.event
async def connect(sid, environ):
    """Initial handler for incoming socket connections."""
    logger.info(f"🌐 Client Connected: {sid}")
    await sio.emit('system_log', {'message': '[SYS] Neural Socket Link Active.'}, to=sid)

async def get_all_sessions_json():
    """Helper to fetch formatted session list."""
    try:
        conn = get_connection()
        rows = conn.execute("SELECT id, title, created_at FROM sessions ORDER BY created_at DESC").fetchall()
        conn.close()
        
        sessions = []
        for r in rows:
            dt = r["created_at"]
            if dt and " " in dt and "T" not in dt:
                dt = dt.replace(" ", "T") + "Z"
            sessions.append({
                "id": r["id"],
                "title": r["title"],
                "created_at": dt
            })
        return sessions
    except Exception as e:
        logger.error(f"Failed to fetch sessions for socket: {e}")
        return []

async def get_all_personas_json():
    """Helper to fetch formatted persona list."""
    try:
        personas = list_personas()
        return personas
    except Exception as e:
        logger.error(f"Failed to fetch personas for socket: {e}")
        return []

@sio.on('connect')
async def handle_connect(sid, environ):
    """Automatically push state to new clients."""
    logger.info(f"🔗 New Connection: {sid}")
    
    # Push initial state instantly
    sessions = await get_all_sessions_json()
    personas = await get_all_personas_json()
    
    await sio.emit('history_list', {'sessions': sessions}, to=sid)
    await sio.emit('personas_list', {'personas': personas}, to=sid)
    logger.debug(f"📤 Initial state pushed to {sid}")

@sio.on('request_history')
async def handle_request_history(sid, data=None):
    """Manual trigger for history refresh."""
    sessions = await get_all_sessions_json()
    await sio.emit('history_list', {'sessions': sessions}, to=sid)

@sio.on('request_personas')
async def handle_request_personas(sid, data=None):
    """Manual trigger for persona refresh."""
    personas = await get_all_personas_json()
    await sio.emit('personas_list', {'personas': personas}, to=sid)

@sio.on('join_session')
async def join_session(sid, data):
    """Locks a client into a specific session room for isolated history synchronization."""
    session_id = data.get("session_id")
    if session_id:
        room_name = f"session_{session_id}"
        await sio.enter_room(sid, room_name)
        logger.info(f"🚪 Client {sid} joined isolated session: {room_name}")

@sio.on('chat_message')
async def chat_message(sid, data):
    """
    Core messaging pipe. Receives user input, triggers Orchestrator, 
    manages session persistence, and broadcasts replies.
    """
    user_text = data.get("text", "")
    session_id = data.get("session_id")
    image_path = data.get("image_path")
    
    if not user_text and not image_path:
        return

    # Dynamic Room Assignment
    session_room = f"session_{session_id}" if session_id else "temporary_handoff"
    await sio.enter_room(sid, session_room)

    logger.info(f"💬 Direct Input [ID {session_id}]: {user_text}")
    await sio.emit('typing', {'status': True}, room=session_room)
    
    try:
        # Implicit session creation for first messages
        if session_id is None:
            conn = get_connection()
            title = await generate_chat_title(user_text)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO sessions (title) VALUES (?)", (title,))
            session_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Update client with identity of the new session
            await sio.emit('new_session_created', {'id': session_id, 'title': title}, room=session_room)
            
            # Refresh global history list for the UI
            sessions = await get_all_sessions_json()
            await sio.emit('history_list', {'sessions': sessions}, to=sid)
            
            # Migrate to the official session room
            old_room = session_room
            session_room = f"session_{session_id}"
            await sio.enter_room(sid, session_room)
            logger.debug(f"🚪 Room Syncing: {old_room} -> {session_room}")

        # Main Orchestration Cycle (Routing -> Tooling -> Narrating)
        result = await Orchestrator.run(user_text, image_path=image_path, session_id=session_id)
        
        reply_text = result.get("text", "System encountered an unexpected void in response logic.")
        files = result.get("files", [])
        
        # Persistence: Link generated artifacts to the relevant message ID
        from src.memory.preferences import save_attachment
        conn = get_connection()
        last_msg = conn.execute(
            "SELECT id FROM conversations WHERE session_id = ? AND role = 'assistant' ORDER BY timestamp DESC LIMIT 1",
            (session_id,)
        ).fetchone()
        conn.close()
        
        if last_msg and files:
            msg_id = last_msg[0]
            for f_path in files:
                save_attachment(msg_id, f_path)
                logger.debug(f"🔗 Resource Linked: MSG[{msg_id}] <-> {f_path}")

        # Broadcast response to all clients in the session room
        payload = {
            'text': reply_text,
            'files': files,
            'session_id': session_id
        }
        await sio.emit('chat_reply', payload, room=session_room)
        
        logger.success(f"📤 Response broadcast complete: {session_room}")
        
    except Exception as e:
        logger.error(f"Real-time Pipe Error: {e}")
        await sio.emit('chat_reply', {'text': f"⚠️ Connection error in neural pipeline: {str(e)}"}, room=session_room)
    finally:
        await sio.emit('typing', {'status': False}, room=session_room)

if __name__ == "__main__":
    import uvicorn
    from src.memory.preferences import init_default_personas
    init_db()
    init_default_personas()
    uvicorn.run("src.web.api:socket_app", host="0.0.0.0", port=8000, reload=False)
