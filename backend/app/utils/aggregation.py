"""Aggregation utilities for multi-year analysis, rankings, and statistical computations."""
from typing import List, Dict, Any, Optional
from collections import defaultdict
import statistics


def aggregate_multi_year_average(
    records: List[Dict[str, Any]],
    value_field: str,
    group_by: Optional[List[str]] = None
) -> Dict[str, float]:
    """Calculate multi-year averages grouped by specified fields.
    
    Args:
        records: List of records from API
        value_field: Field to average (e.g., 'Production', 'Area', 'Rainfall')
        group_by: Fields to group by (e.g., ['State_Name', 'Crop'])
    
    Returns:
        Dict mapping group key to average value
    
    Example:
        records = [
            {'State': 'Punjab', 'Crop': 'Rice', 'Year': 2020, 'Production': 1000},
            {'State': 'Punjab', 'Crop': 'Rice', 'Year': 2021, 'Production': 1200},
        ]
        result = aggregate_multi_year_average(records, 'Production', ['State', 'Crop'])
        # {'Punjab|Rice': 1100.0}
    """
    if not records:
        return {}
    
    group_by = group_by or []
    groups = defaultdict(list)
    
    for record in records:
        # Build group key
        if group_by:
            key_parts = [str(record.get(field, "Unknown")) for field in group_by]
            key = "|".join(key_parts)
        else:
            key = "overall"
        
        # Extract numeric value
        value = record.get(value_field)
        if value is not None:
            try:
                groups[key].append(float(value))
            except (ValueError, TypeError):
                continue
    
    # Calculate averages
    return {key: statistics.mean(values) for key, values in groups.items() if values}


def top_n_ranking(
    records: List[Dict[str, Any]],
    value_field: str,
    n: int = 10,
    group_by: Optional[str] = None,
    ascending: bool = False
) -> List[Dict[str, Any]]:
    """Rank records by a value field and return top N.
    
    Args:
        records: List of records from API
        value_field: Field to rank by (e.g., 'Production', 'Area')
        n: Number of top records to return
        group_by: Optional field to identify items (e.g., 'District_Name', 'Crop')
        ascending: If True, return lowest values (for deficit analysis)
    
    Returns:
        List of top N records with rank added
    
    Example:
        records = [
            {'District': 'A', 'Production': 1000},
            {'District': 'B', 'Production': 2000},
        ]
        result = top_n_ranking(records, 'Production', n=2)
        # [{'District': 'B', 'Production': 2000, 'rank': 1}, ...]
    """
    if not records:
        return []
    
    # Filter records with valid numeric values
    valid_records = []
    for record in records:
        value = record.get(value_field)
        if value is not None:
            try:
                record_copy = record.copy()
                record_copy['_sort_value'] = float(value)
                valid_records.append(record_copy)
            except (ValueError, TypeError):
                continue
    
    # Sort by value
    sorted_records = sorted(
        valid_records,
        key=lambda x: x['_sort_value'],
        reverse=not ascending
    )
    
    # Add rank and return top N
    result = []
    for i, record in enumerate(sorted_records[:n], start=1):
        record['rank'] = i
        del record['_sort_value']
        result.append(record)
    
    return result


def aggregate_by_group(
    records: List[Dict[str, Any]],
    group_field: str,
    value_field: str,
    agg_func: str = "sum"
) -> Dict[str, float]:
    """Aggregate values by a grouping field.
    
    Args:
        records: List of records from API
        group_field: Field to group by (e.g., 'State_Name', 'Season')
        value_field: Field to aggregate (e.g., 'Production', 'Area')
        agg_func: Aggregation function ('sum', 'mean', 'max', 'min', 'count')
    
    Returns:
        Dict mapping group to aggregated value
    
    Example:
        records = [
            {'State': 'Punjab', 'Production': 1000},
            {'State': 'Punjab', 'Production': 1200},
            {'State': 'Haryana', 'Production': 800},
        ]
        result = aggregate_by_group(records, 'State', 'Production', 'sum')
        # {'Punjab': 2200.0, 'Haryana': 800.0}
    """
    if not records:
        return {}
    
    groups = defaultdict(list)
    
    for record in records:
        group_key = str(record.get(group_field, "Unknown"))
        value = record.get(value_field)
        
        if value is not None:
            try:
                groups[group_key].append(float(value))
            except (ValueError, TypeError):
                continue
    
    # Apply aggregation function
    result = {}
    for key, values in groups.items():
        if not values:
            continue
        
        if agg_func == "sum":
            result[key] = sum(values)
        elif agg_func == "mean":
            result[key] = statistics.mean(values)
        elif agg_func == "max":
            result[key] = max(values)
        elif agg_func == "min":
            result[key] = min(values)
        elif agg_func == "count":
            result[key] = len(values)
        else:
            result[key] = sum(values)  # default to sum
    
    return result


