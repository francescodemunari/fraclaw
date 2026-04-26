import React, { useState, useEffect, useRef } from 'react';
import { 
  Settings, History, Paperclip, ArrowUp, Zap, Trash2, 
  Mic, MicOff, X, FileText, Image as ImageIcon, Plus, 
  Menu, User, Check, AlertTriangle, Download
} from 'lucide-react';
import { io } from 'socket.io-client';
import axios from 'axios';

// Automatically detect the host from which the page was loaded.
// Works locally (localhost) and remotely (Tailscale IP) without manual changes.
const BACKEND_HOST = `${window.location.hostname}:8000`;
const socket = io(`http://${BACKEND_HOST}`);
const API_BASE = `http://${BACKEND_HOST}/api`;
const UPLOAD_BASE = `http://${BACKEND_HOST}/uploads`;

function App() {
  const [inputText, setInputText] = useState('');
  const [messages, setMessages] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [personas, setPersonas] = useState([]);
  const [activePersona, setActivePersona] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [attachedFile, setAttachedFile] = useState(null);
  const [sysLogs, setSysLogs] = useState([]);
  const isCreatingSessionRef = useRef(false);
  const currentSessionIdRef = useRef(null);
  
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  // Synchronize Ref with state
  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);
  
  // --- Initialization ---
  useEffect(() => {
    fetchSessions();
    fetchPersonas();

    socket.on('chat_reply', (data) => {
      // Use ref to decide whether to show message or ignore
      // (now we save it anyway if session coincides)
      setMessages(prev => [...prev, { text: data.text, sender: 'bot', files: data.files }]);
      
      if (data.session_id && !currentSessionIdRef.current) {
        isCreatingSessionRef.current = true;
        setCurrentSessionId(data.session_id);
      }
      fetchSessions();
    });

    socket.on('typing', (data) => {
      setIsTyping(data.status);
    });

    socket.on('system_log', (data) => {
      setSysLogs(prev => [...prev, data.message].slice(-8));
    });

    socket.on('new_session_created', (data) => {
      setSessions(prev => [data, ...prev]);
      isCreatingSessionRef.current = true;
      setCurrentSessionId(data.id);
    });

    socket.on('connect', () => {
      console.log("🟢 Socket connected:", socket.id);
      if (currentSessionIdRef.current) {
        socket.emit('join_session', { session_id: currentSessionIdRef.current });
      }
    });

    return () => {
      socket.off('chat_reply');
      socket.off('typing');
      socket.off('system_log');
      socket.off('new_session_created');
      socket.off('connect');
    };
  }, []); // Executed ONLY once on startup

  // Effect for room joining on session change
  useEffect(() => {
    if (currentSessionId) {
      socket.emit('join_session', { session_id: currentSessionId });
    }
  }, [currentSessionId]);

  useEffect(() => {
    if (currentSessionId) {
      if (isCreatingSessionRef.current) {
        isCreatingSessionRef.current = false;
        return;
      }
      fetchMessages(currentSessionId);
    } else {
      setMessages([]);
    }
  }, [currentSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // --- API Calls ---
  const fetchSessions = async () => {
    try {
      const res = await axios.get(`${API_BASE}/sessions`);
      setSessions(res.data.sessions || []);
    } catch (e) { console.error(e); }
  };

  const fetchMessages = async (id) => {
    try {
      const res = await axios.get(`${API_BASE}/sessions/${id}/messages`);
      const formatted = res.data.messages.map(m => ({
          text: m.content,
          sender: m.role === 'user' ? 'user' : 'bot',
          timestamp: m.timestamp,
          files: m.files || []
      }));
      setMessages(formatted);
    } catch (e) { console.error(e); }
  };

  const handleDeleteSession = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm("Delete this conversation?")) return;
    try {
      await axios.delete(`${API_BASE}/sessions/${id}`);
      if (currentSessionId === id) setCurrentSessionId(null);
      fetchSessions();
    } catch (e) { console.error(e); }
  };

  const fetchPersonas = async () => {
    try {
      const res = await axios.get(`${API_BASE}/personas`);
      setPersonas(res.data.personas || []);
      const active = res.data.personas.find(p => p.is_active);
      setActivePersona(active?.name || 'Jarvis');
    } catch (e) { console.error(e); }
  };

  const handleSwitchPersona = async (name) => {
    try {
      await axios.post(`${API_BASE}/personas/activate?name=${name}`);
      setActivePersona(name);
      fetchPersonas();
    } catch (e) { console.error(e); }
  };

  const handlePurge = async () => {
    if (!window.confirm("☣️ HARD RESET: Wipe all data definitively?")) return;
    try {
      await axios.post(`${API_BASE}/system/purge`);
      setMessages([]);
      setSessions([]);
      setCurrentSessionId(null);
      setShowSettings(false);
      fetchSessions();
    } catch (e) { console.error(e); }
  };

  const getFileName = (path) => path.split(/[\\/]/).pop();
  const isImage = (path) => /\.(jpg|jpeg|png|gif|webp|bmp)$/i.test(path);
  const isAudio = (path) => /\.(mp3|wav|ogg|m4a|flac)$/i.test(path);

  // --- File Management ---
  const handleFileUpload = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    if (currentSessionId) formData.append('session_id', currentSessionId);
    try {
      const res = await axios.post(`${API_BASE}/upload`, formData);
      setAttachedFile({
        name: file.name,
        path: res.data.path,
        url: `${UPLOAD_BASE}/${file.name}`,
        type: file.type
      });
    } catch (e) { console.error(e); }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  // --- Voice ---
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      mediaRecorder.ondataavailable = (e) => audioChunksRef.current.push(e.data);
      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const file = new File([audioBlob], `voice_${Date.now()}.wav`, { type: 'audio/wav' });
        handleFileUpload(file);
        stream.getTracks().forEach(track => track.stop());
      };
      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) { alert("Microphone not available."); }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  };

  const handleSend = () => {
    if (!inputText.trim() && !attachedFile) return;
    const isImg = attachedFile?.type.startsWith('image/');
    const msgData = {
      text: inputText,
      session_id: currentSessionId,
      image_path: isImg ? attachedFile.path : null
    };

    setMessages(prev => [...prev, { 
      text: inputText || (isImg ? "🖼️ Image" : "📁 File"), 
      sender: 'user',
      localFile: attachedFile
    }]);

    socket.emit('chat_message', msgData);
    setInputText('');
    setAttachedFile(null);
  };

  return (
    <div 
      className={`flex h-screen w-full relative overflow-hidden bg-background transition-all duration-700 ${isDragging ? 'scale-[0.98]' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={onDrop}
    >
      {/* Aurora Layer */}
      <div className="absolute inset-0 bg-mesh-gradient opacity-50 pointer-events-none"></div>

      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-[60] w-72 bg-surface-container/60 backdrop-blur-2xl border-r border-white/5 transform transition-transform duration-500 ease-out ${showHistory ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex flex-col h-full p-6">
          <div className="flex items-center justify-between mb-10">
            <h2 className="text-xl font-headline font-black text-white flex items-center gap-3">
              <History size={20} className="text-primary"/> HISTORY
            </h2>
            <button onClick={() => setShowHistory(false)} className="p-2 hover:bg-white/5 rounded-full"><X size={20}/></button>
          </div>
          <button 
            onClick={() => { setCurrentSessionId(null); setShowHistory(false); }}
            className="w-full flex items-center gap-3 p-5 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/5 transition-all mb-8 text-on-surface font-bold"
          >
            <Plus size={20} /> NEW CHAT
          </button>
          <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar">
            {sessions.map(s => (
              <div
                key={s.id}
                onClick={() => { setCurrentSessionId(s.id); setShowHistory(false); }}
                className={`group w-full text-left p-4 rounded-xl transition-all border cursor-pointer relative flex items-center justify-between ${currentSessionId === s.id ? 'bg-primary/20 border-primary/40 text-white shadow-[0_0_20px_rgba(129,144,178,0.1)]' : 'border-transparent text-on-surface-variant hover:bg-white/5'}`}
              >
                <div className="overflow-hidden pr-8">
                  <div className="text-sm font-bold truncate">{s.title || "UNTITLED"}</div>
                  <div className="text-[10px] opacity-40 mt-1">{new Date(s.created_at).toLocaleDateString()}</div>
                </div>
                <button 
                  onClick={(e) => handleDeleteSession(e, s.id)}
                  className="opacity-0 group-hover:opacity-100 p-2 hover:bg-red-500/20 hover:text-red-500 rounded-lg transition-all"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
            {sessions.length === 0 && <div className="text-center py-20 opacity-20 text-xs italic">No history</div>}
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col relative z-10">
        <header className="fixed top-0 w-full z-50 flex justify-between items-center px-8 py-6 aurora-header border-b border-white/5">
          <button onClick={() => setShowHistory(true)} className="text-white hover:bg-primary/20 p-2 rounded-full transition-all"><Menu size={26} /></button>
          <div className="brand-text tracking-[0.5em] font-black uppercase text-2xl font-headline select-none flex items-center gap-2 drop-shadow-2xl">
            FRACLAW
          </div>
          <button onClick={() => setShowSettings(true)} className="text-white hover:bg-primary/20 p-2 rounded-full transition-all"><Settings size={26} /></button>
        </header>

        <main className="flex-1 overflow-y-auto pt-32 pb-48 px-4 md:px-0 custom-scrollbar">
          <div className="max-w-4xl mx-auto w-full flex flex-col gap-10">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center min-h-[55vh] text-center space-y-8 animate-fade-in-up">
                <div className="relative group">
                  <div className="absolute -inset-4 bg-primary/20 rounded-[2rem] blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-700"></div>
                  <img src="/logo.png" className="w-40 h-40 md:w-48 md:h-48 object-contain relative transition-transform duration-700 hover:scale-105 active:scale-95 drop-shadow-[0_0_40px_rgba(129,144,178,0.4)] rounded-full" alt="Logo"/>
                </div>
                <div className="space-y-4">
                  <p className="font-body text-xl text-on-surface-variant max-w-sm mx-auto font-light leading-relaxed">
                    Welcome to Fraclaw. <br/> How can I assist you today?
                  </p>
                </div>
              </div>
            ) : (
              messages.map((m, idx) => (
                <div key={idx} className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'} animate-fade-in-up`}>
                  <div className={`flex items-start max-w-[88%] ${m.sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                    <div className={`w-12 h-12 flex items-center justify-center flex-shrink-0 mt-1 shadow-2xl overflow-hidden ${m.sender === 'user' ? 'rounded-2xl ml-4 bg-primary text-black' : 'rounded-2xl mr-4'}`}>
                      {m.sender === 'user' ? <User size={22}/> : <img src="/bot_avatar.png" className="w-full h-full object-cover" alt="Bot"/>}
                    </div>
                    <div className={`px-7 py-5 rounded-[2rem] text-[15px] leading-relaxed whitespace-pre-wrap shadow-2xl relative border ${
                      m.sender === 'user' ? 'glass-panel text-on-surface rounded-tr-md border-white/10' : 'bg-white/5 text-on-surface rounded-tl-md border-white/5'
                    }`}>
                      {m.text}
                      {(m.files || m.localFile) && (
                        <div className="mt-5 flex flex-col gap-4">
                          {[...(m.files || []), m.localFile].filter(Boolean).map((f, fi) => {
                            const name = typeof f === 'string' ? getFileName(f) : f.name;
                            const path = typeof f === 'string' ? f : f.path;
                            // Determine URL based on subfolder (uploads, workspace or output)
                            const isWorkspace = path.includes('workspace');
                            const isOutput = path.includes('output');
                            const isGeneratedImage = path.includes('generated_images');
                            
                            let downloadUrl = `http://localhost:8000/uploads/${name}`;
                            if (isWorkspace) downloadUrl = `http://localhost:8000/workspace/${name}`;
                            if (isOutput) downloadUrl = `http://localhost:8000/outputs/${name}`;
                            if (isGeneratedImage) downloadUrl = `http://localhost:8000/generated_images/${name}`;

                            if (isImage(name)) {
                              return (
                                <div key={fi} className="group relative rounded-2xl overflow-hidden border border-white/10 max-w-md shadow-2xl">
                                  <img src={downloadUrl} alt="Preview" className="w-full object-cover max-h-[500px] cursor-zoom-in transition-transform duration-500 group-hover:scale-[1.03]" />
                                  <a href={downloadUrl} download target="_blank" rel="noreferrer" className="absolute top-3 right-3 p-3 bg-black/70 backdrop-blur-md rounded-full opacity-0 group-hover:opacity-100 transition-all hover:bg-primary hover:text-black"><Download size={18}/></a>
                                </div>
                              );
                            } else if (isAudio(name)) {
                              return (
                                <div key={fi} className="p-6 bg-black/40 backdrop-blur-md rounded-[2rem] border border-primary/20 flex flex-col gap-4 shadow-[0_0_50px_rgba(129,144,178,0.1)] group">
                                  <div className="flex items-center gap-4">
                                     <div className="w-10 h-10 bg-primary/20 rounded-full flex items-center justify-center text-primary animate-pulse">
                                        <Mic size={20}/>
                                     </div>
                                     <div className="flex flex-col">
                                        <span className="text-[13px] font-black text-white tracking-tight truncate max-w-[200px]">{name}</span>
                                        <span className="text-[10px] text-primary/60 font-bold uppercase tracking-widest">Voice Message</span>
                                     </div>
                                     <a href={downloadUrl} download target="_blank" rel="noreferrer" className="ml-auto p-2 opacity-40 hover:opacity-100 hover:bg-primary/20 rounded-full transition-all text-white"><Download size={18}/></a>
                                  </div>
                                  <audio 
                                    controls 
                                    className="w-full h-10 filter invert opacity-80 hover:opacity-100 transition-opacity"
                                    src={downloadUrl}
                                  >
                                    Your browser does not support the audio element.
                                  </audio>
                                </div>
                              );
                            } else {
                              return (
                                <div key={fi} className="p-4 bg-black/40 backdrop-blur-md rounded-2xl border border-white/10 flex items-center gap-4 transition-all hover:border-primary/40">
                                  <FileText size={22} className="text-primary"/>
                                  <span className="text-sm font-medium truncate max-w-[220px]">{name}</span>
                                  <a href={downloadUrl} download target="_blank" rel="noreferrer" className="ml-auto p-2 hover:bg-primary/20 rounded-full transition-all"><Download size={18}/></a>
                                </div>
                              );
                            }
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
            {isTyping && (
              <div className="flex items-center gap-3 text-white/40 text-[13px] ml-16 animate-pulse font-medium">
                <div className="flex gap-1.5 capitalize">
                  <span className="w-2 h-2 bg-primary/40 rounded-full animate-bounce"></span>
                  <span className="w-2 h-2 bg-primary/40 rounded-full animate-bounce" style={{animationDelay:'0.2s'}}></span>
                  <span className="w-2 h-2 bg-primary/40 rounded-full animate-bounce" style={{animationDelay:'0.4s'}}></span>
                </div>
                Thinking...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </main>

        <div className="fixed bottom-0 w-full px-6 pb-10 pt-16 z-40 flex flex-col items-center bg-gradient-to-t from-background via-background/90 to-transparent pointer-events-none">
          {attachedFile && (
            <div className="mb-8 p-3 bg-black/80 backdrop-blur-3xl rounded-[2rem] border border-primary/50 flex items-center gap-5 pointer-events-auto shadow-[0_0_40px_rgba(129,144,178,0.2)] animate-fade-in-up">
              {attachedFile.type.startsWith('image/') ? (
                <div className="w-14 h-14 rounded-2xl overflow-hidden border border-white/20 shadow-inner">
                  <img src={attachedFile.url} className="w-full h-full object-cover" alt="Thumb"/>
                </div>
              ) : (
                <div className="w-14 h-14 bg-white/5 rounded-2xl flex items-center justify-center text-primary border border-white/20 shadow-inner"><FileText size={24}/></div>
              )}
              <div className="flex flex-col pr-4">
                <span className="text-sm font-black text-white max-w-[180px] truncate">{attachedFile.name}</span>
                <span className="text-[11px] text-primary/60 font-bold uppercase tracking-wider">READY FOR ANALYSIS</span>
              </div>
              <button onClick={() => setAttachedFile(null)} className="p-2.5 mr-1 hover:bg-red-500/20 rounded-full text-white/40 hover:text-red-500 transition-all"><X size={18}/></button>
            </div>
          )}

          <div className="w-full max-w-3xl flex items-center gap-3 p-3 glass-panel rounded-[2.8rem] pointer-events-auto shadow-[0_30px_90px_-15px_rgba(0,0,0,0.7)] transition-all duration-700 bg-white/[0.03] focus-within:ring-2 ring-primary/30 group">
            <button onClick={() => fileInputRef.current.click()} className="text-white/30 hover:text-primary hover:bg-primary/10 rounded-[2rem] transition-all flex items-center justify-center w-14 h-14"><Paperclip size={24} /></button>
            <input type="file" ref={fileInputRef} className="hidden" onChange={(e) => e.target.files[0] && handleFileUpload(e.target.files[0])} />
            <div className="flex-1 relative flex items-center min-h-[56px]">
              <textarea 
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => { if(e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }}}
                className="w-full bg-transparent text-white placeholder-white/10 outline-none resize-none py-4 px-3 font-body text-[16px] placeholder:font-light leading-relaxed custom-scrollbar" 
                placeholder={isRecording ? "Listening..." : "Message Fraclaw..."} 
                rows={1}
                disabled={isRecording}
                style={{ maxHeight: '280px' }}
              />
            </div>
            <button onClick={isRecording ? stopRecording : startRecording} className={`flex items-center justify-center w-14 h-14 rounded-[2rem] transition-all ${isRecording ? 'bg-red-500 text-white animate-pulse' : 'text-white/20 hover:text-white hover:bg-white/10'}`}>
              {isRecording ? <MicOff size={24} /> : <Mic size={24} />}
            </button>
            <button 
              onClick={handleSend}
              disabled={(!inputText.trim() && !attachedFile) || isRecording}
              className="w-14 h-14 flex items-center justify-center bg-white/5 text-white/40 disabled:opacity-10 disabled:grayscale rounded-[2rem] hover:bg-white/10 hover:text-white transition-all border border-white/5"
            >
              <ArrowUp size={22} strokeWidth={3} />
            </button>
          </div>
        </div>
      </div>

      {/* Settings (Glass Upgrade) */}
      {showSettings && (
        <div className="fixed inset-0 z-[100] flex animate-fade-in-up">
           <div className="absolute inset-0 bg-black/95 backdrop-blur-md" onClick={() => setShowSettings(false)}></div>
           <div className="absolute right-0 top-0 bottom-0 w-full max-w-md glass-panel border-l border-white/5 p-10 flex flex-col gap-12 overflow-y-auto">
             <div className="flex items-center justify-between">
                <div><h2 className="text-4xl font-headline font-black tracking-[calc(-0.04em)] text-white">SYSTEM</h2><p className="text-primary/60 text-xs font-bold tracking-widest mt-2 uppercase">Core Control</p></div>
                <button onClick={() => setShowSettings(false)} className="p-3 bg-white/5 rounded-full hover:bg-white/10 transition-all"><X size={28}/></button>
             </div>
             <section className="space-y-5">
                <h3 className="text-[11px] uppercase tracking-[3px] text-white/30 font-black">Neural Identity</h3>
                <div className="grid grid-cols-1 gap-4">
                   {personas.map(p => (
                      <button key={p.name} onClick={() => handleSwitchPersona(p.name)} className={`flex items-center justify-between p-5 rounded-3xl border transition-all duration-500 ${activePersona === p.name ? 'bg-primary/10 border-primary/40 shadow-[0_0_30px_rgba(129,144,178,0.1)]' : 'bg-white/[0.02] border-white/5 hover:border-white/10'}`}>
                         <div className="flex items-center gap-5"><div className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-colors ${activePersona === p.name ? 'bg-primary text-black' : 'bg-white/5 text-white/20'}`}><User size={22}/></div><div className="text-left"><div className="text-base font-black text-white">{p.name}</div><div className="text-[11px] text-white/30 truncate max-w-[180px]">{p.description}</div></div></div>
                         {activePersona === p.name && <Check size={20} className="text-primary animate-scale-in"/>}
                      </button>
                   ))}
                </div>
             </section>
             <div className="mt-auto space-y-6 pt-10 border-t border-white/5">
               <button onClick={handlePurge} className="w-full flex items-center justify-center gap-3 py-5 rounded-3xl bg-red-500/10 text-red-500 border border-red-500/20 font-black text-xs uppercase tracking-[3px] hover:bg-red-500 transition-all hover:text-white group active:scale-95 shadow-2xl"><Trash2 size={18} className="group-hover:rotate-12 transition-transform"/> Hard Reset</button>
             </div>
           </div>
        </div>
      )}

      {isDragging && (
        <div className="fixed inset-0 z-[100] border-[8px] border-dashed border-primary/20 bg-primary/5 flex items-center justify-center pointer-events-none animate-pulse backdrop-blur-sm">
           <div className="text-center p-16 rounded-[4rem] bg-black/40 border border-white/10 shadow-[0_0_100px_rgba(129,144,178,0.2)]">
             <div className="w-24 h-24 bg-primary text-black rounded-full flex items-center justify-center mx-auto mb-8 shadow-2xl"><Plus size={48} strokeWidth={3} /></div>
             <div className="text-4xl font-black text-white tracking-tight uppercase italic">Reveal to Fraclaw</div>
           </div>
        </div>
      )}
    </div>
  );
}

export default App;
