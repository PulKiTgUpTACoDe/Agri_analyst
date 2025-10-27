"""Correlation and statistical analysis utilities for climate-production relationships."""
from typing import List, Dict, Any, Tuple, Optional
import statistics


def calculate_correlation(
    x_values: List[float],
    y_values: List[float]
) -> Dict[str, Any]:
    """Calculate Pearson correlation coefficient between two variables.
    
    Args:
        x_values: List of values for first variable (e.g., rainfall)
        y_values: List of values for second variable (e.g., production)
    
    Returns:
        Dict with correlation coefficient, strength, and direction
    
    Example:
        rainfall = [800, 900, 1000, 1100]
        production = [1000, 1100, 1200, 1300]
        result = calculate_correlation(rainfall, production)
        # {'coefficient': 1.0, 'strength': 'very strong', 'direction': 'positive'}
    """
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return {'error': 'Insufficient or mismatched data'}
    
    n = len(x_values)
    
    # Calculate means
    mean_x = statistics.mean(x_values)
    mean_y = statistics.mean(y_values)
    
    # Calculate correlation coefficient
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
    
    sum_sq_x = sum((x - mean_x) ** 2 for x in x_values)
    sum_sq_y = sum((y - mean_y) ** 2 for y in y_values)
    
    denominator = (sum_sq_x * sum_sq_y) ** 0.5
    
    if denominator == 0:
        return {'error': 'Zero variance in data'}
    
    coefficient = numerator / denominator
    
    # Interpret strength
    abs_coef = abs(coefficient)
    if abs_coef >= 0.9:
        strength = "very strong"
    elif abs_coef >= 0.7:
        strength = "strong"
    elif abs_coef >= 0.5:
        strength = "moderate"
    elif abs_coef >= 0.3:
        strength = "weak"
    else:
        strength = "very weak"
    
    # Determine direction
    if coefficient > 0.05:
        direction = "positive"
    elif coefficient < -0.05:
        direction = "negative"
    else:
        direction = "negligible"
    
    return {
        'coefficient': round(coefficient, 3),
        'strength': strength,
        'direction': direction,
        'sample_size': n
    }


def correlate_production_with_climate(
    production_records: List[Dict[str, Any]],
    climate_records: List[Dict[str, Any]],
    production_field: str = "Production",
    climate_field: str = "Rainfall",
    year_field: str = "Year",
    match_field: Optional[str] = None
) -> Dict[str, Any]:
    """Correlate crop production with climate data.
    
    Args:
        production_records: Records with production data
        climate_records: Records with climate data (rainfall, temperature)
        production_field: Field name for production values
        climate_field: Field name for climate values
        year_field: Field name for year
        match_field: Optional field to match records (e.g., 'State', 'District')
    
    Returns:
        Dict with correlation analysis and matched data points
    
    Example:
        prod = [{'Year': 2020, 'State': 'Punjab', 'Production': 1000}]
        climate = [{'Year': 2020, 'State': 'Punjab', 'Rainfall': 800}]
        result = correlate_production_with_climate(prod, climate, match_field='State')
    """
    # Build lookup for climate data
    climate_lookup = {}
    for record in climate_records:
        year = record.get(year_field)
        climate_value = record.get(climate_field)
        
        if year is None or climate_value is None:
            continue
        
        try:
            year_int = int(year)
            climate_float = float(climate_value)
            
            if match_field:
                match_value = str(record.get(match_field, ""))
                key = (year_int, match_value)
            else:
                key = year_int
            
            climate_lookup[key] = climate_float
        except (ValueError, TypeError):
            continue
    
    # Match production with climate
    matched_pairs = []
    for record in production_records:
        year = record.get(year_field)
        prod_value = record.get(production_field)
        
        if year is None or prod_value is None:
            continue
        
        try:
            year_int = int(year)
            prod_float = float(prod_value)
            
            if match_field:
                match_value = str(record.get(match_field, ""))
                key = (year_int, match_value)
            else:
                key = year_int
            
            if key in climate_lookup:
                matched_pairs.append({
                    'year': year_int,
                    'production': prod_float,
                    'climate': climate_lookup[key],
                    'match_field_value': match_value if match_field else None
                })
        except (ValueError, TypeError):
            continue
    
    if len(matched_pairs) < 2:
        return {
            'error': 'Insufficient matched data points',
            'matched_count': len(matched_pairs)
        }
    
    # Extract values for correlation
    production_values = [p['production'] for p in matched_pairs]
    climate_values = [p['climate'] for p in matched_pairs]
    
    # Calculate correlation
    correlation = calculate_correlation(climate_values, production_values)
    
    return {
        **correlation,
        'matched_data_points': len(matched_pairs),
        'production_range': {
            'min': round(min(production_values), 2),
            'max': round(max(production_values), 2),
            'mean': round(statistics.mean(production_values), 2)
        },
        'climate_range': {
            'min': round(min(climate_values), 2),
            'max': round(max(climate_values), 2),
            'mean': round(statistics.mean(climate_values), 2)
        },
        'sample_pairs': matched_pairs[:5]  # Show first 5 for reference
    }


