# 🌱 Agri Analyst

Agri Analyst is an intelligent agricultural analytics platform that provides farmers, traders, and agricultural businesses with data-driven insights on market prices, crop production, and weather patterns. The application features a natural language interface that allows users to ask questions in plain English and receive meaningful analysis.

## ✨ Features

- **Natural Language Querying**: Ask questions about agricultural data in plain English
- **Comprehensive Data Analysis**: Get insights on market prices, crop production, and weather data
- **Source Citations**: Transparent data sources with proper attribution
- **Real-time Data**: Access up-to-date agricultural information
- **Responsive Design**: Works on desktop and mobile devices

## 🚀 Tech Stack

### Backend
- **Framework**: FastAPI (Python)
- **AI/ML**: LangGraph for workflow management
- **Data Processing**: Pandas, NumPy
- **API**: RESTful endpoints with JSON responses
- **CORS**: Secure cross-origin resource sharing

### Frontend
- **Framework**: React with TypeScript
- **UI Components**: Custom components with Framer Motion animations
- **Markdown Support**: For rich text rendering
- **State Management**: React Hooks

## 📦 Installation

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Backend Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/agri-analyst.git
   cd agri-analyst/backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the backend directory with the required configurations.

5. Run the backend server:
   ```bash
   uvicorn app.main:app --reload
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd ../frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   # or
   yarn install
   ```

3. Start the development server:
   ```bash
   npm run dev
   # or
   yarn dev
   ```

4. Open your browser and visit `http://localhost:5173`

## 🌐 API Endpoints

- `POST /ask`: Process agricultural queries
  - Request body: `{ "question": "What are the current wheat prices?" }`
  - Response includes: Answer, sources, and data citations

## 📊 Data Sources

- Market prices
- Crop production statistics
- Weather data (temperature and rainfall)
- Variety-wise pricing

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with ❤️ for the agricultural community
- Special thanks to all contributors and open-source projects that made this possible

## 📬 Contact

For any queries or support, please open an issue on GitHub or contact the maintainers.
