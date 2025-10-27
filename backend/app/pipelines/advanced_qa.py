"""Advanced QA pipeline with aggregation, correlation, and policy synthesis capabilities."""
import json
import os
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

from app.utils.aggregation import (
    aggregate_multi_year_average,
    top_n_ranking,
    aggregate_by_group,
    calculate_year_over_year_growth,
    calculate_trend
)
from app.utils.correlation import (
    correlate_production_with_climate,
    identify_optimal_conditions,
    compare_climate_impact
)
from app.utils.policy_synthesis import (
    generate_policy_arguments,
    synthesize_multi_source_answer,
    generate_comparative_summary
)


def detect_query_type(question: str) -> str:
    """Detect the type of analysis needed based on question keywords.
    
    Returns: 'comparison', 'trend', 'correlation', 'policy', 'ranking', or 'general'
    """
    question_lower = question.lower()
    
    if any(word in question_lower for word in ['compare', 'vs', 'versus', 'difference between']):
        return 'comparison'
    elif any(word in question_lower for word in ['trend', 'over time', 'last decade', 'growth', 'change']):
        return 'trend'
    elif any(word in question_lower for word in ['correlate', 'relationship', 'impact', 'affect', 'influence']):
        return 'correlation'
    elif any(word in question_lower for word in ['policy', 'promote', 'recommend', 'should', 'argument']):
        return 'policy'
    elif any(word in question_lower for word in ['top', 'highest', 'lowest', 'best', 'worst', 'rank']):
        return 'ranking'
    else:
        return 'general'


def perform_advanced_analysis(
    question: str,
    payload: Dict[str, List[Dict[str, Any]]],
    query_type: str
) -> Dict[str, Any]:
    """Perform advanced analysis based on query type and available data.
    
    Args:
        question: User's question
        payload: Dict of fetched records from all endpoints
        query_type: Type of query detected
    
    Returns:
        Dict with analysis results and formatted insights
    """
    analysis_results = {
        'query_type': query_type,
        'insights': [],
        'structured_data': {}
    }
    
    production_data = payload.get('crop_production', [])
    rainfall_data = payload.get('district_rainfall', []) or payload.get('rainfall_subdivisions', [])
    price_data = payload.get('daily_prices', []) or payload.get('variety_prices', [])
    
    # Comparison Analysis
    if query_type == 'comparison' and production_data:
        # Try to identify two entities being compared
        states = list(set(r.get('State_Name', r.get('state', '')) for r in production_data if r.get('State_Name') or r.get('state')))
        
        if len(states) >= 2:
            state_a, state_b = states[0], states[1]
            data_a = [r for r in production_data if r.get('State_Name', r.get('state')) == state_a]
            data_b = [r for r in production_data if r.get('State_Name', r.get('state')) == state_b]
            
            comparison = generate_comparative_summary(
                state_a, state_b, data_a, data_b,
                metric_field='Production',
                entity_type='state'
            )
            
            analysis_results['insights'].append({
                'type': 'state_comparison',
                'title': f'Production Comparison: {state_a} vs {state_b}',
                'data': comparison
            })
            analysis_results['structured_data']['comparison'] = comparison
    
    # Trend Analysis
    if query_type == 'trend' and production_data:
        if 'Crop_Year' in production_data[0]:
            trend = calculate_trend(production_data, 'Crop_Year', 'Production')
            
            if 'direction' in trend:
                analysis_results['insights'].append({
                    'type': 'production_trend',
                    'title': 'Production Trend Analysis',
                    'data': trend,
                    'summary': f'Production trend is {trend["direction"]} with {trend["percent_change"]}% change over {trend["data_points"]} years'
                })
                analysis_results['structured_data']['trend'] = trend
                
                # Add year-over-year growth
                yoy_growth = calculate_year_over_year_growth(
                    production_data, 'Crop_Year', 'Production'
                )
                if yoy_growth:
                    analysis_results['structured_data']['year_over_year'] = yoy_growth
    
    # Correlation Analysis
    if query_type == 'correlation' and production_data and rainfall_data:
        correlation = correlate_production_with_climate(
            production_data,
            rainfall_data,
            production_field='Production',
            climate_field='Rainfall',
            year_field='Year' if 'Year' in production_data[0] else 'Crop_Year'
        )
        
        if 'coefficient' in correlation:
            analysis_results['insights'].append({
                'type': 'climate_correlation',
                'title': 'Production-Climate Correlation',
                'data': correlation,
                'summary': f'{correlation["strength"].capitalize()} {correlation["direction"]} correlation (r={correlation["coefficient"]})'
            })
            analysis_results['structured_data']['correlation'] = correlation
            
            # Identify optimal conditions
            if len(production_data) >= 10:
                optimal = identify_optimal_conditions(
                    production_data,
                    'Production',
                    'Rainfall' if 'Rainfall' in production_data[0] else 'rainfall',
                    top_n=10
                )
                if 'optimal_climate_range' in optimal:
                    analysis_results['structured_data']['optimal_conditions'] = optimal
    
    # Policy Analysis
    if query_type == 'policy':
        # This requires specific crop data - check if we have two crops to compare
        crops = list(set(r.get('Crop', r.get('crop', '')) for r in production_data if r.get('Crop') or r.get('crop')))
        
        if len(crops) >= 2 and rainfall_data:
            crop_a, crop_b = crops[0], crops[1]
            crop_a_data = [r for r in production_data if r.get('Crop', r.get('crop')) == crop_a]
            crop_b_data = [r for r in production_data if r.get('Crop', r.get('crop')) == crop_b]
            
            region = production_data[0].get('State_Name', 'the region')
            
            policy_args = generate_policy_arguments(
                crop_a, crop_b, region,
                {'crop_a': crop_a_data, 'crop_b': crop_b_data},
                {'rainfall': rainfall_data}
            )
            
            analysis_results['insights'].append({
                'type': 'policy_recommendation',
                'title': f'Policy Arguments: {crop_a} vs {crop_b}',
                'data': policy_args
            })
            analysis_results['structured_data']['policy'] = policy_args
    
    # Ranking Analysis
    if query_type == 'ranking' and production_data:
        # Determine what to rank
        if 'Production' in production_data[0]:
            top_producers = top_n_ranking(
                production_data,
                'Production',
                n=10,
                ascending=False
            )
            
            analysis_results['insights'].append({
                'type': 'production_ranking',
                'title': 'Top Producers',
                'data': top_producers,
                'summary': f'Top producer: {top_producers[0].get("District_Name", top_producers[0].get("State_Name", "Unknown"))} with {top_producers[0]["Production"]} tonnes'
            })
            analysis_results['structured_data']['rankings'] = top_producers
    
    # Multi-year averages (for any query with multiple years)
    if production_data and len(production_data) > 1:
        if 'Crop_Year' in production_data[0]:
            # Calculate averages by state
            if 'State_Name' in production_data[0]:
                multi_year_avg = aggregate_multi_year_average(
                    production_data,
                    'Production',
                    ['State_Name']
                )
                analysis_results['structured_data']['multi_year_averages'] = multi_year_avg
    
    return analysis_results