def calculate_year_over_year_growth(
    records: List[Dict[str, Any]],
    year_field: str,
    value_field: str,
    group_by: Optional[str] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Calculate year-over-year growth rates.
    
    Args:
        records: List of records from API
        year_field: Field containing year (e.g., 'Crop_Year', 'Year')
        value_field: Field to calculate growth for (e.g., 'Production')
        group_by: Optional field to group by (e.g., 'State_Name', 'Crop')
    
    Returns:
        Dict mapping group to list of year-over-year growth records
    
    Example:
        records = [
            {'State': 'Punjab', 'Year': 2020, 'Production': 1000},
            {'State': 'Punjab', 'Year': 2021, 'Production': 1100},
        ]
        result = calculate_year_over_year_growth(records, 'Year', 'Production', 'State')
        # {'Punjab': [{'year': 2021, 'value': 1100, 'growth_rate': 10.0, 'prev_value': 1000}]}
    """
    if not records:
        return {}
    
    # Group records
    groups = defaultdict(list)
    for record in records:
        group_key = str(record.get(group_by, "overall")) if group_by else "overall"
        year = record.get(year_field)
        value = record.get(value_field)
        
        if year is not None and value is not None:
            try:
                groups[group_key].append({
                    'year': int(year),
                    'value': float(value)
                })
            except (ValueError, TypeError):
                continue
    
    # Calculate growth rates for each group
    result = {}
    for group_key, data_points in groups.items():
        # Sort by year
        sorted_data = sorted(data_points, key=lambda x: x['year'])
        
        growth_records = []
        for i in range(1, len(sorted_data)):
            prev = sorted_data[i - 1]
            curr = sorted_data[i]
            
            if prev['value'] > 0:
                growth_rate = ((curr['value'] - prev['value']) / prev['value']) * 100
            else:
                growth_rate = 0.0
            
            growth_records.append({
                'year': curr['year'],
                'value': curr['value'],
                'prev_value': prev['value'],
                'growth_rate': round(growth_rate, 2),
                'absolute_change': round(curr['value'] - prev['value'], 2)
            })
        
        if growth_records:
            result[group_key] = growth_records
    
    return result


def calculate_trend(
    records: List[Dict[str, Any]],
    year_field: str,
    value_field: str
) -> Dict[str, Any]:
    """Calculate linear trend (slope and direction) for time series data.
    
    Args:
        records: List of records from API
        year_field: Field containing year
        value_field: Field to analyze trend for
    
    Returns:
        Dict with trend analysis (slope, direction, start_value, end_value)
    
    Example:
        records = [
            {'Year': 2018, 'Production': 1000},
            {'Year': 2019, 'Production': 1100},
            {'Year': 2020, 'Production': 1200},
        ]
        result = calculate_trend(records, 'Year', 'Production')
        # {'slope': 100.0, 'direction': 'increasing', 'start_value': 1000, 'end_value': 1200, ...}
    """
    if len(records) < 2:
        return {'error': 'Insufficient data for trend analysis'}
    
    # Extract year-value pairs
    data_points = []
    for record in records:
        year = record.get(year_field)
        value = record.get(value_field)
        
        if year is not None and value is not None:
            try:
                data_points.append((int(year), float(value)))
            except (ValueError, TypeError):
                continue
    
    if len(data_points) < 2:
        return {'error': 'Insufficient valid data points'}
    
    # Sort by year
    data_points.sort(key=lambda x: x[0])
    
    # Simple linear regression (least squares)
    n = len(data_points)
    sum_x = sum(x for x, y in data_points)
    sum_y = sum(y for x, y in data_points)
    sum_xy = sum(x * y for x, y in data_points)
    sum_x2 = sum(x * x for x, y in data_points)
    
    # Calculate slope
    denominator = n * sum_x2 - sum_x * sum_x
    if denominator == 0:
        slope = 0
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denominator
    
    # Determine direction
    if slope > 0.01:
        direction = "increasing"
    elif slope < -0.01:
        direction = "decreasing"
    else:
        direction = "stable"
    
    return {
        'slope': round(slope, 2),
        'direction': direction,
        'start_year': data_points[0][0],
        'end_year': data_points[-1][0],
        'start_value': round(data_points[0][1], 2),
        'end_value': round(data_points[-1][1], 2),
        'total_change': round(data_points[-1][1] - data_points[0][1], 2),
        'percent_change': round(((data_points[-1][1] - data_points[0][1]) / data_points[0][1] * 100) if data_points[0][1] > 0 else 0, 2),
        'data_points': len(data_points)
    }
