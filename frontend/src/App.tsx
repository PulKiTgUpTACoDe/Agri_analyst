import ChatBox from "../src/components/chatbox";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="max-w-3xl w-full bg-white shadow rounded-2xl p-6">
        <h1 className="text-3xl font-bold text-center mb-6 text-gray-800">
          Agri Data Q&A System
        </h1>
        <ChatBox />
      </div>
    </div>
  );
}
