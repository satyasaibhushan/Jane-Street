#!/usr/bin/env python3
"""
Parse coordinates from the data file and get timezone information for each point.
"""

import re
import sys
import time
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
        print(
            "Warning: timezonefinder not available. Install with: pip install timezonefinder",
            file=sys.stderr,
        )

try:
    import pytz

    pytz_available = True
except ImportError:
    pytz_available = False
    print(
        "Warning: pytz not available. Install with: pip install pytz", file=sys.stderr
    )

try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError

    geopy_available = True
except ImportError:
    geopy_available = False
    print(
        "Warning: geopy not available. Install with: pip install geopy", file=sys.stderr
    )

try:
    import folium

    folium_available = True
except ImportError:
    folium_available = False
    print(
        "Warning: folium not available. Install with: pip install folium",
        file=sys.stderr,
    )


def parse_coordinate_from_digits(
    digit_string: str, max_value: float, max_digits_before_decimal: int
) -> float:
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

        decimal_degrees = degrees + minutes / 60.0 + seconds / 3600.0
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
                best_result = degrees + minutes / 60.0 + (seconds + fraction) / 3600.0

        # Try 2-2-2 split (DDMMSS) if 3-2-2 didn't work or was invalid
        if best_result is None and num_len >= 6:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:6])
            if degrees < 180 and minutes < 60 and seconds < 60:
                fraction = 0
                if num_len > 6:
                    fraction = int(digit_string[6:]) / (10 ** (num_len - 6))
                best_result = degrees + minutes / 60.0 + (seconds + fraction) / 3600.0

        # Try 2-2-3 split (DDMMSSS) if still no result
        if best_result is None and num_len >= 7:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:7])
            if degrees < 180 and minutes < 60:
                fraction = 0
                if num_len > 7:
                    fraction = int(digit_string[7:]) / (10 ** (num_len - 7))
                best_result = degrees + minutes / 60.0 + (seconds + fraction) / 3600.0

        # Try 2-3-2 split (DDMMMSS)
        if best_result is None and num_len >= 7:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:5])
            seconds = int(digit_string[5:7])
            if degrees < 180 and minutes < 60 and seconds < 60:
                fraction = 0
                if num_len > 7:
                    fraction = int(digit_string[7:]) / (10 ** (num_len - 7))
                best_result = degrees + minutes / 60.0 + (seconds + fraction) / 3600.0

        if best_result is not None:
            return best_result

        # Fallback: try simpler splits for shorter numbers
        if num_len == 6:
            # Try 2-2-2 (DDMMSS) - already tried above, but try again as fallback
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:6])
            if degrees < 180 and minutes < 60 and seconds < 60:
                return degrees + minutes / 60.0 + seconds / 3600.0
            # Try 3-2-1 (DDDMMS)
            degrees = int(digit_string[:3])
            minutes = int(digit_string[3:5])
            seconds = int(digit_string[5:6])
            if degrees < 180 and minutes < 60:
                return degrees + minutes / 60.0 + seconds / 3600.0
        elif num_len == 5:
            # Try 2-2-1 (DDMMS)
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:5])
            if degrees < 180 and minutes < 60:
                return degrees + minutes / 60.0 + seconds / 3600.0
            # Try 3-2 (DDDMM)
            degrees = int(digit_string[:3])
            minutes = int(digit_string[3:5])
            if degrees < 180 and minutes < 60:
                return degrees + minutes / 60.0
            # Try 2-3 (DDMMM) - minutes can be > 60 if interpreted differently
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:5])
            if degrees < 180 and minutes < 60:
                return degrees + minutes / 60.0
        elif num_len == 4:
            # Try 2-2 (DDMM)
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            if degrees < 180 and minutes < 60:
                return degrees + minutes / 60.0
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
                        return degrees + minutes / 60.0
                return float(degrees)
        elif num_len == 2:
            return float(int(digit_string))

        return None

    return None


