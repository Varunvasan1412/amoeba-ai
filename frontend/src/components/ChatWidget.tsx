import { useState, useEffect, useRef, useCallback, memo } from "react";
import { MessageCircle, Send, Loader2, Trash2, Plus, Square, Pencil, Sun, Moon, Paperclip, SlidersHorizontal, Building2, FileText, X, CheckCircle2, AlertCircle, Maximize, Brain, Cpu, Mic } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import DynamicForm from "./DynamicForm";
import { useAdmin } from "../context/AdminContext";

type ChatMessage = {
  role: "user" | "ai";
  text: string;
  actions?: any[]; 
  timestamp?: number;
  is_edited?: boolean;
};

// Memoized Message Bubble for performance
const MessageBubble = memo(({ msg, index, onSelect, onSubmitForm, onSwitchMode, onEdit, darkMode }: { 
    msg: ChatMessage, 
    index: number,
    onSelect?: (val: string, index?: number) => void, 
    onSubmitForm?: (data: any) => void,
    onSwitchMode?: (mode: "assistant" | "operations") => void,
    onEdit?: (text: string, index: number) => void,
    darkMode?: boolean
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
  const sourcesAction = msg.actions?.find(a => a.type === "SOURCES");
  
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [searchTerm, setSearchTerm] = useState("");

  const filteredRecords = recordSelection?.payload?.filter((r: any) => 
    r.label.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  return (
    <div className={`flex flex-col gap-2 max-w-[85%] ${msg.role === "user" ? "self-end items-end" : "self-start items-start"}`}> 
        {/* Main Text Bubble */}
        <div
        className={`p-3.5 rounded-2xl text-sm shadow-sm break-words leading-relaxed transition-theme ${
            msg.role === "user"
            ? "bg-blue-600 text-white rounded-br-sm" 
            : darkMode 
                ? "bg-gray-800 text-gray-100 border border-gray-700 rounded-bl-sm shadow-xl"
                : "bg-white text-gray-800 border border-gray-100 rounded-bl-sm shadow-[0_2px_8px_-4px_rgba(0,0,0,0.1)]"
        }`}
        >
        {msg.role === "user" ? (
            <div className="flex flex-col">
                <span>{msg.text}</span>
                {msg.is_edited && (
                    <span className="text-[9px] opacity-60 mt-1 italic text-right">Edited</span>
                )}
            </div>
        ) : (choices || entitySelection || recordSelection || formAction || formRequest || confirmation || success || switchModeAction) ? (
            <div className={`whitespace-pre-wrap font-sans text-sm ${darkMode ? 'text-gray-200' : 'text-gray-800'}`}>
                {msg.text}
                {success && (
                    <div className={`mt-2 font-bold flex items-center gap-2 ${darkMode ? 'text-green-400' : 'text-green-600'}`}>
                        <span>✅</span> {success.payload}
                    </div>
                )}
            </div>
        ) : (
            <div className={`prose prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-li:my-0 overflow-hidden ${darkMode ? 'prose-invert prose-pre:bg-gray-900 prose-pre:text-gray-300' : 'prose-pre:bg-gray-50 prose-pre:text-gray-700'}`}>
            <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={{
                    a: ({ node, ...props }) => (
                        <a 
                            {...props} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-blue-600 underline hover:text-blue-800 transition-colors cursor-pointer font-bold"
                            onClick={(e) => {
                                // If it's an internal-ish or direct link, tell the parent ERP to navigate
                                if (props.href) {
                                    e.preventDefault();
                                    window.parent.postMessage({
                                        type: "AMOEBA_ACTION",
                                        action: "NAVIGATE",
                                        payload: props.href
                                    }, "*");
                                }
                            }}
                        />
                    )
                }}
            >
                {msg.text}
            </ReactMarkdown>
            </div>
        )}
        </div>

        {/* Edit Button for User Messages */}
        {msg.role === "user" && onEdit && (
            <button 
                onClick={() => onEdit(msg.text, index)}
                className="text-[10px] text-gray-400 hover:text-blue-600 transition-colors flex items-center gap-1 mt-0.5 self-end mr-1"
            >
                <Pencil size={10} /> Edit
            </button>
        )}

        {/* Action Buttons (e.g. Choices or Entity Selection) */}
        {msg.role === "ai" && (choices || entitySelection) && (
            <div className="flex flex-col gap-2 mt-1 ml-1 duration-300">
                {(choices?.payload || entitySelection?.payload || []).map((opt: any, idx: number) => (
                    <button
                        key={idx}
                        onClick={() => onSelect && onSelect(opt.table_name || opt.label, opt.index)} 
                        className={`text-left text-xs transition-all p-3 rounded-xl shadow-sm flex items-center gap-2 group border ${
                            darkMode 
                            ? 'bg-gray-800 border-gray-700 hover:bg-gray-700 hover:border-blue-500 text-gray-200' 
                            : 'bg-white border-blue-200 hover:bg-blue-50 hover:border-blue-300 text-gray-700'
                        }`}
                    >
                        <div className={`w-1.5 h-1.5 rounded-full transition-colors ${darkMode ? 'bg-blue-500 group-hover:bg-blue-400' : 'bg-blue-400 group-hover:bg-blue-600'}`}></div>
                        <span className={`font-medium ${darkMode ? 'group-hover:text-blue-400' : 'group-hover:text-blue-800'}`}>{opt.label}</span>
                    </button>
                ))}
            </div>
        )}

        {/* Source Attribution & Confidence */}
        {msg.role === "ai" && sourcesAction && sourcesAction.payload && (
            <div className="flex flex-col gap-2 mt-2 w-full ml-1">
                <div className="flex flex-wrap gap-2">
                    {sourcesAction.payload.sources.map((src: any, idx: number) => (
                        <div 
                            key={idx}
                            className={`flex items-center gap-2 px-2.5 py-1 rounded-lg text-[10px] font-medium border shadow-sm ${
                                darkMode 
                                ? "bg-gray-800/50 border-gray-700 text-gray-400" 
                                : "bg-gray-50 border-gray-100 text-gray-600"
                            }`}
                        >
                            <FileText size={10} className="opacity-70" />
                            <span className="truncate max-w-[80px]">{src.filename}</span>
                            {src.pages && src.pages.length > 0 && (
                                <span className="opacity-60 border-l pl-1.5 border-gray-300 ml-0.5">
                                    P{src.pages.join(", ")}
                                </span>
                            )}
                            <button 
                                onClick={() => console.log("View source:", src.filename)}
                                className={`ml-1 font-bold ${darkMode ? "text-blue-400 hover:text-blue-300" : "text-blue-600 hover:text-blue-700"}`}
                            >
                                View
                            </button>
                        </div>
                    ))}
                </div>
                {sourcesAction.payload.confidence !== undefined && (
                    <div className="flex items-center gap-1.5 text-[10px] opacity-70">
                        <div className={`w-1.5 h-1.5 rounded-full ${
                            sourcesAction.payload.confidence > 80 ? "bg-green-500" : 
                            sourcesAction.payload.confidence > 50 ? "bg-yellow-500" : "bg-red-500"
                        }`}></div>
                        <span>Confidence: {sourcesAction.payload.confidence}%</span>
                    </div>
                )}
            </div>
        )}

        {/* Switch Mode Button */}
        {msg.role === "ai" && switchModeAction && (
            <div className="flex gap-2 mt-1 ml-1">
                <button
                    onClick={() => onSwitchMode && onSwitchMode(switchModeAction.payload)}
                    className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-xl text-xs font-bold hover:bg-blue-700 transition-all shadow-md"
                >
                    Switch to {switchModeAction.payload === "operations" ? "Operations" : "Assistant"}
                </button>
            </div>
        )}

        {/* SEARCHABLE RECORD SELECTOR (For Update/Delete) */}
        {msg.role === "ai" && recordSelection && recordSelection.payload && (
            <div className={`rounded-xl p-3 shadow-md mt-1 w-full max-w-xs flex flex-col gap-2 border ${darkMode ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-100'}`}>
                <div className="relative">
                    <input 
                        type="text"
                        placeholder="Search records..."
                        className={`w-full rounded-lg px-3 py-2 text-sm outline-none transition-all border ${
                            darkMode 
                            ? 'bg-gray-800 border-gray-700 text-white focus:ring-blue-900/50' 
                            : 'bg-gray-50 border-gray-100 focus:ring-blue-100'
                        }`}
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
                <div className="max-h-40 overflow-y-auto flex flex-col gap-1 scrollbar-thin">
                    {filteredRecords.length > 0 ? (
                        filteredRecords.map((r: any) => (
                            <button
                                key={r.id}
                                onClick={() => onSelect && onSelect(r.id.toString())}
                                className={`text-left text-xs p-2.5 rounded-lg transition-colors border border-transparent ${
                                    darkMode ? 'text-gray-300 hover:bg-gray-800 hover:border-gray-700' : 'text-gray-700 hover:bg-blue-50 hover:border-blue-100'
                                }`}
                            >
                                {r.label}
                            </button>
                        ))
                    ) : (
                        <span className="text-[10px] text-gray-400 text-center py-2">No matches found</span>
                    )}
                </div>
            </div>
        )}

        {/* NEW SMART FORM */}
        {msg.role === "ai" && formAction && formAction.payload && (() => {
          const resolvedTitle = 
            formAction?.payload?.display_title ?? 
            formAction?.payload?.label ?? 
            formAction?.payload?.table_name ?? 
            "Form";
          
          
          return (
            <DynamicForm 
                fields={formAction.payload.fields} 
                onSubmit={(data) => onSubmitForm && onSubmitForm(data)}
                onCancel={() => onSelect && onSelect("Cancel")}
                title={resolvedTitle}
                darkMode={darkMode}
            />
          );
        })()}

        {/* Legacy Form Request */}
        {msg.role === "ai" && formRequest && formRequest.payload && (
            <div className={`rounded-xl p-4 shadow-sm mt-1 w-full max-w-xs flex flex-col gap-3 border ${darkMode ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-100'}`}>
                <h4 className={`text-xs font-bold uppercase tracking-wider mb-1 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Enter Details: {formRequest.payload.entity}</h4>
                {formRequest.payload.fields.map((field: string) => (
                    <div key={field} className="flex flex-col gap-1">
                        <label className={`text-[10px] font-semibold uppercase ml-1 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>{field}</label>
                        <input 
                            type="text"
                            placeholder={`Enter ${field}...`}
                            onChange={(e) => setFormData(prev => ({...prev, [field]: e.target.value}))}
                            className={`rounded-lg px-3 py-2 text-sm outline-none transition-all border ${
                                darkMode 
                                ? 'bg-gray-800 border-gray-700 text-white focus:ring-blue-900/50' 
                                : 'bg-gray-50 border-gray-100 focus:ring-blue-100'
                            }`}
                        />
                    </div>
                ))}
                <button 
                    onClick={() => onSubmitForm && onSubmitForm(formData)}
                    className="mt-2 bg-blue-600 text-white py-2 rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors shadow-sm"
                >
                    Submit Details
                </button>
            </div>
        )}

        {/* Confirmation Buttons */}
        {msg.role === "ai" && confirmation && (
            <div className="flex gap-2 mt-2">
                <button 
                    onClick={() => onSelect && onSelect("Yes")}
                    className="bg-red-600 text-white px-6 py-2 rounded-xl text-sm font-semibold hover:bg-red-700 transition-all shadow-md"
                >
                    Confirm
                </button>
                <button 
                    onClick={() => onSelect && onSelect("Cancel")}
                    className={`px-6 py-2 rounded-xl text-sm font-semibold transition-all border ${
                        darkMode 
                        ? 'bg-gray-800 text-gray-400 border-gray-700 hover:bg-gray-700 hover:text-gray-300' 
                        : 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200'
                    }`}
                >
                    Cancel
                </button>
            </div>
        )}
    </div>
  );
});

