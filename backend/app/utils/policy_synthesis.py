"""Policy synthesis utilities for generating data-backed arguments and recommendations."""
from typing import List, Dict, Any, Optional
from .aggregation import aggregate_by_group, calculate_trend, top_n_ranking
from .correlation import correlate_production_with_climate, identify_optimal_conditions


def generate_policy_arguments(
    crop_a_name: str,
    crop_b_name: str,
    region: str,
    production_data: Dict[str, List[Dict[str, Any]]],
    climate_data: Dict[str, List[Dict[str, Any]]],
    n_years: int = 5
) -> Dict[str, Any]:
    """Generate data-backed policy arguments for crop promotion.
    
    Args:
        crop_a_name: Crop to promote (e.g., "Drought-resistant Millet")
        crop_b_name: Crop to reduce (e.g., "Water-intensive Rice")
        region: Geographic region name
        production_data: Dict with 'crop_a' and 'crop_b' production records
        climate_data: Dict with 'rainfall' or 'temperature' records
        n_years: Number of recent years to analyze
    
    Returns:
        Dict with top 3 arguments and supporting data
    
    Example:
        result = generate_policy_arguments(
            "Millet", "Rice", "Maharashtra",
            {'crop_a': [...], 'crop_b': [...]},
            {'rainfall': [...]}
        )
    """
    arguments = []
    
    crop_a_records = production_data.get('crop_a', [])
    crop_b_records = production_data.get('crop_b', [])
    rainfall_records = climate_data.get('rainfall', [])
    
    # Argument 1: Climate Resilience
    if crop_a_records and rainfall_records:
        corr_a = correlate_production_with_climate(
            crop_a_records,
            rainfall_records,
            production_field="Production",
            climate_field="Rainfall"
        )
        
        if 'coefficient' in corr_a:
            coef_a = abs(corr_a['coefficient'])
            
            # Lower correlation with rainfall = more drought-resistant
            if coef_a < 0.5:
                arguments.append({
                    'rank': 1,
                    'title': f'{crop_a_name} Shows Greater Climate Resilience',
                    'argument': f'{crop_a_name} production shows {corr_a["strength"]} correlation (r={corr_a["coefficient"]}) with rainfall, indicating better drought tolerance compared to water-dependent crops. This makes it more suitable for {region} where rainfall variability is a concern.',
                    'data_points': {
                        'correlation_coefficient': corr_a['coefficient'],
                        'correlation_strength': corr_a['strength'],
                        'matched_years': corr_a.get('matched_data_points', 0)
                    },
                    'confidence': 'high' if corr_a.get('matched_data_points', 0) >= 5 else 'medium'
                })
    
    # Argument 2: Production Stability/Trend
    if crop_a_records:
        trend_a = calculate_trend(crop_a_records, 'Crop_Year', 'Production')
        
        if 'direction' in trend_a and trend_a['direction'] == 'increasing':
            arguments.append({
                'rank': 2,
                'title': f'{crop_a_name} Production Shows Positive Growth Trend',
                'argument': f'Over the past {trend_a.get("data_points", n_years)} years, {crop_a_name} production in {region} has shown a {trend_a["direction"]} trend with {trend_a["percent_change"]}% growth from {trend_a["start_year"]} to {trend_a["end_year"]}. This indicates growing farmer adoption and market viability.',
                'data_points': {
                    'trend_direction': trend_a['direction'],
                    'percent_change': trend_a['percent_change'],
                    'start_value': trend_a['start_value'],
                    'end_value': trend_a['end_value'],
                    'years_analyzed': trend_a.get('data_points', 0)
                },
                'confidence': 'high' if trend_a.get('data_points', 0) >= 5 else 'medium'
            })
    
    # Argument 3: Water Efficiency Comparison
    if crop_a_records and crop_b_records and rainfall_records:
        # Compare average production under similar rainfall conditions
        corr_b = correlate_production_with_climate(
            crop_b_records,
            rainfall_records,
            production_field="Production",
            climate_field="Rainfall"
        )
        
        if 'coefficient' in corr_a and 'coefficient' in corr_b:
            coef_a = abs(corr_a['coefficient'])
            coef_b = abs(corr_b['coefficient'])
            
            if coef_b > coef_a + 0.2:  # Crop B is significantly more water-dependent
                arguments.append({
                    'rank': 3,
                    'title': f'{crop_b_name} Requires Significantly More Water Resources',
                    'argument': f'{crop_b_name} shows {corr_b["strength"]} dependence on rainfall (r={corr_b["coefficient"]}), making it vulnerable to water scarcity. In contrast, {crop_a_name} demonstrates {corr_a["strength"]} rainfall dependence (r={corr_a["coefficient"]}), offering better water use efficiency for {region}.',
                    'data_points': {
                        f'{crop_a_name}_rainfall_correlation': corr_a['coefficient'],
                        f'{crop_b_name}_rainfall_correlation': corr_b['coefficient'],
                        'water_efficiency_advantage': round((coef_b - coef_a) * 100, 1)
                    },
                    'confidence': 'high'
                })
    
    # Argument 4: Economic Viability (if area data available)
    if crop_a_records:
        # Check if area under cultivation is increasing
        area_trend = calculate_trend(crop_a_records, 'Crop_Year', 'Area')
        
        if 'direction' in area_trend and area_trend['direction'] == 'increasing':
            arguments.append({
                'rank': 4,
                'title': f'Increasing Farmer Adoption of {crop_a_name}',
                'argument': f'Area under {crop_a_name} cultivation in {region} has increased by {area_trend["percent_change"]}% from {area_trend["start_year"]} to {area_trend["end_year"]}, demonstrating growing farmer confidence and market demand.',
                'data_points': {
                    'area_growth_percent': area_trend['percent_change'],
                    'start_area': area_trend['start_value'],
                    'end_area': area_trend['end_value']
                },
                'confidence': 'medium'
            })
    
    # Sort by rank and return top 3
    arguments.sort(key=lambda x: x['rank'])
    
    return {
        'policy_recommendation': f'Promote {crop_a_name} over {crop_b_name} in {region}',
        'top_arguments': arguments[:3],
        'total_arguments_generated': len(arguments),
        'analysis_period': f'Last {n_years} years',
        'data_sources_used': [
            'crop_production' if crop_a_records or crop_b_records else None,
            'rainfall_data' if rainfall_records else None
        ]
    }