def create_world_map(points: List[dict]):
    """Create an interactive world map with all coordinate points marked."""
    # Calculate center of all points
    if not points:
        return

    avg_lat = sum(p["lat"] for p in points) / len(points)
    avg_lon = sum(p["lon"] for p in points) / len(points)

    # Create map centered on average location
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=2)

    # Color scheme for different combinations
    combo_colors = {"++": "blue", "+-": "green", "-+": "red", "--": "purple"}

    # Add markers for each point
    for point in points:
        lat = point["lat"]
        lon = point["lon"]
        pair = point["pair"]
        combo = point["combo"]
        timezone = point["timezone"]
        offset = point["offset"]
        dms = point["dms"]

        # Create popup text
        popup_text = f"""
        <b>Pair {pair} - {combo}</b><br>
        Coordinates: {dms}<br>
        Decimal: ({lat:.6f}, {lon:.6f})<br>
        Timezone: {timezone}<br>
        """
        if offset is not None:
            popup_text += f"GMT Offset: {offset:+.2f} hours"
        else:
            popup_text += "GMT Offset: N/A"

        # Add marker
        folium.CircleMarker(
            location=[lat, lon],
            radius=8,
            popup=folium.Popup(popup_text, max_width=300),
            color=combo_colors.get(combo, "gray"),
            fill=True,
            fillColor=combo_colors.get(combo, "gray"),
            fillOpacity=0.7,
            tooltip=f"Pair {pair} ({combo}): {timezone}",
        ).add_to(m)

    # Add legend
    legend_html = """
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 120px; 
                background-color: white; z-index:9999; font-size:14px;
                border:2px solid grey; border-radius:5px; padding: 10px">
    <p><b>Legend</b></p>
    <p><i class="fa fa-circle" style="color:blue"></i> ++ (N, E)</p>
    <p><i class="fa fa-circle" style="color:green"></i> +- (N, W)</p>
    <p><i class="fa fa-circle" style="color:red"></i> -+ (S, E)</p>
    <p><i class="fa fa-circle" style="color:purple"></i> -- (S, W)</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Save map
    output_file = "world_map.html"
    m.save(output_file)
    print(f"World map saved to: {output_file}")
    print(f"Open {output_file} in your web browser to view the map")


def get_location_name(lat: float, lon: float) -> str:
    """Get city/location name for given coordinates using reverse geocoding."""
    if not geopy_available:
        return None

    try:
        geolocator = Nominatim(user_agent="timezone_lookup")
        location = geolocator.reverse((lat, lon), timeout=10, exactly_one=True)
        if location:
            address = location.raw.get("address", {})
            # Try to get city, town, or village name
            city = (
                address.get("city")
                or address.get("town")
                or address.get("village")
                or address.get("municipality")
                or address.get("county")
                or address.get("state")
                or address.get("country")
            )
            return city
    except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
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
        with open("data.txt", "r") as f:
            lines = [line.rstrip("\n") for line in f.readlines()]
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
        lines = data.strip().split("\n")

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
        cleaned = line.replace("_", "").strip()
        if cleaned:
            cleaned_column_lines.append(cleaned)

    # Read offsets from file
    column_signs = []
    row_signs = []
    try:
        with open("offests.txt", "r") as f:
            offset_lines = [line.strip() for line in f.readlines() if line.strip()]
        if len(offset_lines) >= 1:
            # First row: sign pattern for columns (each char is + or -)
            # Reverse interpretation: + becomes - and - becomes +
            column_signs = [-1 if c == "+" else 1 for c in offset_lines[0]]
        if len(offset_lines) >= 2:
            # Second row: sign pattern for rows (each char is + or -)
            # Reverse interpretation: + becomes - and - becomes +
            row_signs = [-1 if c == "+" else 1 for c in offset_lines[1]]
    except FileNotFoundError:
        print("Warning: offests.txt not found. Proceeding without sign offsets.")
    except Exception as e:
        print(f"Warning: Error reading offsets: {e}. Proceeding without sign offsets.")

    columns = []
    # Extract 12 columns by taking digit at each position (0-11) from top to bottom
    for col_idx in range(12):
        col_digits = []
        for cleaned_line in cleaned_column_lines:
            if col_idx < len(cleaned_line):
                col_digits.append(cleaned_line[col_idx])

        if col_digits:
            # Combine digits from top to bottom
            digit_string = "".join(col_digits)
            # Parse by finding decimal placement so result < 180, max 3 digits before decimal
            coord = parse_coordinate_from_digits(digit_string, 180.0, 3)
            if coord is not None:
                # Keep base coordinate positive, signs will be applied later
                columns.append((digit_string, abs(coord)))

    # Extract rows (second section) - take all 12 rows
    row_lines = lines[separator_idx + 1 :]
    rows = []
    for row_idx, line in enumerate(row_lines):
        if line.strip():
            cleaned = line.replace("_", "").strip()
            if cleaned:
                # Parse by finding decimal placement so result < 90, max 2 digits before decimal
                coord = parse_coordinate_from_digits(cleaned, 90.0, 2)
                if coord is not None:
                    # Keep base coordinate positive, signs will be applied later
                    rows.append((cleaned, abs(coord)))
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

    # Store all points for map visualization
    all_points = []

    for idx in range(num_pairs):
        row_str, row_val = rows[idx]
        col_str, col_val = columns[idx]

        # Apply signs from offsets file
        # Row sign determines latitude sign, column sign determines longitude sign
        lat_sign = row_signs[idx] if idx < len(row_signs) else 1
        lon_sign = column_signs[idx] if idx < len(column_signs) else 1

        # Calculate final coordinates with applied signs
        lat_val = row_val * lat_sign
        lon_val = col_val * lon_sign

        # Determine direction strings
        lat_dir = "N" if lat_val >= 0 else "S"
        lon_dir = "E" if lon_val >= 0 else "W"
        sign_combo = ("+" if lat_sign > 0 else "-") + ("+" if lon_sign > 0 else "-")

        # Validate coordinates
        if abs(lat_val) > 90 or abs(lon_val) > 180:
            print(f"Pair {idx + 1} (row={row_str}, col={col_str}):")
            print(
                f"  Warning: Coordinates ({lat_val:.6f}, {lon_val:.6f}) are out of valid range"
            )
            print()
            continue

        tz_name = tf.timezone_at(lat=lat_val, lng=lon_val)

        # Get location name (commented out for now)
        # location_name = get_location_name(lat_val, lon_val)

        # Convert to DMS format
        lat_d, lat_m, lat_s = decimal_to_dms(abs(lat_val))
        lon_d, lon_m, lon_s = decimal_to_dms(abs(lon_val))

        print(f"Pair {idx + 1} (row={row_str}, col={col_str}):")
        print(
            f"  Coordinates: {format_dms(lat_d, lat_m, lat_s)} {lat_dir}, {format_dms(lon_d, lon_m, lon_s)} {lon_dir}"
        )
        print(f"    (Decimal: {lat_val:+.6f}, {lon_val:+.6f})")
        print(f"    Sign combination: {sign_combo}")

        if tz_name:
            if pytz_available:
                tz = pytz.timezone(tz_name)
                now = datetime.now(tz)
                offset_seconds = now.utcoffset().total_seconds()
                offset_hours = offset_seconds / 3600.0
                print(f"    Timezone: {tz_name}")
                print(f"    GMT Offset: {offset_hours:+.2f} hours")

                # Store point for map
                all_points.append(
                    {
                        "lat": lat_val,
                        "lon": lon_val,
                        "pair": idx + 1,
                        "combo": sign_combo,
                        "timezone": tz_name,
                        "offset": offset_hours,
                        "dms": f"{format_dms(lat_d, lat_m, lat_s)} {lat_dir}, {format_dms(lon_d, lon_m, lon_s)} {lon_dir}",
                    }
                )
            else:
                print(f"    Timezone: {tz_name}")
                print(f"    GMT Offset: (pytz not available to calculate)")

                # Store point for map
                all_points.append(
                    {
                        "lat": lat_val,
                        "lon": lon_val,
                        "pair": idx + 1,
                        "combo": sign_combo,
                        "timezone": tz_name,
                        "offset": None,
                        "dms": f"{format_dms(lat_d, lat_m, lat_s)} {lat_dir}, {format_dms(lon_d, lon_m, lon_s)} {lon_dir}",
                    }
                )
        else:
            print(f"    Timezone: Not found")
        print()

    # Create world map with all points
    if folium_available and all_points:
        print("Creating world map visualization...")
        create_world_map(all_points)
    elif not folium_available:
        print("Note: Install folium to generate map visualization: pip install folium")


if __name__ == "__main__":
    main()
