import { useState, useEffect, useRef, useCallback, memo } from "react";
import { MessageCircle, X, Send, Loader2, Trash2, Paperclip } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type ChatMessage = {
  sender: "user" | "ai";
  text: string;
  actions?: any[]; 
};

  //Memoized Message Bubble to prevent re-renders on typing
const MessageBubble = memo(({ msg, onSelect }: { msg: ChatMessage, onSelect?: (val: string) => void }) => {
  // Extract actions if present
  const choices = msg.actions?.find(a => a.type === "CHOICE");
  
  // Debug Log
  if (msg.sender === "ai" && msg.actions) {
      console.log("💬 Message Actions:", msg.actions);
      console.log("🔍 Choices Found:", choices);
  }

  return (
    <div className={`flex flex-col gap-2 max-w-[85%] ${msg.sender === "user" ? "self-end items-end" : "self-start items-start"}`}> 
        {/* Main Text Bubble */}
        <div
        className={`p-3.5 rounded-2xl text-sm shadow-sm break-words leading-relaxed ${
            msg.sender === "user"
            ? "bg-blue-600 text-white rounded-br-sm" 
            : "bg-white text-gray-800 border border-gray-100 rounded-bl-sm shadow-[0_2px_8px_-4px_rgba(0,0,0,0.1)]"
        }`}
        >
        {msg.sender === "user" ? (
            msg.text
        ) : choices ? (
            <div className="whitespace-pre-wrap text-gray-800 font-sans text-sm">
                {msg.text}
            </div>
        ) : (
            <div className="prose prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-li:my-0 prose-pre:bg-gray-50 prose-pre:text-gray-700 overflow-hidden">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
            </div>
        )}
        </div>

        {/* Action Buttons (e.g. Choices) */}
        {msg.sender === "ai" && choices && choices.payload && (
            <div className="flex flex-col gap-2 mt-1 ml-1 duration-300">
                {choices.payload.map((opt: any, idx: number) => (
                    <button
                        key={idx}
                        onClick={() => onSelect && onSelect(opt.label)} 
                        className="text-left text-xs bg-white border border-blue-200 hover:bg-blue-50 hover:border-blue-300 transition-colors p-3 rounded-xl shadow-sm flex items-center gap-2 group"
                    >
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-400 group-hover:bg-blue-600 transition-colors"></div>
                        <span className="font-medium text-gray-700 group-hover:text-blue-800">{opt.label}</span>
                    </button>
                ))}
            </div>
        )}
    </div>
  );
});

MessageBubble.displayName = "MessageBubble";

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isTyping, setIsTyping] = useState(false);

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
                  const res = await fetch(`${API_BASE}/routes/learn`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(event.data.routes)
                  });
                  if(res.ok) console.log("✅ Routes Saved to Brain!");
              } catch (err) {
                  console.error("❌ Failed to save routes:", err);
              }
          }
      };
      
      window.addEventListener("message", handleMessage);
      return () => window.removeEventListener("message", handleMessage);
  }, []);

  const socketRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const hasFetchedRef = useRef(false);

  const [attachment, setAttachment] = useState<{name: string, path: string} | null>(null);
  
  const API_BASE = import.meta.env.DEV ? "http://localhost:8000/api" : "/api";

  const fetchHistory = useCallback(async () => {
    if (hasFetchedRef.current) return;

    setIsLoadingHistory(true);
    try {
      const res = await fetch(`${API_BASE}/history`);
      if (!res.ok) throw new Error("Failed to fetch history");
      const data = await res.json();

      console.log(`✅ History Loaded: ${data.length} messages`);

      const history = data.map((msg: any) => ({
        sender: msg.sender,
        text: msg.content,
      }));

      setMessages(history);
      hasFetchedRef.current = true;
    } catch (err) {
      console.error("❌ History Error:", err);
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  const setupWebSocket = useCallback(() => {
    console.log("🔌 Setting up WebSocket...");

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host; 
    const urlParams = new URLSearchParams(window.location.search);
    const apiKey = urlParams.get("api_key") || import.meta.env.VITE_API_KEY || "";
    console.log("API KEY:", apiKey);

    
    const wsUrl = `${protocol}//${host}/api/ws/chat?api_key=${apiKey}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("🟢 WebSocket Connected");
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      console.log("📩 New AI Message:", event.data);
      setIsTyping(false); 
      
      try {
        const payload = JSON.parse(event.data);
        
        // 1. Text Response
        if (payload.text) {
             setMessages((prev) => [...prev, { sender: "ai", text: payload.text }]);
        }
        
        // 2. Action Handling
        if (payload.actions && Array.isArray(payload.actions)) {
            payload.actions.forEach((action: any) => {
                console.log("📢 Dispatching Action to Parent:", action);
                window.parent.postMessage({
                    type: "AMOEBA_ACTION",
                    action: action.type,
                    payload: action.payload
                }, "*"); 
            });
        }
      } catch (e) {
        setMessages((prev) => [...prev, { sender: "ai", text: event.data }]);
      }
    };

    ws.onclose = () => {
      console.log("🔴 WebSocket Disconnected");
      setIsConnected(false);
      setTimeout(() => {
        if (isOpen) {
          setupWebSocket();
        }
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error("❌ WebSocket Error:", error);
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

    const userMessage = { sender: "user" as const, text: displayInput };
    setMessages((prev) => [...prev, userMessage]);
    
    socketRef.current.send(textToSend);
    
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
        setMessages((prev) => [...prev, { sender: "ai", text: "❌ Error uploading file." }]);
    } finally {
        setUploadingState(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

    /* Helper to handle choice selection */
    const handleChoiceSelect = useCallback((label: string) => {
        // Send the label as a user message
        const userMessage = { sender: "user" as const, text: label };
        setMessages((prev) => [...prev, userMessage]);
        
        if (socketRef.current && isConnected) {
             socketRef.current.send(label);
             setIsTyping(true);
        }
    }, [isConnected]);

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end font-sans">
      {isOpen && (
        <div className="w-96 h-[500px] bg-white shadow-2xl rounded-2xl border border-gray-200 flex flex-col mb-4 overflow-hidden transition-all duration-300 ease-in-out">
          {/* Header */}
          <div className="bg-gradient-to-r from-gray-900 to-gray-800 p-4 text-white font-bold flex justify-between items-center shadow-md">
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
                  </div>
              </div>
            </div>
            <div className="flex gap-1">
              <button
                onClick={clearMessages}
                className="hover:bg-white/10 p-1.5 rounded-full transition-colors text-gray-300 hover:text-white"
                title="Clear chat"
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
              </div>
            ) : (
              <>
                {messages.map((msg, i) => (
                  <MessageBubble key={i} msg={msg} onSelect={handleChoiceSelect} />
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
