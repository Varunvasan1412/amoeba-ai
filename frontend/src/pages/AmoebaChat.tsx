import { useState, useEffect, useRef, useCallback, memo } from "react";
import { MessageCircle, X, Send, Loader2, Trash2, Paperclip, Plus, MessageSquare } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import DynamicForm from "../components/DynamicForm";

type ChatMessage = {
  role: "user" | "ai";
  text: string;
  actions?: any[]; 
};

type ChatSession = {
    session_id: string;
    title: string;
    updated_at: string;
};

// Enhanced Message Bubble for Full Screen
const MessageBubble = memo(({ msg, onSelect, onSubmitForm, onSwitchMode }: { 
    msg: ChatMessage, 
    onSelect?: (val: string, index?: number) => void, 
    onSubmitForm?: (data: any) => void,
    onSwitchMode?: (mode: "assistant" | "operations") => void
}) => {
  // Extract actions if present
  const choices = msg.actions?.find(a => a.type === "CHOICE");
  const entitySelection = msg.actions?.find(a => a.type === "entity_selection");
  const recordSelection = msg.actions?.find(a => a.type === "record_selection");
  const formAction = msg.actions?.find(a => a.type === "form");
  const formRequest = msg.actions?.find(a => a.type === "form_request"); // Legacy
  const confirmation = msg.actions?.find(a => a.type === "confirmation");
  const success = msg.actions?.find(a => a.type === "success");
  const switchModeAction = msg.actions?.find(a => a.type === "SWITCH_MODE");
  
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [searchTerm, setSearchTerm] = useState("");

  const filteredRecords = recordSelection?.payload?.filter((r: any) => 
    r.label.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  return (
    <div className={`flex flex-col gap-2 max-w-[85%] ${msg.role === "user" ? "self-end items-end" : "self-start items-start"}`}> 
        {/* Main Text Bubble */}
        <div
        className={`p-4 rounded-2xl text-[15px] shadow-sm break-words leading-relaxed ${
            msg.role === "user"
            ? "bg-blue-600 text-white rounded-br-sm" 
            : "bg-white text-gray-800 border border-gray-100 rounded-bl-sm shadow-md"
        }`}
        >
        {msg.role === "user" ? (
            msg.text
        ) : (choices || entitySelection || recordSelection || formAction || formRequest || confirmation || success || switchModeAction) ? (
            <div className="whitespace-pre-wrap text-gray-800 font-sans text-[15px]">
                {msg.text}
                {success && (
                    <div className="mt-2 text-green-600 font-bold flex items-center gap-2">
                        <span>✅</span> {success.payload}
                    </div>
                )}
            </div>
        ) : (
            <div className="prose prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-li:my-0 prose-pre:bg-gray-50 prose-pre:text-gray-700 overflow-hidden">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {msg.text}
            </ReactMarkdown>
            </div>
        )}
        </div>

        {/* Action Buttons (e.g. Choices or Entity Selection) */}
        {msg.role === "ai" && (choices || entitySelection) && (
            <div className="flex flex-wrap gap-2 mt-1 duration-300">
                {(choices?.payload || entitySelection?.payload || []).map((opt: any, idx: number) => (
                    <button
                        key={idx}
                        onClick={() => onSelect && onSelect(opt.table_name || opt.label, opt.index)} 
                        className="text-left text-sm bg-white border border-blue-200 hover:bg-blue-50 hover:border-blue-300 transition-colors p-3 rounded-xl shadow-sm flex items-center gap-2 group"
                    >
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-400 group-hover:bg-blue-600 transition-colors"></div>
                        <span className="font-medium text-gray-700 group-hover:text-blue-800">{opt.label}</span>
                    </button>
                ))}
            </div>
        )}

        {/* Switch Mode Button */}
        {msg.role === "ai" && switchModeAction && (
            <div className="flex gap-2 mt-1">
                <button
                    onClick={() => onSwitchMode && onSwitchMode(switchModeAction.payload)}
                    className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-bold hover:bg-blue-700 transition-all shadow-md"
                >
                    Switch to {switchModeAction.payload === "operations" ? "Operations Mode" : "Assistant Mode"}
                </button>
            </div>
        )}

        {/* SEARCHABLE RECORD SELECTOR (For Update/Delete) */}
        {msg.role === "ai" && recordSelection && recordSelection.payload && (
            <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-md mt-1 w-full max-w-sm flex flex-col gap-3">
                <div className="relative">
                    <input 
                        type="text"
                        placeholder="Search records..."
                        className="w-full bg-gray-50 border border-gray-100 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-100 mb-1"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
                <div className="max-h-60 overflow-y-auto flex flex-col gap-1 scrollbar-thin">
                    {filteredRecords.length > 0 ? (
                        filteredRecords.map((r: any) => (
                            <button
                                key={r.id}
                                onClick={() => onSelect && onSelect(r.id.toString())}
                                className="text-left text-sm p-3 hover:bg-blue-50 rounded-lg transition-colors border border-transparent hover:border-blue-100"
                            >
                                {r.label}
                            </button>
                        ))
                    ) : (
                        <span className="text-xs text-gray-400 text-center py-2">No matches found</span>
                    )}
                </div>
            </div>
        )}

        {/* SMART FORM */}
        {msg.role === "ai" && formAction && formAction.payload && (
            <div className="max-w-md w-full">
                <DynamicForm 
                    fields={formAction.payload.fields} 
                    onSubmit={(data) => onSubmitForm && onSubmitForm(data)}
                    onCancel={() => onSelect && onSelect("Cancel")}
                    title={formAction.payload.table_name}
                />
            </div>
        )}

        {/* Legacy Form Request */}
        {msg.role === "ai" && formRequest && formRequest.payload && (
            <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm mt-1 w-full max-w-sm flex flex-col gap-4">
                <h4 className="text-sm font-bold text-gray-700 uppercase tracking-wider mb-1">Enter Details: {formRequest.payload.entity}</h4>
                {formRequest.payload.fields.map((field: string) => (
                    <div key={field} className="flex flex-col gap-1">
                        <label className="text-xs font-semibold text-gray-500 uppercase ml-1">{field}</label>
                        <input 
                            type="text"
                            placeholder={`Enter ${field}...`}
                            onChange={(e) => setFormData(prev => ({...prev, [field]: e.target.value}))}
                            className="bg-gray-50 border border-gray-100 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-100 outline-none"
                        />
                    </div>
                ))}
                <button 
                    onClick={() => onSubmitForm && onSubmitForm(formData)}
                    className="mt-2 bg-blue-600 text-white py-3 rounded-xl text-sm font-bold hover:bg-blue-700 transition-colors shadow-md"
                >
                    Submit Details
                </button>
            </div>
        )}

        {/* Confirmation Buttons */}
        {msg.role === "ai" && confirmation && (
            <div className="flex gap-3 mt-2">
                <button 
                    onClick={() => onSelect && onSelect("Yes")}
                    className="bg-red-600 text-white px-8 py-2.5 rounded-xl text-sm font-bold hover:bg-red-700 transition-all shadow-md"
                >
                    Confirm
                </button>
                <button 
                    onClick={() => onSelect && onSelect("Cancel")}
                    className="bg-gray-100 text-gray-600 px-8 py-2.5 rounded-xl text-sm font-bold hover:bg-gray-200 transition-all border border-gray-200"
                >
                    Cancel
                </button>
            </div>
        )}
    </div>
  );
});

MessageBubble.displayName = "MessageBubble";

export default function AmoebaChat() {
  const API_BASE = import.meta.env.DEV ? "http://localhost:8000/api" : "/api";
  const urlParams = new URLSearchParams(window.location.search);
  const currentApiKey = urlParams.get("api_key") || import.meta.env.VITE_API_KEY || "";

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>("");
  const [chatMode, setChatMode] = useState<"assistant" | "operations">("assistant");
  
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [aiConfig, setAiConfig] = useState<{provider: string, model: string} | null>(null);
  
  const socketRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const fetchSessions = useCallback(async () => {
    try {
        const res = await fetch(`${API_BASE}/chat/sessions?api_key=${currentApiKey}`);
        if(res.ok) {
            const data = await res.json();
            setSessions(data);
            if(data.length > 0 && !currentSessionId) {
                setCurrentSessionId(data[0].session_id);
            }
        }
    } catch(e) {
        console.error("Error fetching sessions:", e);
    }

    // Fetch AI Config for model indicator
    try {
        const configRes = await fetch(`${API_BASE}/ai-config?api_key=${currentApiKey}`);
        if (configRes.ok) {
            const configData = await configRes.json();
            setAiConfig(configData);
        }
    } catch (err) {
        console.warn("⚠️ Could not fetch AI config:", err);
    }
  }, [API_BASE, currentApiKey, currentSessionId]);

  useEffect(() => {
      fetchSessions();
  }, [fetchSessions]);

  const fetchHistory = useCallback(async (sessionId: string) => {
    setIsLoadingHistory(true);
    try {
      const res = await fetch(`${API_BASE}/chat/messages/${sessionId}?api_key=${currentApiKey}`);
      if (!res.ok) throw new Error("Failed to fetch history");
      const data = await res.json();

      const history = data.map((msg: any) => ({
        role: msg.role,
        text: msg.content,
        actions: msg.actions || [],
      }));
      setMessages(history);
    } catch (err) {
      console.error("History Error:", err);
      setMessages([]);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [API_BASE, currentApiKey]);

  const activeSessionRef = useRef<string>("");
  useEffect(() => {
      activeSessionRef.current = currentSessionId;
  }, [currentSessionId]);

  const setupWebSocket = useCallback((sessionId: string) => {
    // 1. Clean up existing socket without triggering its onclose reconnect logic
    if (socketRef.current) {
        console.log("🧹 Cleaning up old socket...");
        socketRef.current.onclose = null; 
        socketRef.current.onerror = null;
        socketRef.current.close();
        socketRef.current = null;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host; 
    const wsUrl = `${protocol}//${host}/api/ws/chat?api_key=${currentApiKey}`;

    console.log(`🔌 Connecting to WebSocket for session ${sessionId}...`);
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    // Heartbeat
    let heartbeatInterval: any;

    ws.onopen = () => {
        console.log("🟢 WebSocket Connected");
        setIsConnected(true);
        heartbeatInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "ping" }));
            }
        }, 30000);
    };

    ws.onmessage = (event) => {
      setIsTyping(false); 
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "pong") return;

        if (payload.text) {
             setMessages((prev) => [...prev, { 
                 role: "ai" as const, 
                 text: payload.text,
                 actions: payload.actions || []
             }]);
        }

        if (payload.actions && Array.isArray(payload.actions)) {
            payload.actions.forEach((action: any) => {
                const targetWindow = window.opener || window.parent;
                if (action.type === "NAVIGATE") {
                    targetWindow.postMessage({ type: "AMOEBA_ACTION", action: "NAVIGATE", payload: action.payload }, "*");
                    try { targetWindow.focus(); } catch(e) {}
                    setMessages(prev => [...prev, { role: "ai", text: `🚀 Switched your main window to **${action.payload}**` }]);
                } else {
                    targetWindow.postMessage({ type: "AMOEBA_ACTION", action: action.type, payload: action.payload }, "*");
                }
            });
        }
      } catch (e) {
        setMessages((prev) => [...prev, { role: "ai", text: event.data }]);
      }
    };

    ws.onclose = (event) => {
      console.log("🔴 WebSocket Closed:", event.reason);
      setIsConnected(false);
      clearInterval(heartbeatInterval);
      
      // Auto-reconnect if this is still the active session
      if (sessionId === activeSessionRef.current) {
          console.log("🔄 Scheduling Reconnect...");
          setTimeout(() => {
              if (sessionId === activeSessionRef.current) {
                  setupWebSocket(sessionId);
              }
          }, 3000);
      }
    };

    ws.onerror = (error) => {
      console.error("❌ WebSocket Error:", error);
      setIsTyping(false);
      ws.close();
    };
  }, [currentApiKey]); // Removed currentSessionId from deps to avoid re-creating on every state change

  useEffect(() => {
      if(currentSessionId) {
          fetchHistory(currentSessionId).then(() => {
              setupWebSocket(currentSessionId);
          });
      }
      
      return () => {
          if (socketRef.current) {
              socketRef.current.onclose = null;
              socketRef.current.close();
              socketRef.current = null;
          }
      };
  }, [currentSessionId, fetchHistory, setupWebSocket]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleNewChat = async () => {
    try {
        const res = await fetch(`${API_BASE}/chat/session?api_key=${currentApiKey}`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ title: "New Chat" })
        });
        if(res.ok) {
            const data = await res.json();
            setCurrentSessionId(data.session_id);
            setMessages([]);
            fetchSessions();
        }
    } catch(e) {
        console.error("Error creating session:", e);
    }
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if(!window.confirm("Are you sure you want to delete this chat session?")) return;

    try {
        const res = await fetch(`${API_BASE}/chat/session/${sessionId}?api_key=${currentApiKey}`, {
            method: "DELETE"
        });
        if(res.ok) {
            setSessions(prev => prev.filter(s => s.session_id !== sessionId));
            if(currentSessionId === sessionId) {
                const remaining = sessions.filter(s => s.session_id !== sessionId);
                if(remaining.length > 0) {
                    setCurrentSessionId(remaining[0].session_id);
                } else {
                    setCurrentSessionId("");
                    setMessages([]);
                }
            }
        }
    } catch(e) {
        console.error("Error deleting session:", e);
    }
  };

  const handleChoiceSelect = useCallback((label: string, index?: number) => {
    if (!socketRef.current || !isConnected) return;
    const textToSend = index !== undefined ? index.toString() : label;
    setMessages((prev) => [...prev, { role: "user", text: label }]);
    const payload = {
        text: textToSend,
        mode: chatMode,
        api_key: currentApiKey,
        session_id: currentSessionId
    };
    socketRef.current.send(JSON.stringify(payload));
    setIsTyping(true);
  }, [isConnected, chatMode, currentApiKey, currentSessionId]);

  const handleFormSubmit = useCallback((data: any) => {
    if (!socketRef.current || !isConnected) return;
    const text = JSON.stringify(data);
    setMessages((prev) => [...prev, { role: "user", text: "Submitted form details." }]);
    const payload = {
        text: text,
        mode: chatMode,
        api_key: currentApiKey,
        session_id: currentSessionId
    };
    socketRef.current.send(JSON.stringify(payload));
    setIsTyping(true);
  }, [isConnected, chatMode, currentApiKey, currentSessionId]);

  const sendMessage = () => {
    if (!input.trim() || !socketRef.current || !isConnected) return;
    
    // Optimistic UI update
    setMessages((prev) => [...prev, { role: "user", text: input }]);
    
    const payload = {
        text: input,
        mode: chatMode,
        api_key: currentApiKey,
        session_id: currentSessionId
    };
    
    socketRef.current.send(JSON.stringify(payload));
    setInput("");
    setIsTyping(true); 
    
    // Quick refresh of sessions after first message to get updated title
    if(messages.length === 0) {
        setTimeout(() => fetchSessions(), 2000);
    }
  };

  const handleSwitchAndResend = useCallback((newMode: "assistant" | "operations") => {
    setChatMode(newMode);
    
    // Find the last user message to automatically re-run it in the new mode
    const lastUserMsg = [...messages].reverse().find(m => m.role === "user");
    
    if (lastUserMsg && socketRef.current && isConnected) {
        console.log(`🔄 Auto-resending last prompt in ${newMode} mode:`, lastUserMsg.text);
        
        const payload = {
            text: lastUserMsg.text,
            mode: newMode,
            api_key: currentApiKey,
            session_id: currentSessionId
        };
        
        socketRef.current.send(JSON.stringify(payload));
        setIsTyping(true);
    }
  }, [messages, isConnected, currentApiKey, currentSessionId]);

  return (
    <div className="flex h-screen w-full bg-white font-sans text-gray-900 pointer-events-auto">
        {/* Sidebar */}
        <div className="w-72 bg-gray-50 border-r border-gray-200 flex flex-col">
            <div className="p-4 border-b border-gray-200">
                <button 
                    onClick={handleNewChat}
                    className="w-full flex items-center justify-center gap-2 bg-white border border-gray-200 shadow-sm hover:shadow hover:border-gray-300 text-gray-800 font-medium py-2.5 px-4 rounded-xl transition-all"
                >
                    <Plus size={18} /> New Chat
                </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-1">
                <div className="text-xs font-semibold text-gray-400 mb-2 px-2 uppercase tracking-wider">Recent Sessions</div>
                {sessions.map(s => (
                    <div 
                        key={s.session_id}
                        onClick={() => setCurrentSessionId(s.session_id)}
                        className={`group w-full text-left px-3 py-2.5 rounded-lg text-sm truncate transition-colors flex items-center gap-3 cursor-pointer ${
                            currentSessionId === s.session_id ? "bg-blue-100 text-blue-800 font-medium" : "hover:bg-gray-100 text-gray-600"
                        }`}
                    >
                        <MessageSquare size={16} className={currentSessionId === s.session_id ? "text-blue-600 flex-shrink-0" : "text-gray-400 flex-shrink-0"} />
                        <span className="truncate flex-1">{s.title}</span>
                        <button 
                            onClick={(e) => handleDeleteSession(e, s.session_id)}
                            className={`p-1 rounded-md hover:bg-red-100 hover:text-red-600 transition-all opacity-0 group-hover:opacity-100 ${currentSessionId === s.session_id ? "opacity-100" : ""}`}
                        >
                            <Trash2 size={14} />
                        </button>
                    </div>
                ))}
            </div>
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col relative">
            <div className="absolute top-0 w-full p-4 flex justify-between items-center bg-white/80 backdrop-blur-sm z-10 border-b border-gray-100">
                <div className="flex items-center gap-6">
                    <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                        <MessageCircle className="text-blue-600" />
                        Amoeba AI 
                        <span className={`text-xs px-2 py-1 rounded-full ml-2 ${isConnected ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                            {isConnected ? "Connected" : "Reconnecting..."}
                        </span>
                        {aiConfig && (
                            <span className="text-[11px] font-medium bg-blue-50 text-blue-600 px-2 py-1 rounded-lg ml-2 border border-blue-100">
                                🧠 {aiConfig.model.split(':')[0]} · {aiConfig.provider}
                            </span>
                        )}
                    </h2>

                    {/* Mode Toggle */}
                    <div className="flex bg-gray-100 p-1 rounded-xl items-center gap-1 shadow-inner">
                        <button 
                            onClick={() => setChatMode("assistant")}
                            className={`px-4 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-all ${chatMode === "assistant" ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
                        >
                            Assistant
                        </button>
                        <button 
                            onClick={() => setChatMode("operations")}
                            className={`px-4 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-all ${chatMode === "operations" ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
                        >
                            Operations
                        </button>
                    </div>
                </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-8 pt-20 bg-white flex flex-col gap-6 scrollbar-thin max-w-5xl mx-auto w-full">
                {isLoadingHistory ? (
                    <div className="flex items-center justify-center h-full">
                        <Loader2 className="animate-spin text-blue-500" size={32} />
                    </div>
                ) : messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto">
                        <div className="bg-gray-50 p-6 rounded-full mb-6">
                            <MessageCircle size={48} className="text-blue-500" />
                        </div>
                        <h3 className="text-2xl font-bold text-gray-800 mb-2">How can I help you today?</h3>
                        <p className="text-gray-500">Ask about your ERP data, generate reports, or manage your operations directly from this console.</p>
                        <p className="mt-4 text-xs font-semibold text-gray-400 uppercase tracking-widest">
                            Current Mode: <span className="text-blue-600">{chatMode}</span>
                        </p>
                        {aiConfig && (
                            <p className="mt-2 text-xs font-medium text-gray-300">
                                Powered by {aiConfig.model.split(':')[0]} via {aiConfig.provider}
                            </p>
                        )}
                    </div>
                ) : (
                    <>
                        {messages.map((msg, i) => (
                            <MessageBubble 
                                key={i} 
                                msg={msg} 
                                onSelect={handleChoiceSelect} 
                                onSubmitForm={handleFormSubmit}
                                onSwitchMode={handleSwitchAndResend}
                            />
                        ))}
                        {isTyping && (
                            <div className="bg-white border border-gray-100 self-start rounded-2xl rounded-bl-sm p-4 shadow-sm flex items-center gap-1.5 w-20 h-12">
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                            </div>
                        )}
                        <div ref={messagesEndRef} className="h-4" />
                    </>
                )}
            </div>

            <div className="p-4 bg-white max-w-4xl mx-auto w-full pb-8">
                <div className="relative shadow-lg rounded-2xl border border-gray-200 bg-white p-2 flex gap-2 overflow-hidden focus-within:border-blue-300 focus-within:ring-4 focus-within:ring-blue-100/50 transition-all">
                    <textarea
                        className="flex-1 bg-transparent border-0 px-3 py-3 text-[15px] outline-none resize-none max-h-48 min-h-[52px]"
                        rows={1}
                        value={input}
                        disabled={!isConnected || isLoadingHistory}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                sendMessage();
                            }
                        }}
                        placeholder={`Message Amoeba AI in ${chatMode} mode...`}
                    />
                    <button
                        onClick={sendMessage}
                        disabled={!isConnected || !input.trim()}
                        className="self-end p-3.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:bg-gray-100 disabled:text-gray-400 transition-all"
                    >
                        <Send size={18} className={input.trim() ? "translate-x-0.5" : ""} />
                    </button>
                </div>
                <div className="text-center mt-3 text-xs text-gray-400">Amoeba AI can make mistakes. Consider verifying important information.</div>
            </div>
        </div>
    </div>
  );
}
