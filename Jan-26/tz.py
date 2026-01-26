#!/usr/bin/env python3
"""
Parse coordinates from the data file and get timezone information for each point.
"""

import re
import sys
from typing import List, Tuple
from datetime import datetime

def decimal_to_dms(decimal_degrees: float) -> Tuple[int, int, float]:
    """Convert decimal degrees to degrees, minutes, seconds.
    
    Returns:
        Tuple of (degrees, minutes, seconds)
    """
    degrees = int(decimal_degrees)
    minutes_float = abs(decimal_degrees - degrees) * 60.0
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60.0
    return (degrees, minutes, seconds)

def format_dms(degrees: int, minutes: int, seconds: float) -> str:
    """Format degrees, minutes, seconds as a string.
    
    Returns:
        Formatted string like "32° 27' 2.16\""
    """
    return f"{degrees}° {minutes}' {seconds:.2f}\""

# Try to import timezone finder libraries
try:
    from timezonefinder import TimezoneFinder
    tf_available = True
except ImportError:
    try:
        from timezonefinderL import TimezoneFinder
        tf_available = True
    except ImportError:
        tf_available = False
        print("Warning: timezonefinder not available. Install with: pip install timezonefinder", file=sys.stderr)

try:
    import pytz
    pytz_available = True
except ImportError:
    pytz_available = False
    print("Warning: pytz not available. Install with: pip install pytz", file=sys.stderr)

def parse_coordinate_from_digits(digit_string: str, max_value: float, max_digits_before_decimal: int) -> float:
    """Parse coordinate from a string of digits assuming DMS format (DDMMSS or DDDMMSS).
    
    The digits are interpreted as degrees, minutes, seconds format.
    For rows: max 2 digits for degrees (DDMMSS format)
    For columns: max 3 digits for degrees (DDDMMSS format)
    
    Args:
        digit_string: String of digits (e.g., "324506" or "3031976")
        max_value: Maximum allowed value (180 for longitude, 90 for latitude)
        max_digits_before_decimal: Maximum digits for degrees (2 for rows, 3 for columns)
    
    Returns:
        Decimal degrees converted from DMS format
    """
    if not digit_string:
        return None
    
    num_len = len(digit_string)
    
    # For rows: DDMMSS format (2 digits degrees, 2 digits minutes, 2 digits seconds)
    if max_digits_before_decimal == 2:
        if num_len >= 6:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:6])
            # Remaining digits are fractional seconds
            if num_len > 6:
                fraction = int(digit_string[6:]) / (10 ** (num_len - 6))
                seconds += fraction
        elif num_len == 5:
            # 5 digits: DDMMS format (2 digits degrees, 2 digits minutes, 1 digit seconds)
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:5])
        elif num_len == 4:
            # 4 digits: DDMM format (2 digits degrees, 2 digits minutes)
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = 0
        elif num_len == 3:
            # 3 digits: DDM format (2 digits degrees, 1 digit minutes)
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:3])
            seconds = 0
        else:
            degrees = int(digit_string)
            minutes = 0
            seconds = 0
        
        # Validate: minutes and seconds should be < 60
        if minutes >= 60 or seconds >= 60:
            # Invalid, try alternative interpretation
            if num_len == 5:
                # Try as DDDMM (3 digits degrees, 2 digits minutes) but max is 2 for rows
                # So this shouldn't happen, but handle gracefully
                return None
            return None
        
        decimal_degrees = degrees + minutes/60.0 + seconds/3600.0
        return decimal_degrees
    
    # For columns: DDDMMSS format (3 digits degrees, 2 digits minutes, 2 digits seconds)
    # But we need to be flexible - try different splits and pick valid one
    elif max_digits_before_decimal == 3:
        # Try different splits: 3-2-2, 2-2-2, 2-2-3, etc.
        best_result = None
        
        # Try 3-2-2 split (DDDMMSS)
        if num_len >= 7:
            degrees = int(digit_string[:3])
            minutes = int(digit_string[3:5])
            seconds = int(digit_string[5:7])
            if degrees < 180 and minutes < 60 and seconds < 60:
                fraction = 0
                if num_len > 7:
                    fraction = int(digit_string[7:]) / (10 ** (num_len - 7))
                best_result = degrees + minutes/60.0 + (seconds + fraction)/3600.0
        
        # Try 2-2-2 split (DDMMSS) if 3-2-2 didn't work or was invalid
        if best_result is None and num_len >= 6:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:6])
            if degrees < 180 and minutes < 60 and seconds < 60:
                fraction = 0
                if num_len > 6:
                    fraction = int(digit_string[6:]) / (10 ** (num_len - 6))
                best_result = degrees + minutes/60.0 + (seconds + fraction)/3600.0
        
        # Try 2-2-3 split (DDMMSSS) if still no result
        if best_result is None and num_len >= 7:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:7])
            if degrees < 180 and minutes < 60:
                fraction = 0
                if num_len > 7:
                    fraction = int(digit_string[7:]) / (10 ** (num_len - 7))
                best_result = degrees + minutes/60.0 + (seconds + fraction)/3600.0
        
        # Try 2-3-2 split (DDMMMSS)
        if best_result is None and num_len >= 7:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:5])
            seconds = int(digit_string[5:7])
            if degrees < 180 and minutes < 60 and seconds < 60:
                fraction = 0
                if num_len > 7:
                    fraction = int(digit_string[7:]) / (10 ** (num_len - 7))
                best_result = degrees + minutes/60.0 + (seconds + fraction)/3600.0
        
        if best_result is not None:
            return best_result
        
        # Fallback: try simpler splits for shorter numbers
        if num_len == 6:
            # Try 2-2-2 (DDMMSS) - already tried above, but try again as fallback
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:6])
            if degrees < 180 and minutes < 60 and seconds < 60:
                return degrees + minutes/60.0 + seconds/3600.0
            # Try 3-2-1 (DDDMMS)
            degrees = int(digit_string[:3])
            minutes = int(digit_string[3:5])
            seconds = int(digit_string[5:6])
            if degrees < 180 and minutes < 60:
                return degrees + minutes/60.0 + seconds/3600.0
        elif num_len == 5:
            # Try 2-2-1 (DDMMS)
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:5])
            if degrees < 180 and minutes < 60:
                return degrees + minutes/60.0 + seconds/3600.0
            # Try 3-2 (DDDMM)
            degrees = int(digit_string[:3])
            minutes = int(digit_string[3:5])
            if degrees < 180 and minutes < 60:
                return degrees + minutes/60.0
            # Try 2-3 (DDMMM) - minutes can be > 60 if interpreted differently
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:5])
            if degrees < 180 and minutes < 60:
                return degrees + minutes/60.0
        elif num_len == 4:
            # Try 2-2 (DDMM)
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            if degrees < 180 and minutes < 60:
                return degrees + minutes/60.0
            # Try 3-1 (DDDM)
            degrees = int(digit_string[:3])
            if degrees < 180:
                return float(degrees)
        elif num_len >= 3:
            degrees = int(digit_string[:3])
            if degrees < 180:
                if num_len > 3:
                    minutes = int(digit_string[3:])
                    if minutes < 60:
                        return degrees + minutes/60.0
                return float(degrees)
        elif num_len == 2:
            return float(int(digit_string))
        
        return None
    
    return None

