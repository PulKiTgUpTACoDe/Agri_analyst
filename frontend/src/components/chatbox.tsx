import { useState } from "react";

export default function ChatBox() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [context, setContext] = useState<string | null>(null);
  const [endpoints, setEndpoints] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const API_BASE = import.meta.env.VITE_API_BASE

  const askBackend = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setAnswer("");
    setContext(null);
    setEndpoints(null);
    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!res.ok) {
        throw new Error(`Backend error ${res.status}`);
      }
      const data = await res.json();
      setAnswer(data.answer ?? "");
      setContext(data.context ?? null);
      setEndpoints(data.usedEndpoints ?? null);
    } catch (err: any) {
      setError(err?.message || "Error connecting to backend.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about rainfall, crops..."
          className="grow border border-gray-300 rounded px-4 py-2 focus:ring focus:ring-blue-200 outline-none"
          onKeyDown={(e) => { if (e.key === 'Enter') askBackend(); }}
        />
        <button
          onClick={askBackend}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 transition disabled:opacity-50"
          disabled={loading}
        >
          {loading ? "Thinking..." : "Ask"}
        </button>
      </div>

      {error && (
        <div className="mt-4 p-3 border rounded bg-red-50 text-red-700">
          {error}
        </div>
      )}

      {answer && (
        <div className="mt-4 p-4 border rounded bg-gray-50">
          <div className="font-semibold mb-1">Answer</div>
          <div>{answer}</div>
          {(context || endpoints) && (
            <div className="mt-3">
              <button
                onClick={() => setShowDetails((s) => !s)}
                className="text-sm text-blue-600 hover:underline"
              >
                {showDetails ? "Hide details" : "Show details"}
              </button>
              {showDetails && (
                <div className="mt-2 text-sm text-gray-700 space-y-2">
                  {endpoints && (
                    <div>
                      <div className="font-medium">Used endpoints</div>
                      <pre className="whitespace-pre-wrap break-words">{JSON.stringify(endpoints, null, 2)}</pre>
                    </div>
                  )}
                  {context && (
                    <div>
                      <div className="font-medium">Context (preview)</div>
                      <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words">{context}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
