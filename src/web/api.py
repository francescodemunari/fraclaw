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

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import socketio
from loguru import logger

from src.agent.orchestrator import Orchestrator
from src.agent.core import _make_client
from src.memory.database import get_connection, init_db
from src.memory.preferences import list_personas, switch_persona, save_conversation_message, sync_memory_to_disk
from src.memory.vector import clear_all_memories
from src.config import config

# FastAPI Standalone App
app = FastAPI(title="Fraclaw Web API", version="1.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Socket.IO async server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Upload directory
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Workspace directory (for Coder outputs)
WORKSPACE_DIR = Path("data/workspace")
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# Expose folders for browser previews and downloads
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")
app.mount("/workspace", StaticFiles(directory="data/workspace"), name="workspace")
app.mount("/outputs", StaticFiles(directory="data/output"), name="outputs")

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# --- API Endpoints ---

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "agent": "Fraclaw Local AI"}

@app.get("/api/sessions")
async def get_sessions():
    """Returns the list of chat sessions."""
    try:
        conn = get_connection()
        conn.row_factory = dict_factory
        rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        conn.close()
        return {"sessions": rows}
    except Exception as e:
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
    """Deletes a chat session and all its messages (via Cascade)."""
    try:
        conn = get_connection()
        # Ensure foreign keys are enabled (already in get_connection but good to be safe)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if deleted:
            logger.info(f"🗑️ Session {session_id} deleted.")
            return {"status": "success"}
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: int):
    """Retrieves messages for a specific session with attachments."""
    try:
        conn = get_connection()
        conn.row_factory = dict_factory
        # Get messages
        rows = conn.execute(
            "SELECT id, role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY timestamp ASC", 
            (session_id,)
        ).fetchall()
        
        messages = []
        for row in rows:
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
    """Clears all history, user facts, and monitors (Hard Reset)."""
    try:
        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        
        # Atomic wipe
        cursor.execute("DELETE FROM conversations")
        cursor.execute("DELETE FROM sessions")
        cursor.execute("DELETE FROM user_facts")
        cursor.execute("DELETE FROM web_monitors")
        
        # Reset ID sequence
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('sessions', 'conversations', 'user_facts', 'web_monitors')")
        
        conn.commit()
        conn.close()
        
        # Sync reset to MEMORY.md
        sync_memory_to_disk()
        
        # Hard reset Vector Memory (ChromaDB)
        clear_all_memories()
        
        logger.warning("☣️ SYSTEM PURGE COMPLETED (Full Wipe)")
        return {"status": "success", "message": "All data wiped including vector and disk memory."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Upload Endpoint ---

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), session_id: Optional[int] = Form(None)):
    """Handles file uploads (images, audio, documents)."""
    try:
        file_path = UPLOAD_DIR / file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"📁 File uploaded via Web: {file.filename} (Path: {file_path})")
        
        # Audio transcription if applicable
        transcription = None
        if file.content_type.startswith("audio/"):
            from src.tools.whisper_tool import transcribe_audio
            res = await transcribe_audio(str(file_path.absolute()))
            if res and "text" in res:
                transcription = res["text"]
                logger.info(f"🎙️ Audio transcription: {transcription}")

        return {
            "status": "success",
            "filename": file.filename,
            "path": str(file_path.absolute()),
            "type": file.content_type,
            "transcription": transcription
        }
    except Exception as e:
        logger.error(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- AI Title Helper ---

async def generate_chat_title(first_message: str) -> str:
    """Uses LLM to generate a short title for the chat."""
    try:
        client = _make_client()
        prompt = (
            "Given this first message of a chat, generate a title of MAXIMUM 3 words.\\n"
            "Respond ONLY with the title, no quotes or punctuation.\\n\\n"
            f"Message: {first_message}"
        )
        response = await client.chat.completions.create(
            model=config.lm_studio_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.3
        )
        return response.choices[0].message.content.strip() or "Conversation"
    except:
        return "New Chat"

# --- Socket.IO Events ---

@sio.event
async def connect(sid, environ):
    logger.info(f"🌐 Web UI Client connected: {sid}")
    await sio.emit('system_log', {'message': '[SYS] Web UI Socket connection established.'}, to=sid)

@sio.on('join_session')
async def join_session(sid, data):
    session_id = data.get("session_id")
    if session_id:
        room_name = f"session_{session_id}"
        await sio.enter_room(sid, room_name)
        logger.info(f"🚪 Client {sid} joined room {room_name}")

@sio.on('chat_message')
async def chat_message(sid, data):
    """
    Receives user message from Web UI.
    Supports session_id and optional attachments.
    """
    user_text = data.get("text", "")
    session_id = data.get("session_id")
    image_path = data.get("image_path")
    
    if not user_text and not image_path:
        return

    # 1. ROOM MANAGEMENT (RESILIENCE)
    # We join a room dedicated to this session.
    # If the client reconnects, they will re-join this room and receive pending messages.
    session_room = f"session_{session_id}" if session_id else "temp_session"
    await sio.enter_room(sid, session_room)

    logger.info(f"💬 Web Input [Session {session_id}][Room {session_room}]: {user_text}")
    await sio.emit('system_log', {'message': f'[NET] Processing input...'}, room=session_room)
    await sio.emit('typing', {'status': True}, room=session_room)
    
    try:
        # Create session if missing
        if session_id is None:
            conn = get_connection()
            title = await generate_chat_title(user_text)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO sessions (title) VALUES (?)", (title,))
            session_id = cursor.lastrowid
            conn.commit()
            conn.close()
            await sio.emit('new_session_created', {'id': session_id, 'title': title}, room=session_room)
            # If the session was just created, update the room name
            old_room = session_room
            session_room = f"session_{session_id}"
            await sio.enter_room(sid, session_room)
            logger.debug(f"🚪 Room Migrated: {old_room} -> {session_room}")

        # Orchestration Execution
        # We need to save the result and ensure attachments are linked
        result = await Orchestrator.run(user_text, image_path=image_path, session_id=session_id)
        
        reply_text = result.get("text", "No response.")
        files = result.get("files", [])
        
        # LINK ATTACHMENTS TO THE LAST ASSISTANT MESSAGE
        # Note: Orchestrator.run calls run_agent which already saves the message to SQL.
        # We find the last message for this session.
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
                logger.info(f"🔗 Linked attachment to message {msg_id}: {f_path}")

        # REDUNDANT SEND (Current Room + Session Fallback)
        payload = {
            'text': reply_text,
            'files': files,
            'session_id': session_id
        }
        await sio.emit('chat_reply', payload, room=session_room)
        
        # If for some reason session_id changed, emit to the nominal room too
        fallback_room = f"session_{session_id}"
        if session_id and session_room != fallback_room:
            await sio.emit('chat_reply', payload, room=fallback_room)

        logger.success(f"📤 [SOCKET] Response sent successfully to room {session_room}")
        await sio.emit('system_log', {'message': f'[SYS] Response sent to {session_room}.'}, room=session_room)
        
    except Exception as e:
        logger.error(f"Socket.IO Error: {e}")
        import traceback
        traceback.print_exc()
        await sio.emit('chat_reply', {'text': f"❌ Critical Error: {str(e)}"}, room=session_room)
    finally:
        await sio.emit('typing', {'status': False}, room=session_room)

if __name__ == "__main__":
    import uvicorn
    from src.memory.preferences import init_default_personas
    init_db()
    init_default_personas()
    uvicorn.run("src.web.api:socket_app", host="0.0.0.0", port=8000, reload=False)