def get_timezone_info(lat: float, lon: float) -> Tuple[str, float]:
    """Get timezone name and GMT offset for given coordinates."""
    if not tf_available:
        return None, None
    
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    
    if tz_name and pytz_available:
        tz = pytz.timezone(tz_name)
        # Get UTC offset
        now = datetime.now(tz)
        offset_seconds = now.utcoffset().total_seconds()
        offset_hours = offset_seconds / 3600.0
        return tz_name, offset_hours
    elif tz_name:
        # If we have timezone name but no pytz, just return the name
        return tz_name, None
    else:
        return None, None

def main():
    # Try to read from file, otherwise use embedded data
    try:
        with open('data.txt', 'r') as f:
            lines = [line.rstrip('\n') for line in f.readlines()]
    except FileNotFoundError:
        # Data from the file
        data = """336111111752
060045631965
343005943513
195242552307
922923199005
_78153003176
___642148___


324506
300240
402700
425229
311409
272654
365201
211408
323047
04229_
143957
35056_"""
        lines = data.strip().split('\n')
    
    # Find the separator (empty line)
    separator_idx = None
    for i, line in enumerate(lines):
        if not line.strip():
            separator_idx = i
            break
    
    if separator_idx is None:
        print("Error: Could not find separator between columns and rows")
        return
    
    # Extract columns (first section) - get 12 columns
    # For each column position (0-11), extract digits from top to bottom
    column_lines = lines[:separator_idx]
    
    # Clean lines (remove underscores)
    cleaned_column_lines = []
    for line in column_lines:
        cleaned = line.replace('_', '').strip()
        if cleaned:
            cleaned_column_lines.append(cleaned)
    
    columns = []
    # Extract 12 columns by taking digit at each position (0-11) from top to bottom
    for col_idx in range(12):
        col_digits = []
        for cleaned_line in cleaned_column_lines:
            if col_idx < len(cleaned_line):
                col_digits.append(cleaned_line[col_idx])
        
        if col_digits:
            # Combine digits from top to bottom
            digit_string = ''.join(col_digits)
            # Parse by finding decimal placement so result < 180, max 3 digits before decimal
            coord = parse_coordinate_from_digits(digit_string, 180.0, 3)
            if coord is not None:
                columns.append((digit_string, coord))
    
    # Extract rows (second section) - take all 12 rows
    row_lines = lines[separator_idx+1:]
    rows = []
    for line in row_lines:
        if line.strip():
            cleaned = line.replace('_', '').strip()
            if cleaned:
                # Parse by finding decimal placement so result < 90, max 2 digits before decimal
                coord = parse_coordinate_from_digits(cleaned, 90.0, 2)
                if coord is not None:
                    rows.append((cleaned, coord))
    # Ensure we have exactly 12 rows
    rows = rows[:12]
    
    print(f"Found {len(columns)} columns and {len(rows)} rows\n")
    print("=" * 80)
    
    if not tf_available:
        print("ERROR: timezonefinder library is required. Please install it with:")
        print("  pip install timezonefinder")
        print("\nOr if that doesn't work, try:")
        print("  pip install timezonefinderL")
        return
    
    # Get timezone for each point
    tf = TimezoneFinder()
    
    # Process matching pairs: row 1→col 1, row 2→col 2, etc. (12 pairs total)
    num_pairs = min(len(rows), len(columns))
    print(f"Processing {num_pairs} matching pairs (row 1→col 1, row 2→col 2, etc.):\n")
    
    for idx in range(num_pairs):
        row_str, row_val = rows[idx]
        col_str, col_val = columns[idx]
        
        # Try both interpretations: (row=lat, col=lon) and (row=lon, col=lat)
        # Start with row as latitude, column as longitude
        lat, lon = row_val, col_val
        
        # Validate coordinates are in reasonable range
        # If coordinates are out of range, they might be in wrong format
        # Try swapping if needed
        if abs(lat) > 90 or abs(lon) > 180:
            # Try swapping
            lat, lon = col_val, row_val
            # If still invalid after swapping, the coordinates are likely wrong
            if abs(lat) > 90 or abs(lon) > 180:
                print(f"  Warning: Coordinates ({lat:.6f}, {lon:.6f}) are out of valid range")
                print(f"  Skipping timezone lookup for this pair")
                print()
                continue
        
        tz_name = tf.timezone_at(lat=lat, lng=lon)
        
        if tz_name:
            if pytz_available:
                tz = pytz.timezone(tz_name)
                now = datetime.now(tz)
                offset_seconds = now.utcoffset().total_seconds()
                offset_hours = offset_seconds / 3600.0
                
                # Convert to DMS format
                lat_d, lat_m, lat_s = decimal_to_dms(lat)
                lon_d, lon_m, lon_s = decimal_to_dms(lon)
                
                print(f"Pair {idx + 1} (row={row_str}, col={col_str}):")
                print(f"  Coordinates: {format_dms(lat_d, lat_m, lat_s)} N, {format_dms(lon_d, lon_m, lon_s)} E")
                print(f"  (Decimal: {lat:.6f}, {lon:.6f})")
                print(f"  Timezone: {tz_name}")
                print(f"  GMT Offset: {offset_hours:+.2f} hours")
                print()
            else:
                # Convert to DMS format
                lat_d, lat_m, lat_s = decimal_to_dms(lat)
                lon_d, lon_m, lon_s = decimal_to_dms(lon)
                
                print(f"Pair {idx + 1} (row={row_str}, col={col_str}):")
                print(f"  Coordinates: {format_dms(lat_d, lat_m, lat_s)} N, {format_dms(lon_d, lon_m, lon_s)} E")
                print(f"  (Decimal: {lat:.6f}, {lon:.6f})")
                print(f"  Timezone: {tz_name}")
                print(f"  GMT Offset: (pytz not available to calculate)")
                print()
        else:
            # Convert to DMS format
            lat_d, lat_m, lat_s = decimal_to_dms(lat)
            lon_d, lon_m, lon_s = decimal_to_dms(lon)
            
            print(f"Pair {idx + 1} (row={row_str}, col={col_str}):")
            print(f"  Coordinates: {format_dms(lat_d, lat_m, lat_s)} N, {format_dms(lon_d, lon_m, lon_s)} E")
            print(f"  (Decimal: {lat:.6f}, {lon:.6f})")
            print(f"  Timezone: Not found (coordinates may be out of range)")
            print()

if __name__ == "__main__":
    main()