MessageBubble.displayName = "MessageBubble";

export default function ChatWidget() {
  const { clientId, darkMode, setDarkMode } = useAdmin();
  const API_BASE = "/api";
  
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const recognitionRef = useRef<any>(null);
  const [chatMode, setChatMode] = useState<"assistant" | "operations">(() => {
    const saved = localStorage.getItem("amoeba_chat_mode");
    return (saved === "operations") ? "operations" : "assistant";
  });
  const [aiConfig, setAiConfig] = useState<{provider: string, model: string} | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>(() => localStorage.getItem("amoeba_selected_model") || "gemini-2.0-flash-lite");
  const [isEditingIndex, setIsEditingIndex] = useState<number | null>(null);
  const [editPreserveCount, setEditPreserveCount] = useState<number | null>(null);
  const [sources, setSources] = useState<{erp: boolean, documents: boolean, web: boolean}>(() => {
    try {
        const saved = localStorage.getItem("amoeba_chat_sources");
        const parsed = saved ? JSON.parse(saved) : { erp: true, documents: true, web: false };
        // Force web to false since it's disabled in backend
        return { ...parsed, web: false };
    } catch {
        return { erp: true, documents: true, web: false };
    }
  });
  const [showSourcesPopup, setShowSourcesPopup] = useState(false);
  const [promptHistory, setPromptHistory] = useState<string[]>(() => {
    try {
        const saved = localStorage.getItem("amoeba_prompt_history");
        return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [historyPointer, setHistoryPointer] = useState<number>(-1);
  
  useEffect(() => {
    localStorage.setItem("amoeba_selected_model", selectedModel);
  }, [selectedModel]);

  const hasInitialScrolled = useRef(false);

  // Persist sources selection
  useEffect(() => {
      localStorage.setItem("amoeba_chat_sources", JSON.stringify(sources));
  }, [sources]);

  // Chat Session Management
  const [currentSessionId, setCurrentSessionId] = useState<string>(() => {
    const saved = localStorage.getItem("amoeba_chat_session_id");
    if (saved) return saved;
    const newId = crypto.randomUUID();
    localStorage.setItem("amoeba_chat_session_id", newId);
    return newId;
  });

  const handleNewChat = useCallback(() => {
    const newId = crypto.randomUUID();
    setCurrentSessionId(newId);
    localStorage.setItem("amoeba_chat_session_id", newId);
    setMessages([]);
    hasFetchedRef.current = false;
    hasInitialScrolled.current = false;
    // We don't need to call fetchHistory because a new session won't have history
    // But we might want to tell the user it's a new chat
  }, []);

  // Sync chatMode to localStorage
  useEffect(() => {
      localStorage.setItem("amoeba_chat_mode", chatMode);
  }, [chatMode]);

  // Get API Key for payload
  const urlParams = new URLSearchParams(window.location.search);
  const currentApiKey = urlParams.get("api_key") || import.meta.env.VITE_API_KEY || "";
  const isWidgetMode = urlParams.get("mode") === "widget" || window.parent !== window;

  useEffect(() => {
      const state = isOpen ? "EXPANDED" : "COLLAPSED";
      
      window.parent.postMessage({
          type: "AMOEBA_RESIZE",
          state: state
      }, "*");
  }, [isOpen]);

  useEffect(() => {
      const handleMessage = async (event: MessageEvent) => {
          if (event.data && event.data.type === "AMOEBA_DISCOVERED_ROUTES") {
              try {
                  const res = await fetch(`${API_BASE}/routes/learn?api_key=${currentApiKey}`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(event.data.routes)
                  });
                  if(res.ok) { }
              } catch (err) {
                  console.error("❌ Failed to save routes:", err);
              }
          }

          if (event.data && event.data.type === "AMOEBA_DISCOVERED_FIELDS" && clientId) {
              try {
                  await fetch(`${API_BASE}/ui-schema`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                          client_id: clientId,
                          page_path: event.data.path,
                          fields: event.data.fields
                      })
                  });
              } catch (err) {
                  console.error("❌ UI Learning failed:", err);
              }
          }
      };
      
      window.addEventListener("message", handleMessage);
      return () => window.removeEventListener("message", handleMessage);
  }, [clientId, API_BASE, currentApiKey]);

  const socketRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const hasFetchedRef = useRef(false);

  const [attachment, setAttachment] = useState<{ name: string; path: string } | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const fetchHistory = useCallback(async () => {
    if (isEditingIndex !== null) return; // Prevent overwriting the UI while editing
    if (hasFetchedRef.current) return;

    setIsLoadingHistory(true);
    try {
      const res = await fetch(`${API_BASE}/history?api_key=${currentApiKey}&session_id=${currentSessionId}`);
      if (!res.ok) throw new Error("Failed to fetch history");
      const data = await res.json();


      const history = data.map((msg: any) => ({
        role: msg.role,
        text: msg.content,
        actions: msg.actions || [], 
        timestamp: msg.timestamp,
        is_edited: msg.is_edited
      }));

      setMessages(history);
      hasFetchedRef.current = true;

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
    } catch (err) {
      console.error("❌ History Error:", err);
      // If history fetch fails (e.g. 403), don't show infinite loader
      setMessages([]);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [currentApiKey, currentSessionId, API_BASE]);

  const setupWebSocket = useCallback(() => {

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host; 
    const urlParams = new URLSearchParams(window.location.search);
    const apiKey = urlParams.get("api_key") || import.meta.env.VITE_API_KEY || "";

    
    const wsUrl = `${protocol}//${host}/api/ws/chat?api_key=${apiKey}`;

    const ws = new WebSocket(wsUrl);

    // Heartbeat to keep connection alive

    ws.onopen = () => {
      setIsConnected(true);
      // heartbeatInterval = setInterval(() => {
      //     if (ws.readyState === WebSocket.OPEN) {
      //         ws.send(JSON.stringify({ type: "ping" }));
      //     }
      // }, 30000); // 30s heartbeat
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        
        // Ignore pong responses
        if (payload.type === "pong") return;

        if (payload.type === "done") {
             setIsTyping(false);
             return;
        }

        // 1. Text & Action Response
        if (payload.text) {
             setMessages((prev: ChatMessage[]) => {
                 const lastMsg = prev[prev.length - 1];
                 if (lastMsg && lastMsg.role === "ai") {
                     // Append to current AI message
                     const updated = [...prev];
                     updated[updated.length - 1] = {
                         ...lastMsg,
                         text: (lastMsg.text || "") + payload.text,
                         actions: payload.actions || lastMsg.actions || []
                     };
                     return updated;
                 } else {
                     // New AI message
                     return [...prev, { 
                         role: "ai" as const, 
                         text: payload.text,
                         actions: payload.actions || [],
                         timestamp: Date.now()
                     }];
                 }
             });
        }
        
        // 2. Parent Dispatch (for Navigation/etc)
        if (payload.actions && Array.isArray(payload.actions)) {
            payload.actions.forEach((action: any) => {
                // ... (existing logging)
                window.parent.postMessage({
                    type: "AMOEBA_ACTION",
                    action: action.type,
                    payload: action.payload
                }, "*"); 
            });
        }
      } catch (e) {
        setMessages((prev) => [...prev, { role: "ai", text: event.data, timestamp: Date.now() }]);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      setIsTyping(false); 
      setTimeout(() => {
        if (isOpen) {
          setupWebSocket();
        }
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error("❌ WebSocket Error:", error);
      setIsTyping(false);
    };

    socketRef.current = ws;
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && !socketRef.current) {
      fetchHistory().then(() => {
        setupWebSocket();
      });
    }

    return () => {
      if (!isOpen && socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [isOpen, fetchHistory, setupWebSocket]);

  useEffect(() => {
    if (!isLoadingHistory && messages.length > 0) {
        if (!hasInitialScrolled.current) {
            messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
            hasInitialScrolled.current = true;
        } else {
            messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
        }
    }
  }, [messages, isTyping, isLoadingHistory]);

  const sendMessage = (overrideText?: any) => {
    const textToProcess = typeof overrideText === 'string' ? overrideText : input;
    if ((!textToProcess.trim() && !attachment) || !socketRef.current || !isConnected) return;

    let textToSend = textToProcess;
    let displayInput = textToProcess;

    if (attachment) {
        const contextPrefix = `[SYSTEM: User uploaded file '${attachment.name}' at '${attachment.path}']\n`;
        textToSend = contextPrefix + input;
        displayInput = `📎 ${attachment.name}\n${input}`;
    }

    const userMessage = { role: "user" as const, text: displayInput };
    setMessages((prev) => [...prev, userMessage]);
    
    const payload = {
        text: textToSend,
        mode: chatMode,
        api_key: currentApiKey,
        session_id: currentSessionId,
        is_edit: false,
        sources,
        model: selectedModel
    };
    socketRef.current.send(JSON.stringify(payload));
    
    // History Persistence
    if (input.trim()) {
        const newHistory = [input, ...promptHistory.filter(h => h !== input)].slice(0, 50);
        setPromptHistory(newHistory);
        localStorage.setItem("amoeba_prompt_history", JSON.stringify(newHistory));
    }
    setHistoryPointer(-1);

    setInput("");
    setAttachment(null);
    setIsTyping(true); 
    setIsEditingIndex(null); 
  };

  const sendMessageEdited = () => {
    // Show Stop button immediately before any checks
    setIsTyping(true);

    if (!input.trim() || !socketRef.current || !isConnected) {
      setIsTyping(false);
      return;
    }
    
    // Capture current messages as context before optimistic update
    const preservedHistory = messages.map((m) => ({ role: m.role, content: m.text || "" }));

    setMessages((prev) => [...prev, { role: "user", text: input, is_edited: true }]);
    
    const payload = {
        text: input,
        mode: chatMode,
        api_key: currentApiKey,
        session_id: currentSessionId,
        is_edit: true,
        preserve_count: editPreserveCount ?? 0,
        history_context: preservedHistory,
        sources,
        model: selectedModel
    };
    
    socketRef.current.send(JSON.stringify(payload));
    
    // History Persistence
    if (input.trim()) {
        const newHistory = [input, ...promptHistory.filter(h => h !== input)].slice(0, 50);
        setPromptHistory(newHistory);
        localStorage.setItem("amoeba_prompt_history", JSON.stringify(newHistory));
    }
    setHistoryPointer(-1);

    setInput("");
    setIsEditingIndex(null);
    setEditPreserveCount(null);
  };

  const handleStop = () => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ type: "STOP" }));
    }
    setIsTyping(false);
  };

  const handleEdit = (text: string, index: number) => {
    setIsEditingIndex(index);
    setEditPreserveCount(index);
    // 1. Truncate conversation from this point
    setMessages((prev: ChatMessage[]) => prev.slice(0, index));
    // 2. Strip attachment prefix if present
    const cleanText = text.replace(/^📎 .*\n/, "");
    setInput(cleanText);
    setTimeout(() => {
        const textarea = document.querySelector('textarea');
        if (textarea) (textarea as HTMLTextAreaElement).focus();
    }, 10);
  };

  const clearMessages = () => {
    setMessages([]);
  };

  /* File Upload Handler */
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadingState, setUploadingState] = useState(false);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingState(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("client_id", String(clientId || "1"));

    try {
        const res = await fetch(`${API_BASE}/documents/upload`, {
            method: "POST",
            body: formData
        });
        
        if (!res.ok) {
            let errorMsg = "Upload failed";
            try {
                const errorData = await res.json();
                errorMsg = errorData.detail || errorMsg;
            } catch (jsonErr) {
                // If not JSON, get the plain text status or error message
                const textError = await res.text();
                errorMsg = textError || `Server Error (${res.status})`;
            }
            throw new Error(errorMsg);
        }
        
        const data = await res.json();
        setAttachment({ name: file.name, path: data.filepath || "" }); 
        showToast("File uploaded and ready!", "success");

    } catch (err: any) {
        const msg = err.message || "Error uploading file.";
        setMessages((prev) => [...prev, { role: "ai", text: `❌ ${msg}` }]);
        showToast(msg, "error");
    } finally {
        setUploadingState(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

    /* Helper to handle choice selection */
    const handleChoiceSelect = useCallback((label: string, index?: number) => {
        // Send the index if available, otherwise fallback to label
        const textToSend = index !== undefined ? index.toString() : label;
        
        // Show the label as a user message for visual consistency
        const userMessage = { role: "user" as const, text: label };
        setMessages((prev) => [...prev, userMessage]);
        
        if (socketRef.current && isConnected) {
             const payload = {
                 text: textToSend,
                 mode: chatMode,
                 api_key: currentApiKey,
                 session_id: currentSessionId,
                 sources,
                 model: selectedModel
             };
             socketRef.current.send(JSON.stringify(payload));
             setIsTyping(true);
        }
    }, [isConnected, chatMode, currentApiKey, currentSessionId]);

    /* Helper to handle form submission */
    const handleFormSubmit = useCallback((data: any) => {
        const text = JSON.stringify(data);
        const userMessage = { role: "user" as const, text: "Submitted form details." };
        setMessages((prev) => [...prev, userMessage]);
        
        if (socketRef.current && isConnected) {
             const payload = {
                 text: text,
                 mode: chatMode,
                 api_key: currentApiKey,
                 session_id: currentSessionId,
                 sources,
                 model: selectedModel
             };
             socketRef.current.send(JSON.stringify(payload));
             setIsTyping(true);
        }
    }, [isConnected, chatMode, currentApiKey, currentSessionId]);

  const handleSwitchAndResend = useCallback((newMode: "assistant" | "operations") => {
    setChatMode(newMode);
    
    // Find last user message to resend
    const lastUserMsg = [...messages].reverse().find(m => m.role === "user");
    if (lastUserMsg && socketRef.current && isConnected) {
        const payload = {
            text: lastUserMsg.text,
            mode: newMode,
            api_key: currentApiKey,
            session_id: currentSessionId,
            sources,
            model: selectedModel
        };
        socketRef.current.send(JSON.stringify(payload));
        setIsTyping(true);
    }
  }, [messages, isConnected, currentApiKey, currentSessionId]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (isEditingIndex !== null) {
            sendMessageEdited();
        } else {
            sendMessage();
        }
    } else if (e.key === "ArrowUp") {
        const isAtStart = e.currentTarget.selectionStart === 0;
        if (isAtStart) {
            e.preventDefault();
            const nextPointer = historyPointer + 1;
            if (nextPointer < promptHistory.length) {
                setHistoryPointer(nextPointer);
                setInput(promptHistory[nextPointer]);
            }
        }
    } else if (e.key === "ArrowDown" && historyPointer !== -1) {
        e.preventDefault();
        const nextPointer = historyPointer - 1;
        if (nextPointer >= 0) {
            setHistoryPointer(nextPointer);
            setInput(promptHistory[nextPointer]);
        } else {
            setHistoryPointer(-1);
            setInput("");
        }
    }
  };

  const startListening = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      return;
    }
    
    const startingText = input.trim() ? input.trim() + " " : "";
    let finalDetected = "";
    
    if (!recognitionRef.current) {
        recognitionRef.current = new SpeechRecognition();
        recognitionRef.current.continuous = false;
        recognitionRef.current.interimResults = true;
        recognitionRef.current.lang = "en-US";
        
        recognitionRef.current.onerror = (event: any) => {
            if (event.error === 'not-allowed' || event.error === 'denied') {
                alert("Microphone access required. Please check your browser permissions.");
            }
            setIsListening(false);
        };
    }
    
    recognitionRef.current.onend = () => {
        setIsListening(false);
        if (finalDetected.trim()) {
            sendMessage(startingText + finalDetected);
        }
    };
    
    recognitionRef.current.onresult = (event: any) => {
        let interimTranscript = '';
        let currentFinal = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                currentFinal += event.results[i][0].transcript;
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }
        
        finalDetected += currentFinal;
        setInput(startingText + finalDetected + interimTranscript);
    };

    try {
        recognitionRef.current.start();
        setIsListening(true);
    } catch (e) {
        console.error("Speech recognition error:", e);
        setIsListening(false);
    }
  };

  return (
    <div className={`${isWidgetMode ? "relative w-full h-full flex flex-col items-end justify-end" : "fixed bottom-5 right-5 z-50 flex flex-col items-end"} font-sans transition-theme`}>
      {isOpen && (
        <div className={`w-96 h-[550px] shadow-2xl rounded-2xl border flex flex-col ${isWidgetMode ? "mb-0" : "mb-4"} overflow-hidden transition-all duration-300 ease-in-out transition-theme ${darkMode ? 'bg-gray-900 border-gray-800' : 'bg-white border-gray-200'}`}>
          {/* Header */}
          <div className={`p-4 text-white flex flex-col gap-4 shadow-lg z-10 flex-shrink-0 transition-theme ${darkMode ? 'bg-gray-900' : 'bg-slate-900'}`}>
            <div className="flex justify-between items-center w-full min-h-[40px]">
                <div className="flex items-center gap-3">
                    <div className="bg-blue-600 p-2 rounded-xl shadow-inner">
                        <MessageCircle size={18} />
                    </div>
                    <div className="flex flex-col">
                        <div className="flex items-center gap-2">
                            <span className="text-sm font-bold tracking-tight text-white/95">Amoeba AI</span>
                            {/* Model Selector Mini */}
                            <div className={`flex p-0.5 rounded-lg items-center gap-0.5 shadow-inner ${darkMode ? 'bg-gray-800' : 'bg-slate-800'}`}>
                                <button 
                                    onClick={(e) => { e.stopPropagation(); setSelectedModel("gemini-2.0-flash-lite"); }}
                                    className={`p-1 rounded-md transition-all ${selectedModel.includes("gemini") ? (darkMode ? 'bg-blue-600 text-white' : 'bg-blue-500 text-white shadow-sm') : 'text-gray-500 hover:text-gray-400'}`}
                                    title="Gemini"
                                >
                                    <Brain size={10} />
                                </button>
                                <button 
                                    onClick={(e) => { e.stopPropagation(); setSelectedModel("llama3:latest"); }}
                                    className={`p-1 rounded-md transition-all ${selectedModel.includes("llama") ? (darkMode ? 'bg-purple-600 text-white' : 'bg-purple-500 text-white shadow-sm') : 'text-gray-500 hover:text-gray-400'}`}
                                    title="Ollama"
                                >
                                    <Cpu size={10} />
                                </button>
                            </div>
                        </div>
                        <div className="flex items-center gap-1.5 ">
                            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.5)]" : "bg-red-500 animate-pulse"}`} />
                            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                                {isLoadingHistory ? "Syncing..." : isConnected ? "Online" : "Connecting..."}
                            </span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => window.open(`/ai?api_key=${currentApiKey}`, '_blank')}
                        className="hover:bg-white/10 p-2 rounded-xl transition-all duration-200 text-gray-400 hover:text-white"
                        title="Open Full Chat"
                    >
                        <Maximize size={16} />
                    </button>
                    <button
                        onClick={handleNewChat}
                        className="hover:bg-white/10 p-2 rounded-xl transition-all duration-200 text-gray-400 hover:text-white"
                        title="New chat"
                    >
                        <Plus size={16} />
                    </button>
                    <button
                        onClick={clearMessages}
                        className="hover:bg-white/10 p-2 rounded-xl transition-all duration-200 text-gray-400 hover:text-white"
                        title="Clear history"
                    >
                        <Trash2 size={16} />
                    </button>
                    <button
                        onClick={() => setDarkMode(!darkMode)}
                        className="hover:bg-white/10 p-2 rounded-xl transition-all duration-200 text-gray-400 hover:text-white"
                        title={darkMode ? "Light Mode" : "Dark Mode"}
                    >
                        {darkMode ? <Sun size={16} /> : <Moon size={16} />}
                    </button>
                    <button
                        onClick={() => setIsOpen(false)}
                        className="hover:bg-red-500/20 p-2 rounded-xl transition-all duration-200 text-gray-400 hover:text-red-400"
                        title="Close chat"
                    >
                        <X size={16} />
                    </button>
                </div>
            </div>

            <div className="flex items-center justify-between gap-3">
                <div className={`flex p-1 rounded-2xl items-center gap-1 w-full ${darkMode ? 'bg-gray-800' : 'bg-slate-800'}`}>
                    <button 
                        onClick={() => handleSwitchAndResend("assistant")}
                        className={`flex-1 py-1.5 rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all duration-300 ${chatMode === "assistant" ? (darkMode ? 'bg-gray-700 text-blue-400 shadow-md ring-1 ring-white/5' : 'bg-slate-700 text-white shadow-md border border-slate-600') : 'text-gray-500 hover:text-gray-300'}`}
                    >
                        Assistant
                    </button>
                    <button 
                        onClick={() => handleSwitchAndResend("operations")}
                        className={`flex-1 py-1.5 rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all duration-300 ${chatMode === "operations" ? (darkMode ? 'bg-gray-700 text-blue-400 shadow-md ring-1 ring-white/5' : 'bg-slate-700 text-white shadow-md border border-slate-600') : 'text-gray-500 hover:text-gray-300'}`}
                    >
                        Operations
                    </button>
                </div>
                {aiConfig && (
                    <div className="flex flex-col items-end">
                        <span className={`text-[10px] font-black tracking-[0.2em] uppercase whitespace-nowrap opacity-80 ${darkMode ? 'text-blue-500' : 'text-blue-400'}`}>
                            {aiConfig.model.split(':')[0]}
                        </span>
                    </div>
                )}
            </div>
            
          </div>

          {/* Messages Area */}
          <div className={`flex-1 p-4 overflow-y-auto overflow-x-hidden flex flex-col gap-3 scrollbar-custom transition-colors transition-theme ${darkMode ? 'bg-gray-950' : 'bg-gray-50'}`}>
            {isLoadingHistory ? (
              <div className="flex flex-col items-center justify-center h-full gap-2">
                <Loader2 className="animate-spin text-blue-500" size={32} />
                <p className="text-gray-400 text-xs font-medium uppercase tracking-wide">Loading history...</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 text-center px-6">
                <div className={`p-4 rounded-full mb-3 ${darkMode ? 'bg-gray-900 border border-gray-800 shadow-inner' : 'bg-gray-100'}`}>
                    <MessageCircle size={32} className={darkMode ? 'text-gray-700' : 'text-gray-300'} />
                </div>
                <p className={`font-medium ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>Amoeba is ready!</p>
                <p className={`text-xs mt-1 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>Ask me to generate reports, write blogs, or navigate the app.</p>
                {aiConfig && (
                  <p className="text-[10px] mt-2 text-gray-300 font-medium">
                    Powered by {aiConfig.model.split(':')[0]} ({aiConfig.provider})
                  </p>
                )}
              </div>
            ) : (
              <>
                {messages.map((msg, i) => (
                  <div key={i} className="group flex flex-col">
                    <MessageBubble 
                      msg={msg} 
                      index={i}
                      onSelect={handleChoiceSelect} 
                      onSubmitForm={handleFormSubmit} 
                      onSwitchMode={handleSwitchAndResend}
                      onEdit={handleEdit}
                      darkMode={darkMode}
                    />
                  </div>
                ))}
                
                {/* Typing Indicator Bubble */}
                {isTyping && (
                  <div className={`self-start rounded-2xl rounded-bl-sm p-3.5 shadow-sm flex items-center gap-1 w-16 h-10 border transition-colors ${darkMode ? 'bg-gray-800 border-gray-700 shadow-gray-950/50' : 'bg-white border-gray-100'}`}>
                    <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                    <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                    <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"></div>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input Area */}
          <div className={`p-3 border-t flex flex-col gap-2 transition-theme ${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100'}`}>
            
            {/* Attachment Chip */}
            {attachment && (
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg w-fit text-sm animate-in fade-in slide-in-from-bottom-2 transition-colors ${
                    darkMode ? 'bg-blue-900/40 text-blue-300' : 'bg-blue-50 text-blue-700'
                }`}>
                    <Paperclip size={14} />
                    <span className="font-medium truncate max-w-[200px]">{attachment.name}</span>
                    <button 
                        onClick={() => setAttachment(null)}
                        className={`rounded-full p-0.5 ml-1 transition-colors ${darkMode ? 'hover:bg-blue-800' : 'hover:bg-blue-100'}`}
                    >
                        <X size={14} />
                    </button>
                </div>
            )}

            <div className="flex gap-2 items-end">
            {/* Hidden File Input */}
            <input 
                type="file" 
                ref={fileInputRef} 
                className="hidden" 
                onChange={handleFileSelect}
                accept=".csv,.xlsx,.xls,.pdf,.docx,.txt" 
            />
            
            {/* Sources Popup */}
            {showSourcesPopup && chatMode === "assistant" && (
                <div
                    className={`absolute bottom-[72px] left-3 z-50 w-64 rounded-2xl shadow-2xl border overflow-hidden ${
                        darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                    }`}
                    style={{ animation: 'fadeSlideUp 0.15s ease-out' }}
                >
                    <div className={`px-4 py-3 border-b ${ darkMode ? 'border-gray-700' : 'border-gray-100' }`}>
                        <span className={`text-xs font-bold uppercase tracking-widest ${ darkMode ? 'text-gray-400' : 'text-gray-500' }`}>Sources</span>
                    </div>
                    {/* ERP Data */}
                    <div className={`flex items-center gap-3 px-4 py-3 border-b ${ darkMode ? 'border-gray-700/50' : 'border-gray-50' }`}>
                        <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${ darkMode ? 'bg-gray-700' : 'bg-gray-100' }`}>
                            <Building2 size={16} className={darkMode ? 'text-gray-300' : 'text-gray-600'} />
                        </div>
                        <span className={`flex-1 text-sm font-medium ${ darkMode ? 'text-gray-200' : 'text-gray-800' }`}>Search company knowledge</span>
                        <button
                            onClick={() => setSources(s => ({...s, erp: !s.erp}))}
                            className={`relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0 ${ sources.erp ? 'bg-green-500' : (darkMode ? 'bg-gray-600' : 'bg-gray-200') }`}
                        >
                            <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300 ${ sources.erp ? 'translate-x-5' : 'translate-x-0' }`} />
                        </button>
                    </div>
                    {/* Documents */}
                    <div className={`flex items-center gap-3 px-4 py-3 border-b ${ darkMode ? 'border-gray-700/50' : 'border-gray-50' }`}>
                        <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${ darkMode ? 'bg-gray-700' : 'bg-gray-100' }`}>
                            <FileText size={16} className={darkMode ? 'text-gray-300' : 'text-gray-600'} />
                        </div>
                        <span className={`flex-1 text-sm font-medium ${ darkMode ? 'text-gray-200' : 'text-gray-800' }`}>Search documents</span>
                        <button
                            onClick={() => setSources(s => ({...s, documents: !s.documents}))}
                            className={`relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0 ${ sources.documents ? 'bg-green-500' : (darkMode ? 'bg-gray-600' : 'bg-gray-200') }`}
                        >
                            <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300 ${ sources.documents ? 'translate-x-5' : 'translate-x-0' }`} />
                        </button>
                    </div>
                    {/* Web - DISABLED for now */}
                    {/* 
                    <div className="flex items-center gap-3 px-4 py-3">
                        <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${ darkMode ? 'bg-gray-700' : 'bg-gray-100' }`}>
                            <Globe size={16} className={darkMode ? 'text-gray-300' : 'text-gray-600'} />
                        </div>
                        <span className={`flex-1 text-sm font-medium ${ darkMode ? 'text-gray-200' : 'text-gray-800' }`}>Include web results</span>
                        <button
                            onClick={() => setSources(s => ({...s, web: !s.web}))}
                            className={`relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0 ${ sources.web ? 'bg-green-500' : (darkMode ? 'bg-gray-600' : 'bg-gray-200') }`}
                        >
                            <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300 ${ sources.web ? 'translate-x-5' : 'translate-x-0' }`} />
                        </button>
                    </div>
                    */}
                </div>
            )}

            <button
                onClick={() => fileInputRef.current?.click()}
                disabled={!isConnected || isLoadingHistory || uploadingState}
                className={`p-3 rounded-full transition-all flex-shrink-0 mb-0.5 ${
                    darkMode ? 'bg-gray-700 text-gray-400 hover:bg-gray-600' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}
                title="Attach file"
            >
                {uploadingState ? <Loader2 size={18} className="animate-spin" /> : <Paperclip size={18} />}
            </button>

            {/* Sources Icon Button — Assistant mode only */}
            {chatMode === "assistant" && (
                <button
                    onClick={() => setShowSourcesPopup(p => !p)}
                    className={`relative p-3 rounded-full transition-all flex-shrink-0 mb-0.5 ${
                        showSourcesPopup
                            ? 'bg-blue-600 text-white'
                            : (darkMode ? 'bg-gray-700 text-gray-400 hover:bg-gray-600' : 'bg-gray-100 text-gray-500 hover:bg-gray-200')
                    }`}
                    title="Select sources"
                >
                    <SlidersHorizontal size={18} />
                    {/* Dot indicator when any non-default source is toggled */}
                    {(sources.web || !sources.erp || !sources.documents) && (
                        <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-blue-400 border border-white" />
                    )}
                </button>
            )}

            <div className="relative flex-1 flex items-center">
                <textarea
                  className={`w-full border-0 rounded-2xl px-4 py-3 pr-10 text-sm outline-none transition-theme disabled:opacity-50 resize-none max-h-32 min-h-[44px] ${
                      darkMode 
                      ? 'bg-gray-700 text-white focus:bg-gray-600 focus:ring-2 focus:ring-blue-900/50 placeholder-gray-500' 
                      : 'bg-gray-100 text-gray-900 focus:bg-white focus:ring-2 focus:ring-blue-100'
                  }`}
                  rows={1}
                  value={input}
                  disabled={!isConnected || isLoadingHistory}
                  onChange={(e) => {
                      setInput(e.target.value);
                      if (historyPointer !== -1 && e.target.value !== promptHistory[historyPointer]) {
                          setHistoryPointer(-1);
                      }
                  }}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    isListening
                      ? "Listening..."
                      : isLoadingHistory
                      ? "Loading..."
                      : isConnected
                      ? "Ask or attach a file..."
                      : "Connecting..."
                  }
                />
                {speechSupported && (
                    <button
                        onClick={isListening ? () => recognitionRef.current?.stop() : startListening}
                        disabled={!isConnected || isLoadingHistory}
                        className={`absolute right-3 p-1.5 rounded-full transition-colors ${
                            isListening 
                            ? 'text-red-500 bg-red-100 dark:bg-red-900/40 animate-pulse' 
                            : darkMode ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-600' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-200'
                        }`}
                        title={isListening ? "Stop listening" : "Voice Input"}
                    >
                        <Mic size={18} />
                    </button>
                )}
            </div>
            {isTyping ? (
                <button
                onClick={handleStop}
                className="p-3 rounded-full bg-red-500 text-white hover:bg-red-600 transition-all flex-shrink-0 mb-0.5"
                title="Stop generation"
                >
                <Square size={18} fill="currentColor" />
                </button>
            ) : (
                <button
                onClick={sendMessage}
                disabled={!isConnected || !input.trim() || isLoadingHistory}
                className={`p-3 rounded-full transition-all duration-200 flex-shrink-0 mb-0.5 ${
                    !isConnected || !input.trim() || isLoadingHistory 
                    ? (darkMode ? 'bg-gray-700 text-gray-500' : 'bg-gray-100 text-gray-400') 
                    : "bg-blue-600 text-white hover:bg-blue-700 hover:shadow-lg hover:scale-105"
                }`}
                >
                {isLoadingHistory ? (
                    <Loader2 size={18} className="animate-spin" />
                ) : isConnected ? (
                    <Send size={18} className={input.trim() ? "translate-x-0.5" : ""} />
                ) : (
                    <Loader2 size={18} className="animate-spin" />
                )}
                </button>
            )}
          </div>
          </div>
        </div>
      )}

      {!isOpen && (
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={`group relative flex items-center justify-center w-14 h-14 rounded-full shadow-2xl transition-all duration-300 hover:scale-110 active:scale-95 bg-gradient-to-br from-blue-600 to-blue-700 hover:shadow-blue-500/30`}
          title="Open chat"
        >
          <MessageCircle size={26} className="text-white transition-transform duration-300 group-hover:-rotate-12" />
          
          {isConnected && (
              <span className="absolute top-0 right-0 flex h-3.5 w-3.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-green-500 border-2 border-white"></span>
              </span>
          )}
        </button>
      )}
        {/* Toast Notifications */}
        {toast && (
          <div className={`fixed bottom-24 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-2 px-4 py-3 rounded-xl shadow-2xl border animate-in fade-in slide-in-from-bottom-4 transition-all ${
            toast.type === 'success' 
              ? (darkMode ? 'bg-green-900/90 border-green-800 text-green-100' : 'bg-green-50 border-green-100 text-green-800')
              : toast.type === 'error'
              ? (darkMode ? 'bg-red-900/90 border-red-800 text-red-100' : 'bg-red-50 border-red-100 text-red-800')
              : (darkMode ? 'bg-blue-900/90 border-blue-800 text-blue-100' : 'bg-blue-50 border-blue-100 text-blue-800')
          }`}>
            {toast.type === 'success' && <CheckCircle2 size={18} className="text-green-500" />}
            {toast.type === 'error' && <AlertCircle size={18} className="text-red-500" />}
            {toast.type === 'info' && <Loader2 size={18} className="animate-spin text-blue-500" />}
            <span className="text-sm font-medium">{toast.message}</span>
          </div>
        )}

      <style>{`
        .transition-theme {
            transition: all 0.3s ease-in-out !important;
        }
        .scrollbar-custom::-webkit-scrollbar {
          width: 6px;
        }
        .scrollbar-custom::-webkit-scrollbar-track {
          background: transparent;
        }
        .scrollbar-custom::-webkit-scrollbar-thumb {
          background: ${darkMode ? "#374151" : "#e5e7eb"};
          border-radius: 10px;
        }
        .scrollbar-custom::-webkit-scrollbar-thumb:hover {
          background: ${darkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)'};
          background-clip: content-box;
        }
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .animate-in {
            animation: fadeSlideUp 0.2s ease-out;
        }
      `}</style>
    </div>
  );
}
