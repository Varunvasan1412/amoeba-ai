import { useState, useEffect, useRef, useCallback, memo } from "react";
import { MessageCircle, X, Send, Loader2, Trash2, Paperclip, Maximize } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import DynamicForm from "./DynamicForm";
import { useAdmin } from "../context/AdminContext";

type ChatMessage = {
  role: "user" | "ai";
  text: string;
  actions?: any[]; 
};

// Memoized Message Bubble for performance
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
        className={`p-3.5 rounded-2xl text-sm shadow-sm break-words leading-relaxed ${
            msg.role === "user"
            ? "bg-blue-600 text-white rounded-br-sm" 
            : "bg-white text-gray-800 border border-gray-100 rounded-bl-sm shadow-[0_2px_8px_-4px_rgba(0,0,0,0.1)]"
        }`}
        >
        {msg.role === "user" ? (
            msg.text
        ) : (choices || entitySelection || recordSelection || formAction || formRequest || confirmation || success || switchModeAction) ? (
            <div className="whitespace-pre-wrap text-gray-800 font-sans text-sm">
                {msg.text}
                {success && (
                    <div className="mt-2 text-green-600 font-bold flex items-center gap-2">
                        <span>✅</span> {success.payload}
                    </div>
                )}
            </div>
        ) : (
            <div className="prose prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-li:my-0 prose-pre:bg-gray-50 prose-pre:text-gray-700 overflow-hidden">
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

        {/* Action Buttons (e.g. Choices or Entity Selection) */}
        {msg.role === "ai" && (choices || entitySelection) && (
            <div className="flex flex-col gap-2 mt-1 ml-1 duration-300">
                {(choices?.payload || entitySelection?.payload || []).map((opt: any, idx: number) => (
                    <button
                        key={idx}
                        onClick={() => onSelect && onSelect(opt.table_name || opt.label, opt.index)} 
                        className="text-left text-xs bg-white border border-blue-200 hover:bg-blue-50 hover:border-blue-300 transition-colors p-3 rounded-xl shadow-sm flex items-center gap-2 group"
                    >
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-400 group-hover:bg-blue-600 transition-colors"></div>
                        <span className="font-medium text-gray-700 group-hover:text-blue-800">{opt.label}</span>
                    </button>
                ))}
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
            <div className="bg-white border border-gray-100 rounded-xl p-3 shadow-md mt-1 w-full max-w-xs flex flex-col gap-2">
                <div className="relative">
                    <input 
                        type="text"
                        placeholder="Search records..."
                        className="w-full bg-gray-50 border border-gray-100 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-100 mb-1"
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
                                className="text-left text-xs p-2.5 hover:bg-blue-50 rounded-lg transition-colors border border-transparent hover:border-blue-100"
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
        {msg.role === "ai" && formAction && formAction.payload && (
            <DynamicForm 
                fields={formAction.payload.fields} 
                onSubmit={(data) => onSubmitForm && onSubmitForm(data)}
                onCancel={() => onSelect && onSelect("Cancel")}
                title={formAction.payload.table_name}
            />
        )}

        {/* Legacy Form Request */}
        {msg.role === "ai" && formRequest && formRequest.payload && (
            <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm mt-1 w-full max-w-xs flex flex-col gap-3">
                <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Enter Details: {formRequest.payload.entity}</h4>
                {formRequest.payload.fields.map((field: string) => (
                    <div key={field} className="flex flex-col gap-1">
                        <label className="text-[10px] font-semibold text-gray-400 uppercase ml-1">{field}</label>
                        <input 
                            type="text"
                            placeholder={`Enter ${field}...`}
                            onChange={(e) => setFormData(prev => ({...prev, [field]: e.target.value}))}
                            className="bg-gray-50 border border-gray-100 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 outline-none"
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
                    className="bg-gray-100 text-gray-600 px-6 py-2 rounded-xl text-sm font-semibold hover:bg-gray-200 transition-all border border-gray-200"
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
  const { clientId } = useAdmin();
  const API_BASE = import.meta.env.DEV ? "http://localhost:8000/api" : "/api";
  
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  const [chatMode, setChatMode] = useState<"assistant" | "operations">("assistant");
  const [aiConfig, setAiConfig] = useState<{provider: string, model: string} | null>(null);

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
    // We don't need to call fetchHistory because a new session won't have history
    // But we might want to tell the user it's a new chat
  }, []);

  // Get API Key for payload
  const urlParams = new URLSearchParams(window.location.search);
  const currentApiKey = urlParams.get("api_key") || import.meta.env.VITE_API_KEY || "";

  useEffect(() => {
      const state = isOpen ? "EXPANDED" : "COLLAPSED";
      console.log(`📡 Posting Message to Parent: AMOEBA_RESIZE -> ${state}`);
      
      window.parent.postMessage({
          type: "AMOEBA_RESIZE",
          state: state
      }, "*");
  }, [isOpen]);

  useEffect(() => {
      const handleMessage = async (event: MessageEvent) => {
          if (event.data && event.data.type === "AMOEBA_DISCOVERED_ROUTES") {
              console.log("🧠 Learning Routes:", event.data.routes);
              try {
                  const res = await fetch(`${API_BASE}/routes/learn?api_key=${currentApiKey}`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(event.data.routes)
                  });
                  if(res.ok) console.log("✅ Routes Saved to Brain!");
              } catch (err) {
                  console.error("❌ Failed to save routes:", err);
              }
          }

          if (event.data && event.data.type === "AMOEBA_DISCOVERED_FIELDS" && clientId) {
              console.log(`🧠 [UI LEARNING] Received ${event.data.fields.length} fields from Parent DOM`);
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
                  console.log("✅ UI Schema Updated in Brain!");
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

  const [attachment, setAttachment] = useState<{name: string, path: string} | null>(null);

  const fetchHistory = useCallback(async () => {
    if (hasFetchedRef.current) return;

    setIsLoadingHistory(true);
    try {
      const res = await fetch(`${API_BASE}/history?api_key=${currentApiKey}&session_id=${currentSessionId}`);
      if (!res.ok) throw new Error("Failed to fetch history");
      const data = await res.json();

      console.log(`✅ History Loaded: ${data.length} messages for session ${currentSessionId}`);

      const history = data.map((msg: any) => ({
        role: msg.role,
        text: msg.content,
        actions: msg.actions || [], // 🔥 Preserve actions from history if they exist
        timestamp: msg.timestamp || Date.now()
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
    console.log("🔌 Setting up WebSocket...");

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host; 
    const urlParams = new URLSearchParams(window.location.search);
    const apiKey = urlParams.get("api_key") || import.meta.env.VITE_API_KEY || "";
    console.log("API KEY:", apiKey);

    
    const wsUrl = `${protocol}//${host}/api/ws/chat?api_key=${apiKey}`;

    const ws = new WebSocket(wsUrl);

    // Heartbeat to keep connection alive
    let heartbeatInterval: any;

    ws.onopen = () => {
      console.log("🟢 WebSocket Connected");
      setIsConnected(true);
      heartbeatInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "ping" }));
          }
      }, 30000); // 30s heartbeat
    };

    ws.onmessage = (event) => {
      console.log("📩 New AI Message:", event.data);
      setIsTyping(false); 
      
      try {
        const payload = JSON.parse(event.data);
        
        // Ignore pong responses
        if (payload.type === "pong") return;

        // 1. Text & Action Response
        if (payload.text) {
             const newMessage = { 
                 role: "ai" as const, 
                 text: payload.text,
                 actions: payload.actions || [],
                 timestamp: Date.now()
             };
             setMessages((prev) => [...prev, newMessage]);
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
      console.log("🔴 WebSocket Disconnected");
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
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const sendMessage = () => {
    if ((!input.trim() && !attachment) || !socketRef.current || !isConnected) return;

    let textToSend = input;
    let displayInput = input;

    if (attachment) {
        const contextPrefix = `[SYSTEM: User uploaded file '${attachment.name}' at '${attachment.path}']\n`;
        textToSend = contextPrefix + input;
        displayInput = `📎 ${attachment.name}\n${input}`;
    }

    const userMessage = { role: "user" as const, text: displayInput };
    setMessages((prev) => [...prev, userMessage]);
    
    // JSON Payload
    const payload = {
        text: textToSend,
        mode: chatMode,
        api_key: currentApiKey,
        session_id: currentSessionId
    };
    socketRef.current.send(JSON.stringify(payload));
    
    setInput("");
    setAttachment(null);
    setIsTyping(true); 
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

    try {
        const res = await fetch(`${API_BASE}/upload`, {
            method: "POST",
            body: formData
        });
        
        if (!res.ok) throw new Error("Upload failed");
        
        const data = await res.json();
        setAttachment({ name: file.name, path: data.filepath });
        console.log("📎 File attached:", file.name);

    } catch (err) {
        setMessages((prev) => [...prev, { role: "ai", text: "❌ Error uploading file." }]);
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
                 session_id: currentSessionId
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
                 session_id: currentSessionId
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
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end font-sans">
      {isOpen && (
        <div className="w-96 h-[500px] bg-white shadow-2xl rounded-2xl border border-gray-200 flex flex-col mb-4 overflow-hidden transition-all duration-300 ease-in-out">
          {/* Header */}
          <div className="bg-gradient-to-r from-gray-900 to-gray-800 p-4 text-white font-bold flex flex-col gap-3 shadow-md">
            <div className="flex justify-between items-center w-full">
                <div className="flex items-center gap-3">
                <div className="bg-white/10 p-1.5 rounded-full">
                    <MessageCircle size={18} />
                </div>
                <div className="flex flex-col">
                    <span>Amoeba AI</span>
                    <div className="flex items-center gap-1.5 ">
                        <div
                            className={`w-2 h-2 rounded-full ${
                            isConnected ? "bg-green-400" : "bg-red-500 animate-pulse"
                            }`}
                        />
                        <span className="text-[10px] font-normal text-gray-300 opacity-80">
                            {isLoadingHistory ? "Syncing..." : isConnected ? "Online" : "Connecting..."}
                        </span>
                        {aiConfig && (
                          <span className="text-[9px] font-medium bg-white/10 px-1.5 py-0.5 rounded-full text-blue-300 ml-1">
                            🧠 {aiConfig.model.split(':')[0]} · {aiConfig.provider}
                          </span>
                        )}
                    </div>
                </div>
                </div>
                <div className="flex gap-1">
                <button
                    onClick={() => window.open(`/ai?api_key=${currentApiKey}`, '_blank')}
                    className="hover:bg-white/10 p-1.5 rounded-full transition-colors text-gray-300 hover:text-white"
                    title="Open Full Chat"
                >
                    <Maximize size={16} />
                </button>
                <button
                    onClick={handleNewChat}
                    className="hover:bg-white/10 p-1.5 rounded-full transition-colors text-gray-300 hover:text-white"
                    title="New chat"
                >
                    <Send size={16} />
                </button>
                <button
                    onClick={clearMessages}
                    className="hover:bg-white/10 p-1.5 rounded-full transition-colors text-gray-300 hover:text-white"
                    title="Clear history"
                >
                    <Trash2 size={16} />
                </button>
                <button
                    onClick={() => setIsOpen(false)}
                    className="hover:bg-white/10 p-1.5 rounded-full transition-colors text-gray-300 hover:text-white"
                    title="Close chat"
                >
                    <X size={18} />
                </button>
                </div>
            </div>

            {/* Mode Toggle */}
            <div className="flex bg-black/20 p-1 rounded-xl items-center gap-1 self-center w-full max-w-[280px]">
                <button 
                    onClick={() => setChatMode("assistant")}
                    className={`flex-1 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-wider transition-all ${chatMode === "assistant" ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-400 hover:text-white'}`}
                >
                    Assistant
                </button>
                <button 
                    onClick={() => setChatMode("operations")}
                    className={`flex-1 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-wider transition-all ${chatMode === "operations" ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-400 hover:text-white'}`}
                >
                    Operations
                </button>
            </div>
          </div>

          {/* Messages Area */}
          <div className="flex-1 p-4 overflow-y-auto overflow-x-hidden bg-gray-50 flex flex-col gap-3 scrollbar-thin scrollbar-thumb-gray-200">
            {isLoadingHistory ? (
              <div className="flex flex-col items-center justify-center h-full gap-2">
                <Loader2
                  className="animate-spin text-blue-500"
                  size={32}
                />
                <p className="text-gray-400 text-xs font-medium uppercase tracking-wide">Loading history...</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 text-center px-6">
                <div className="bg-gray-100 p-4 rounded-full mb-3">
                    <MessageCircle size={32} className="text-gray-300" />
                </div>
                <p className="font-medium text-gray-600">Amoeba is ready!</p>
                <p className="text-xs mt-1 text-gray-400">Ask me to generate reports, write blogs, or navigate the app.</p>
                {aiConfig && (
                  <p className="text-[10px] mt-2 text-gray-300 font-medium">
                    Powered by {aiConfig.model.split(':')[0]} ({aiConfig.provider})
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
                
                {/* Typing Indicator Bubble */}
                {isTyping && (
                  <div className="bg-white border border-gray-100 self-start rounded-2xl rounded-bl-sm p-3.5 shadow-sm flex items-center gap-1 w-16 h-10">
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
          <div className="p-3 bg-white border-t border-gray-100 flex flex-col gap-2">
            
            {/* Attachment Chip */}
            {attachment && (
                <div className="flex items-center gap-2 bg-blue-50 text-blue-700 px-3 py-1.5 rounded-lg w-fit text-sm animate-in fade-in slide-in-from-bottom-2">
                    <Paperclip size={14} />
                    <span className="font-medium truncate max-w-[200px]">{attachment.name}</span>
                    <button 
                        onClick={() => setAttachment(null)}
                        className="hover:bg-blue-100 rounded-full p-0.5 ml-1 transition-colors"
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
                accept=".csv,.xlsx,.xls,.pdf" 
            />
            
            <button
                onClick={() => fileInputRef.current?.click()}
                disabled={!isConnected || isLoadingHistory || uploadingState}
                className="p-3 rounded-full bg-gray-100 text-gray-500 hover:bg-gray-200 transition-all flex-shrink-0 mb-0.5"
                title="Attach file"
            >
                {uploadingState ? <Loader2 size={18} className="animate-spin" /> : <Paperclip size={18} />}
            </button>

            <textarea
              className="flex-1 bg-gray-100 border-0 rounded-2xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-100 focus:bg-white outline-none transition-all disabled:opacity-50 resize-none max-h-32 min-h-[44px]"
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
              placeholder={
                isLoadingHistory
                  ? "Loading..."
                  : isConnected
                  ? "Ask or attach a file..."
                  : "Connecting..."
              }
            />
            <button
              onClick={sendMessage}
              disabled={!isConnected || !input.trim() || isLoadingHistory}
              className={`p-3 rounded-full transition-all duration-200 flex-shrink-0 mb-0.5 ${
                  !isConnected || !input.trim() || isLoadingHistory 
                  ? "bg-gray-100 text-gray-400 cursor-not-allowed" 
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
          </div>
          </div>
        </div>
      )}

      {/* Floating Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`group relative flex items-center justify-center w-14 h-14 rounded-full shadow-2xl transition-all duration-300 hover:scale-110 active:scale-95 ${
            isOpen ? "bg-gray-800 rotate-90" : "bg-gradient-to-br from-blue-600 to-blue-700 hover:shadow-blue-500/30"
        }`}
        title={isOpen ? "Close chat" : "Open chat"}
      >
        {isOpen ? (
            <X size={26} className="text-white transition-transform duration-300" />
        ) : (
            <MessageCircle size={26} className="text-white transition-transform duration-300 group-hover:-rotate-12" />
        )}
        
        {!isOpen && isConnected && (
            <span className="absolute top-0 right-0 flex h-3.5 w-3.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-green-500 border-2 border-white"></span>
            </span>
        )}
      </button>
    </div>
  );
}
