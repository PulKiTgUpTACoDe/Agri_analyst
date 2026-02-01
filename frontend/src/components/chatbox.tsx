import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion, AnimatePresence } from "framer-motion";

interface Citation {
  id: string;
  name: string;
  icon: string;
  records: number;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  metadata?: {
    sources?: string[];
    query_type?: string;
    total_records?: number;
  };
  timestamp?: string;
}

export default function ChatBox() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const API_BASE = import.meta.env.VITE_API_BASE;
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  // Debug: Log the API_BASE being used
  useEffect(() => {
    console.log("API_BASE:", API_BASE);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const askBackend = async () => {
    if (!question.trim()) return;

    const timestamp = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

    const userMessage: Message = { role: "user", content: question, timestamp };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setLoading(true);
    setError(null);

    try {
      const controller = new AbortController();
      // const timeoutId = setTimeout(() => controller.abort(), 60000);

      const res = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
        signal: controller.signal,
      });

      // clearTimeout(timeoutId);

      if (!res.ok) {
        throw new Error(`Error ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();

      const assistantMessage: Message = {
        role: "assistant",
        content: data.answer ?? "No response",
        citations: data.citations || [],
        metadata: {
          sources: data.metadata?.sources || data.usedEndpoints,
          query_type: data.query_type,
          total_records: data.total_records || data.metadata?.records_fetched,
        },
        timestamp,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      if (err.name === "AbortError") {
        setError(
          "Request timed out. The query is taking too long. Please try a simpler question or check your connection.",
        );
      } else {
        setError(
          err?.message ||
            "Error connecting to backend. Please make sure the backend server is running.",
        );
      }
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] bg-gradient-to-br from-emerald-50 via-white to-green-50 rounded-3xl shadow-xl backdrop-blur-lg p-4 border border-emerald-100">
      {/* Welcome Section */}
      {messages.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
          <div className="bg-gradient-to-br from-emerald-500 to-green-600 p-6 rounded-3xl text-white mb-6 shadow-lg">
            <svg
              className="w-12 h-12 mx-auto"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
          </div>
          <h2 className="text-3xl font-bold text-gray-800 mb-2">
            Ask Anything About Indian Agriculture
          </h2>
          <p className="text-gray-600 mb-8">
            Get insights from 5+ datasets on crops, markets, and weather trends
            🌾
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-xl">
            {[
              { q: "What is rice production in Punjab?", icon: "🌾" },
              { q: "Compare wheat prices in Punjab vs Haryana", icon: "📊" },
              { q: "Show rainfall trends in Maharashtra", icon: "🌧️" },
              { q: "Top 10 cotton producing districts", icon: "🏆" },
            ].map((item, i) => (
              <button
                key={i}
                onClick={() => setQuestion(item.q)}
                className="p-4 bg-white border border-gray-200 rounded-xl hover:border-emerald-400 hover:shadow-lg transition-all text-left flex items-center gap-3"
              >
                <span className="text-2xl">{item.icon}</span>
                <span className="text-gray-700 font-medium">{item.q}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Chat Messages */}
      {messages.length > 0 && (
        <div className="flex-1 overflow-y-auto px-2 space-y-4 scrollbar-thin scrollbar-thumb-emerald-200 scrollbar-track-transparent">
          <AnimatePresence>
            {messages.map((msg, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-3xl p-5 rounded-2xl shadow-sm ${
                    msg.role === "user"
                      ? "bg-gradient-to-r from-emerald-500 to-green-600 text-white rounded-tr-sm"
                      : "bg-white border border-gray-100 text-gray-800 rounded-tl-sm"
                  }`}
                >
                  <div className="w-full">
                    <div className="prose prose-sm max-w-none prose-headings:text-gray-800 prose-p:text-gray-700 prose-strong:text-gray-900 prose-ul:text-gray-700 prose-li:text-gray-700 prose-table:text-sm prose-th:bg-emerald-50 prose-th:text-emerald-900 prose-th:font-semibold prose-th:p-2 prose-td:p-2 prose-td:border prose-td:border-gray-200 prose-table:border-collapse prose-table:w-full prose-table:my-4">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                    <div className="flex justify-end mt-2">
                      <span className="text-xs text-gray-400">
                        {msg.timestamp}
                      </span>
                    </div>
                  </div>

                  {/* Citations */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-100">
                      <div className="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1">
                        <svg
                          className="w-3.5 h-3.5"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                          />
                        </svg>
                        Data Sources Used:
                      </div>
                      <div className="space-y-2">
                        {msg.citations.map((citation, i) => (
                          <div
                            key={i}
                            className="flex items-center gap-2 text-xs bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-100 rounded-lg px-3 py-2"
                          >
                            <span className="text-lg">{citation.icon}</span>
                            <div className="flex-1">
                              <div className="font-medium text-gray-800">
                                {citation.name}
                              </div>
                              <div className="text-gray-500">
                                {citation.records} records analyzed
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Metadata badges */}
                  {msg.metadata && (
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                      {msg.metadata.query_type && (
                        <span className="px-2 py-1 bg-emerald-50 text-emerald-700 rounded-full font-medium">
                          {msg.metadata.query_type}
                        </span>
                      )}
                      {msg.metadata.total_records && (
                        <span className="px-2 py-1 bg-purple-50 text-purple-700 rounded-full font-medium">
                          {msg.metadata.total_records} total records
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {loading && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-2xl p-4 flex items-center gap-3 text-gray-500 shadow-sm">
                <div className="flex gap-1">
                  <div
                    className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  ></div>
                  <div
                    className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  ></div>
                  <div
                    className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  ></div>
                </div>
                <span className="text-sm italic">Analyzing data...</span>
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>
      )}

      {/* Error Box */}
      {error && (
        <div className="mb-3 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-start gap-3">
          <svg
            className="w-5 h-5 mt-0.5 flex-shrink-0"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clipRule="evenodd"
            />
          </svg>
          <div>
            <p className="font-medium">Error</p>
            <p className="text-sm">{error}</p>
          </div>
        </div>
      )}

      {/* Input Box */}
      <div className="bg-white border border-gray-200 rounded-2xl shadow-lg p-3 mt-3 flex items-end gap-3">
        <textarea
          value={question}
          onChange={(e) => {
            setQuestion(e.target.value);
            // Auto-resize textarea
            e.target.style.height = "auto";
            e.target.style.height = Math.min(e.target.scrollHeight, 200) + "px";
          }}
          placeholder="Ask about crops, prices, weather, production..."
          rows={1}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (!loading) {
                askBackend();
                // Reset height after sending
                e.currentTarget.style.height = "auto";
              }
            }
          }}
          disabled={loading}
          className="flex-1 resize-none px-4 py-3 border border-gray-100 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-gray-800 placeholder-gray-400 max-h-[200px] overflow-y-auto"
          style={{ minHeight: "48px" }}
        />
        <button
          onClick={askBackend}
          disabled={loading || !question.trim()}
          className="p-3 bg-gradient-to-r from-emerald-500 to-green-600 text-white rounded-xl hover:from-emerald-600 hover:to-green-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-md"
        >
          {loading ? (
            <svg
              className="w-5 h-5 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
          ) : (
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