def synthesize_multi_source_answer(
    question: str,
    data_sources: Dict[str, List[Dict[str, Any]]],
    analysis_type: str = "general"
) -> Dict[str, Any]:
    """Synthesize answer from multiple data sources with structured analysis.
    
    Args:
        question: User's question
        data_sources: Dict mapping source name to records
        analysis_type: Type of analysis ('comparison', 'trend', 'correlation', 'general')
    
    Returns:
        Dict with synthesized insights and structured data
    """
    insights = []
    
    # Extract available sources
    production_data = data_sources.get('crop_production', [])
    rainfall_data = data_sources.get('district_rainfall', []) or data_sources.get('rainfall_subdivisions', [])
    price_data = data_sources.get('daily_prices', []) or data_sources.get('variety_prices', [])
    temp_data = data_sources.get('temperature_series', [])
    
    # Generate insights based on available data
    if production_data:
        # Production insights
        if len(production_data) > 1:
            # Aggregate by state or crop
            if 'State_Name' in production_data[0]:
                state_totals = aggregate_by_group(production_data, 'State_Name', 'Production', 'sum')
                top_states = sorted(state_totals.items(), key=lambda x: x[1], reverse=True)[:5]
                
                insights.append({
                    'type': 'production_ranking',
                    'title': 'Top Producing States',
                    'data': [{'state': k, 'production': v} for k, v in top_states],
                    'summary': f'Top producer: {top_states[0][0]} with {top_states[0][1]:,.0f} tonnes'
                })
            
            # Trend analysis if multiple years
            if 'Crop_Year' in production_data[0]:
                trend = calculate_trend(production_data, 'Crop_Year', 'Production')
                if 'direction' in trend:
                    insights.append({
                        'type': 'trend_analysis',
                        'title': 'Production Trend',
                        'data': trend,
                        'summary': f'Production is {trend["direction"]} with {trend["percent_change"]}% change from {trend["start_year"]} to {trend["end_year"]}'
                    })
    
    if production_data and rainfall_data:
        # Correlation analysis
        corr = correlate_production_with_climate(
            production_data,
            rainfall_data,
            production_field='Production',
            climate_field='Rainfall'
        )
        
        if 'coefficient' in corr:
            insights.append({
                'type': 'correlation',
                'title': 'Production-Rainfall Relationship',
                'data': corr,
                'summary': f'{corr["strength"].capitalize()} {corr["direction"]} correlation (r={corr["coefficient"]}) between rainfall and production'
            })
    
    if price_data:
        # Price insights
        if 'modal_price' in price_data[0] or 'Modal_Price' in price_data[0]:
            price_field = 'modal_price' if 'modal_price' in price_data[0] else 'Modal_Price'
            
            if 'state' in price_data[0] or 'State' in price_data[0]:
                state_field = 'state' if 'state' in price_data[0] else 'State'
                avg_prices = aggregate_by_group(price_data, state_field, price_field, 'mean')
                
                insights.append({
                    'type': 'price_comparison',
                    'title': 'Average Prices by State',
                    'data': avg_prices,
                    'summary': f'Price range: ₹{min(avg_prices.values()):,.0f} to ₹{max(avg_prices.values()):,.0f} per quintal'
                })
    
    return {
        'question': question,
        'insights': insights,
        'data_sources_analyzed': list(data_sources.keys()),
        'total_records': sum(len(v) for v in data_sources.values()),
        'analysis_type': analysis_type
    }