def identify_optimal_conditions(
    records: List[Dict[str, Any]],
    production_field: str,
    climate_field: str,
    top_n: int = 10
) -> Dict[str, Any]:
    """Identify climate conditions associated with highest production.
    
    Args:
        records: Combined records with both production and climate data
        production_field: Field name for production
        climate_field: Field name for climate variable
        top_n: Number of top production records to analyze
    
    Returns:
        Dict with optimal climate range and statistics
    
    Example:
        records = [
            {'Production': 1000, 'Rainfall': 800},
            {'Production': 1200, 'Rainfall': 900},
        ]
        result = identify_optimal_conditions(records, 'Production', 'Rainfall')
    """
    # Filter valid records
    valid_records = []
    for record in records:
        prod = record.get(production_field)
        climate = record.get(climate_field)
        
        if prod is not None and climate is not None:
            try:
                valid_records.append({
                    'production': float(prod),
                    'climate': float(climate)
                })
            except (ValueError, TypeError):
                continue
    
    if len(valid_records) < top_n:
        top_n = len(valid_records)
    
    if top_n == 0:
        return {'error': 'No valid data'}
    
    # Sort by production and get top N
    sorted_records = sorted(valid_records, key=lambda x: x['production'], reverse=True)
    top_records = sorted_records[:top_n]
    
    # Analyze climate conditions for top production
    top_climate_values = [r['climate'] for r in top_records]
    
    return {
        'optimal_climate_range': {
            'min': round(min(top_climate_values), 2),
            'max': round(max(top_climate_values), 2),
            'mean': round(statistics.mean(top_climate_values), 2),
            'median': round(statistics.median(top_climate_values), 2)
        },
        'top_production_range': {
            'min': round(min(r['production'] for r in top_records), 2),
            'max': round(max(r['production'] for r in top_records), 2),
            'mean': round(statistics.mean(r['production'] for r in top_records), 2)
        },
        'sample_size': top_n,
        'interpretation': f"Highest production observed with {climate_field} between {round(min(top_climate_values), 0)} and {round(max(top_climate_values), 0)}"
    }


def compare_climate_impact(
    group_a_records: List[Dict[str, Any]],
    group_b_records: List[Dict[str, Any]],
    production_field: str,
    climate_field: str,
    group_a_name: str = "Group A",
    group_b_name: str = "Group B"
) -> Dict[str, Any]:
    """Compare climate impact on production between two groups (states/regions).
    
    Args:
        group_a_records: Records for first group
        group_b_records: Records for second group
        production_field: Field name for production
        climate_field: Field name for climate variable
        group_a_name: Name of first group
        group_b_name: Name of second group
    
    Returns:
        Dict with comparative analysis
    """
    def extract_values(records):
        prod_vals = []
        climate_vals = []
        for record in records:
            prod = record.get(production_field)
            climate = record.get(climate_field)
            if prod is not None and climate is not None:
                try:
                    prod_vals.append(float(prod))
                    climate_vals.append(float(climate))
                except (ValueError, TypeError):
                    continue
        return prod_vals, climate_vals
    
    prod_a, climate_a = extract_values(group_a_records)
    prod_b, climate_b = extract_values(group_b_records)
    
    if len(prod_a) < 2 or len(prod_b) < 2:
        return {'error': 'Insufficient data for comparison'}
    
    corr_a = calculate_correlation(climate_a, prod_a)
    corr_b = calculate_correlation(climate_b, prod_b)
    
    return {
        group_a_name: {
            'correlation': corr_a,
            'avg_production': round(statistics.mean(prod_a), 2),
            'avg_climate': round(statistics.mean(climate_a), 2),
            'sample_size': len(prod_a)
        },
        group_b_name: {
            'correlation': corr_b,
            'avg_production': round(statistics.mean(prod_b), 2),
            'avg_climate': round(statistics.mean(climate_b), 2),
            'sample_size': len(prod_b)
        },
        'comparison': {
            'stronger_correlation': group_a_name if abs(corr_a.get('coefficient', 0)) > abs(corr_b.get('coefficient', 0)) else group_b_name,
            'higher_avg_production': group_a_name if statistics.mean(prod_a) > statistics.mean(prod_b) else group_b_name,
            'production_difference': round(abs(statistics.mean(prod_a) - statistics.mean(prod_b)), 2)
        }
    }
