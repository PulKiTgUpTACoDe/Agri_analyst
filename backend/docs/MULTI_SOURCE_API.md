# Multi-Source API Architecture

## Overview

The Agri Analyst system is designed to query **multiple data.gov.in APIs simultaneously** with different API keys for different government departments. This enables cross-domain analysis between agricultural and meteorological data.

## Architecture Design

### 1. Multiple API Keys

Each government department/dataset requires its own API key:

```
Agriculture Ministry:
├── Crop Production API Key
├── Horticulture API Key
└── Livestock API Key

India Meteorological Department (IMD):
├── Rainfall API Key
├── Temperature API Key
└── Climate Patterns API Key

Other Departments:
├── Land Resources API Key
└── Water Resources API Key
```

### 2. Data Source Registry

The `DataSourceRegistry` manages all available data sources:

```python
from app.core.data_sources import get_data_source_registry, DataSourceType

registry = get_data_source_registry()

# Get specific source
crop_source = registry.get_source(DataSourceType.CROP_PRODUCTION)

# Get all agriculture sources
agri_sources = registry.get_agriculture_sources()

# Get all meteorology sources
meteo_sources = registry.get_meteorology_sources()

# Get cross-domain sources for correlation
cross_domain = registry.get_cross_domain_sources()
```

### 3. Parallel Query Execution

The `DataGovAPIClient` can query multiple sources in parallel:

```python
from app.utils import get_api_client
from app.core import DataSourceType

client = get_api_client(db_session)

# Query multiple sources simultaneously
queries = [
    {
        "source_type": DataSourceType.CROP_PRODUCTION,
        "filters": {"state_name": "Punjab", "crop_year": 2020}
    },
    {
        "source_type": DataSourceType.RAINFALL,
        "filters": {"state_name": "Punjab", "year": 2020}
    }
]

results = await client.query_multiple_sources(queries)
```

### 4. Cross-Domain Correlation

Built-in method for crop-weather correlation:

```python
# Query both crop and weather data for correlation analysis
result = await client.query_crop_weather_correlation(
    state="Punjab",
    year=2020,
    crop="Rice",
    district="Ludhiana"
)

# Returns:
# {
#     "state": "Punjab",
#     "year": 2020,
#     "crop": "Rice",
#     "district": "Ludhiana",
#     "results": [
#         {
#             "source": "Crop Production Statistics",
#             "data": [...],  # Crop production data
#         },
#         {
#             "source": "Rainfall Data",
#             "data": [...],  # Rainfall data
#         }
#     ]
# }
```

## LangGraph Integration

The LangGraph reasoning workflow will:

1. **Intent Analysis** - Determine which data sources are needed
2. **Source Selection** - Select relevant agriculture and meteorology APIs
3. **Query Generation** - Generate parallel queries for each source
4. **Execution** - Execute all queries simultaneously
5. **Synthesis** - Use LLM to correlate and synthesize results

### Example Flow:

**User Question:**
> "Compare rainfall in Punjab and Haryana in 2020, and show which state had better rice production"

**LangGraph Steps:**
1. **Intent**: Compare rainfall + crop production across states
2. **Sources Selected**:
   - CROP_PRODUCTION (for rice data)
   - RAINFALL (for rainfall data)
3. **Queries Generated**:
   ```python
   [
       {"source": CROP_PRODUCTION, "filters": {"state": "Punjab", "year": 2020, "crop": "Rice"}},
       {"source": CROP_PRODUCTION, "filters": {"state": "Haryana", "year": 2020, "crop": "Rice"}},
       {"source": RAINFALL, "filters": {"state": "Punjab", "year": 2020}},
       {"source": RAINFALL, "filters": {"state": "Haryana", "year": 2020}}
   ]
   ```
4. **Execute**: All 4 queries run in parallel
5. **Synthesize**: LLM correlates rainfall and production data

## Caching Strategy

API responses are cached to reduce load:

- **Cache TTL**: 1 hour (configurable)
- **Cache Key**: MD5 hash of (endpoint + parameters)
- **Storage**: PostgreSQL `api_cache` table
- **Benefits**:
  - Faster responses for repeated queries
  - Reduced API quota usage
  - Cost savings

## Configuration

### Environment Variables (`.env`):

```bash
# Agriculture Ministry
AGRI_CROP_PRODUCTION_API_KEY=your_key_here
AGRI_HORTICULTURE_API_KEY=your_key_here
AGRI_LIVESTOCK_API_KEY=your_key_here

# IMD
IMD_RAINFALL_API_KEY=your_key_here
IMD_TEMPERATURE_API_KEY=your_key_here
IMD_CLIMATE_API_KEY=your_key_here
```

### Resource IDs

Update resource IDs in `app/core/data_sources.py` after exploring data.gov.in:

```python
resource_id="9ef84268-d588-465a-a308-a864a43d0070"  # Example
```

To find resource IDs:
1. Go to https://data.gov.in/
2. Search for dataset (e.g., "crop production")
3. Click "API" button
4. Copy the resource ID from the API endpoint

## Example Sample Questions

### Question 1: Cross-State Rainfall Comparison
```
"Compare the average annual rainfall in Punjab and Haryana for the last 5 years. 
List the top 3 crops by production volume in each state during the same period."
```

**Data Sources Used:**
- IMD Rainfall API (2 queries: Punjab, Haryana)
- Agriculture Crop Production API (2 queries: Punjab, Haryana)

### Question 2: District-Level Analysis
```
"Identify the district in Punjab with the highest wheat production in 2020 
and compare it with the lowest wheat-producing district in Haryana."
```

**Data Sources Used:**
- Agriculture Crop Production API (2 queries with district-level filters)

### Question 3: Climate-Crop Correlation
```
"Analyze rice production trends in Uttar Pradesh over the last decade. 
Correlate this with rainfall patterns and temperature data."
```

**Data Sources Used:**
- Agriculture Crop Production API (10-year time series)
- IMD Rainfall API (10-year time series)
- IMD Temperature API (10-year time series)

### Question 4: Policy Analysis
```
"A policy advisor wants to promote drought-resistant crops over water-intensive 
crops in Maharashtra. Provide 3 data-backed arguments using the last 10 years 
of rainfall and crop production data."
```

**Data Sources Used:**
- Agriculture Crop Production API (multiple crops, 10 years)
- IMD Rainfall API (10-year deficit analysis)
- IMD Climate Patterns API (drought frequency)

## Benefits of Multi-Source Architecture

1. **Real-time Data**: Always queries live data from government sources
2. **Data Sovereignty**: No unauthorized data duplication
3. **Cross-Domain Insights**: Correlates agriculture and climate seamlessly
4. **Scalability**: Easy to add new data sources
5. **Traceability**: Every answer cites exact data sources
6. **Flexibility**: LLM adapts to different data structures

## Next Steps (Phase 6)

The LangGraph workflow will intelligently:
- Determine which APIs to call based on the question
- Generate optimal query parameters
- Execute queries in parallel
- Handle missing data gracefully
- Synthesize results with proper citations

This architecture ensures the system can answer complex, multi-domain questions that require correlating data from different government departments.