def generate_comparative_summary(
    entity_a: str,
    entity_b: str,
    data_a: List[Dict[str, Any]],
    data_b: List[Dict[str, Any]],
    metric_field: str,
    entity_type: str = "state"
) -> Dict[str, Any]:
    """Generate comparative summary between two entities (states/districts/crops).
    
    Args:
        entity_a: Name of first entity
        entity_b: Name of second entity
        data_a: Records for first entity
        data_b: Records for second entity
        metric_field: Field to compare (e.g., 'Production', 'Rainfall')
        entity_type: Type of entity being compared
    
    Returns:
        Dict with comparative analysis
    """
    def extract_values(records):
        values = []
        for record in records:
            val = record.get(metric_field)
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    continue
        return values
    
    values_a = extract_values(data_a)
    values_b = extract_values(data_b)
    
    if not values_a or not values_b:
        return {'error': 'Insufficient data for comparison'}
    
    import statistics
    
    avg_a = statistics.mean(values_a)
    avg_b = statistics.mean(values_b)
    
    difference = avg_a - avg_b
    percent_diff = (difference / avg_b * 100) if avg_b > 0 else 0
    
    winner = entity_a if avg_a > avg_b else entity_b
    
    return {
        'comparison_type': f'{entity_type}_comparison',
        entity_a: {
            'average': round(avg_a, 2),
            'min': round(min(values_a), 2),
            'max': round(max(values_a), 2),
            'sample_size': len(values_a)
        },
        entity_b: {
            'average': round(avg_b, 2),
            'min': round(min(values_b), 2),
            'max': round(max(values_b), 2),
            'sample_size': len(values_b)
        },
        'comparison': {
            'higher': winner,
            'difference': round(abs(difference), 2),
            'percent_difference': round(abs(percent_diff), 2),
            'summary': f'{winner} has {abs(percent_diff):.1f}% higher {metric_field.lower()}'
        }
    }