async def run_advanced_pipeline(question: str, payload: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Run advanced analysis pipeline with aggregation, correlation, and synthesis.
    
    Args:
        question: User's question
        payload: Fetched data from all endpoints
    
    Returns:
        Dict with answer, analysis, and metadata
    """
    # Detect query type
    query_type = detect_query_type(question)
    print(f"[ADVANCED_QA] Detected query type: {query_type}")
    
    # Perform advanced analysis
    analysis = perform_advanced_analysis(question, payload, query_type)
    
    # Format context with analysis results
    context_parts = []
    
    # Add raw data preview
    for source, records in payload.items():
        if records:
            context_parts.append(f"\n## {source.replace('_', ' ').title()} Data ({len(records)} records)")
            context_parts.append(json.dumps(records[:3], ensure_ascii=False, indent=2))
    
    # Add analysis insights
    if analysis['insights']:
        context_parts.append("\n## Advanced Analysis")
        for insight in analysis['insights']:
            context_parts.append(f"\n### {insight['title']}")
            context_parts.append(json.dumps(insight['data'], ensure_ascii=False, indent=2))
    
    context = "\n".join(context_parts)
    
    # Enhanced system prompt for advanced queries
    system_prompt = f"""You are an expert Agriculture Data Analyst with advanced analytical capabilities.

Query Type: {query_type}

Available Analysis:
- Multi-year aggregation and averages
- Trend analysis with growth rates
- Correlation between production and climate
- Comparative analysis between states/districts/crops
- Top-N rankings and performance metrics
- Policy recommendations with data-backed arguments

Instructions:
1. Use the provided data and analysis results to answer comprehensively
2. For comparisons: Present side-by-side data with clear differences
3. For trends: Mention direction, growth rate, and time period
4. For correlations: Explain strength, direction, and implications
5. For policy questions: Present top 3 data-backed arguments
6. For rankings: List top items with specific numbers
7. Always cite specific numbers, years, states, and data sources
8. If analysis is insufficient, clearly state what additional data would help

Be precise, data-driven, and actionable in your response."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Question: {question}\n\nData and Analysis:\n{context}")
    ])
    
    model = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.3")),
        max_output_tokens=int(os.getenv("GEMINI_MAX_TOKENS", "2048")),
    )
    
    chain = {"question": lambda x: x, "context": lambda x: context} | prompt | model | StrOutputParser()
    answer = await chain.ainvoke(question)
    
    return {
        'answer': answer,
        'query_type': query_type,
        'analysis': analysis,
        'context_preview': context[:1000] + "..." if len(context) > 1000 else context,
        'data_sources_used': [k for k, v in payload.items() if v],
        'total_records_analyzed': sum(len(v) for v in payload.values())
    }
