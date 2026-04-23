"""Test weather-only queries (no data.gov.in dependency)."""
import asyncio
import httpx
import json

async def test():
    async with httpx.AsyncClient(timeout=120.0) as client:
        queries = [
            "What is the current weather in Punjab for farming?",
            "Show me the rainfall in Maharashtra for the last year",
        ]
        for q in queries:
            print(f"\n{'='*60}")
            print(f"QUERY: {q}")
            print(f"{'='*60}")
            r = await client.post("http://127.0.0.1:8000/ask", json={"question": q})
            data = r.json()
            print(f"Status: {r.status_code}")
            print(f"Sources: {data.get('usedEndpoints', [])}")
            print(f"Citations: {[c['name'] for c in data.get('citations', [])]}")
            print(f"Timing: {data.get('timing', {})}")
            if data.get('weather_location'):
                print(f"Location: {data['weather_location']}")
            print(f"\nAnswer:\n{data.get('answer', 'No answer')[:600]}")
            print()

asyncio.run(test())
