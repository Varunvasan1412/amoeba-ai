import { useState, useEffect, useRef, useCallback } from "react";
import { MessageCircle, X, Send, Loader2, Trash2 } from "lucide-react";

type ChatMessage = {
  sender: "user" | "ai";
  text: string;
};

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true); // New loading state

  const socketRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const hasFetchedRef = useRef(false); // Prevent multiple fetches

  // Fetch history - separate from WebSocket connection
  const fetchHistory = useCallback(async () => {
    if (hasFetchedRef.current) return;

    setIsLoadingHistory(true);
    try {
      const res = await fetch("http://localhost:8000/history");
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
      // Still show chat even if history fails
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  // Setup WebSocket connection
  const setupWebSocket = useCallback(() => {
    console.log("🔌 Setting up WebSocket...");
    const ws = new WebSocket("ws://localhost:8000/ws/chat");

    ws.onopen = () => {
      console.log("🟢 WebSocket Connected");
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      console.log("📩 New AI Message:", event.data);
      setMessages((prev) => [...prev, { sender: "ai", text: event.data }]);
    };

    ws.onclose = () => {
      console.log("🔴 WebSocket Disconnected");
      setIsConnected(false);
      // Attempt to reconnect after 3 seconds
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

  // Initialize when component mounts or chat opens
  useEffect(() => {
    if (isOpen && !socketRef.current) {
      // Fetch history first, then setup WebSocket
      fetchHistory().then(() => {
        setupWebSocket();
      });
    }

    return () => {
      // Cleanup WebSocket when chat closes
      if (!isOpen && socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [isOpen, fetchHistory, setupWebSocket]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = () => {
    if (!input.trim() || !socketRef.current || !isConnected) return;

    const userMessage = { sender: "user" as const, text: input };
    setMessages((prev) => [...prev, userMessage]);
    socketRef.current.send(input);
    setInput("");
  };

  const clearMessages = () => {
    setMessages([]);
  };

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end font-sans">
      {isOpen && (
        <div className="w-80 h-96 bg-white shadow-2xl rounded-2xl border border-gray-200 flex flex-col mb-4 overflow-hidden">
          {/* HEADER */}
          <div className="bg-gray-900 p-4 text-white font-bold flex justify-between items-center shadow-md">
            <div className="flex items-center gap-2">
              <span>Amoeba AI</span>
              <div
                className={`w-2 h-2 rounded-full ${
                  isConnected ? "bg-green-400" : "bg-red-500 animate-pulse"
                }`}
              />
              {isLoadingHistory && (
                <span className="text-xs font-normal text-gray-300">
                  Loading history...
                </span>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={clearMessages}
                className="hover:text-red-400"
                title="Clear chat"
              >
                <Trash2 size={16} />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="hover:text-gray-300"
                title="Close chat"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* MESSAGES CONTAINER */}
          <div className="flex-1 p-4 overflow-y-auto bg-gray-50 flex flex-col gap-3">
            {isLoadingHistory ? (
              <div className="flex flex-col items-center justify-center h-full">
                <Loader2
                  className="animate-spin text-gray-400 mb-2"
                  size={24}
                />
                <p className="text-gray-400 text-sm">Loading chat history...</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 text-sm">
                <p>No chat history yet</p>
                <p className="text-xs mt-1">Start a conversation!</p>
              </div>
            ) : (
              <>
                {messages.map((msg, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-xl max-w-[85%] text-sm shadow-sm break-words ${
                      msg.sender === "user"
                        ? "bg-gray-900 text-white self-end rounded-br-none"
                        : "bg-white text-gray-800 border border-gray-200 self-start rounded-bl-none"
                    }`}
                  >
                    {msg.text}
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* INPUT AREA */}
          <div className="p-3 bg-white border-t border-gray-100 flex gap-2">
            <input
              className="flex-1 bg-gray-100 border-0 rounded-full px-4 py-2 text-sm focus:ring-2 focus:ring-gray-500 outline-none transition-all disabled:opacity-50"
              value={input}
              disabled={!isConnected || isLoadingHistory}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && sendMessage()}
              placeholder={
                isLoadingHistory
                  ? "Loading..."
                  : isConnected
                  ? "Type a message..."
                  : "Connecting..."
              }
            />
            <button
              onClick={sendMessage}
              disabled={!isConnected || !input.trim() || isLoadingHistory}
              className="bg-gray-900 text-white p-2 rounded-full disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoadingHistory ? (
                <Loader2 size={16} className="animate-spin" />
              ) : isConnected ? (
                <Send size={16} />
              ) : (
                <Loader2 size={16} className="animate-spin" />
              )}
            </button>
          </div>
        </div>
      )}

      {/* TOGGLE BUTTON */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="bg-gray-900 text-white p-4 rounded-full shadow-xl hover:scale-105 transition-transform"
        title={isOpen ? "Close chat" : "Open chat"}
      >
        {isOpen ? <X size={24} /> : <MessageCircle size={24} />}
      </button>
    </div>
  );
}
