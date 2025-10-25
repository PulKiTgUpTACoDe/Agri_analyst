# Agri Analyst - Backend

Intelligent Q&A system over data.gov.in agricultural and climate data using LangChain and LangGraph.

## Setup Instructions

### 1. Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Data.gov.in API Key
- Google Gemini API Key

### 2. Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
copy .env.example .env
```

Required environment variables:
- `GOOGLE_API_KEY` - Your Gemini API key from Google AI Studio
- **Multiple data.gov.in API keys** (at minimum, configure these two):
  - `AGRI_CROP_PRODUCTION_API_KEY` - Agriculture Ministry crop production data
  - `IMD_RAINFALL_API_KEY` - India Meteorological Department rainfall data
- `POSTGRES_PASSWORD` - PostgreSQL password

**Note:** The system uses **multiple API keys** for different government departments. Each dataset on data.gov.in requires its own API key. Configure as many as you have access to for full functionality.

### 4. Database Setup

Ensure PostgreSQL is running and create the database:

```sql
CREATE DATABASE agri_analyst;
```

The application will automatically create tables on startup.

### 5. Run the Application

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000/docs for interactive API documentation.

## Project Structure

```
backend/
├── app/
│   ├── api/              # API routes
│   ├── core/             # Core configuration (LLM, embeddings, config)
│   ├── db/               # Database (PostgreSQL, ChromaDB)
│   ├── graph/            # LangGraph reasoning workflow
│   ├── chains/           # LangChain query chains
│   ├── models/           # Pydantic models
│   ├── utils/            # Utility functions (data.gov.in clients)
│   ├── rag/              # RAG components
│   └── main.py           # FastAPI application
├── data/                 # Data storage (ChromaDB, cache)
├── tests/                # Test suite
├── requirements.txt      # Dependencies
└── .env                  # Environment variables (not in git)
```

## Architecture

### Tech Stack
- **Framework**: FastAPI
- **LLM**: Google Gemini (via LangChain)
- **Orchestration**: LangGraph
- **Vector Store**: ChromaDB
- **Database**: PostgreSQL
- **Embeddings**: Sentence-Transformers

### Data Flow
1. User asks question via API
2. LangGraph reasoning workflow:
   - **Intent Analysis** → Determine what user wants (crop data? weather data? both?)
   - **Source Selection** → Choose relevant datasets (Agriculture API + IMD API)
   - **Query Generation** → Generate parallel API calls for multiple sources
   - **Query Execution** → Fetch from data.gov.in **in parallel** using appropriate API keys
   - **Synthesis** → Combine results with LLM to correlate crop and weather data
3. Response with citations returned

### Multi-Source Architecture
The system queries **multiple government APIs simultaneously**:
- **Agriculture Ministry APIs** (crop production, horticulture, livestock)
- **IMD APIs** (rainfall, temperature, climate patterns)
- **Other Ministry APIs** (land resources, water resources)

Each source has its own API key. The system executes queries in parallel and correlates data across domains to answer complex questions like "How did rainfall patterns affect rice production in Punjab?"

See [docs/MULTI_SOURCE_API.md](docs/MULTI_SOURCE_API.md) for detailed architecture.

## API Endpoints

- `GET /health` - Health check
- `POST /api/v1/ask` - Submit question (coming in Phase 8)
- `GET /api/v1/datasets` - List available datasets (coming in Phase 8)

## Development Status

✅ Phase 1: Core Configuration & Dependencies - COMPLETE
⏳ Phase 2-10: In progress

## License

See LICENSE file in root directory.
