import ChatBox from "./components/chatbox";

export default function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 via-white to-green-50">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-emerald-500 to-green-600 rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-emerald-600 to-green-600 bg-clip-text text-transparent">
                Agri Analyst
              </h1>
              <p className="text-xs text-gray-500">AI-Powered Agricultural Intelligence</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span className="px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full font-medium">5 Data Sources</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        <ChatBox />
      </main>

      {/* Footer */}
      <footer className="border-t bg-white/50 backdrop-blur-sm mt-12">
        <div className="max-w-6xl mx-auto px-6 py-6 text-center text-sm text-gray-600">
          <p>Powered by Google Gemini AI • Data from data.gov.in</p>
        </div>
      </footer>
    </div>
  );
}
