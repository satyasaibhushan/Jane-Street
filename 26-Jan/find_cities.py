#!/usr/bin/env python3
"""
Find top 3 cities/regions near each coordinate point and display on map.
"""

import sys
from typing import List, Tuple, Dict
from timezonefinder import TimezoneFinder
import pytz
from datetime import datetime
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import time

def parse_coordinate_from_digits(
    digit_string: str, max_value: float, max_digits_before_decimal: int
) -> float:
    """Parse coordinate from a string of digits assuming DMS format."""
    if not digit_string:
        return None

    num_len = len(digit_string)

    # For rows: DDMMSS format (2 digits degrees, 2 digits minutes, 2 digits seconds)
    if max_digits_before_decimal == 2:
        if num_len >= 6:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:6])
            if num_len > 6:
                fraction = int(digit_string[6:]) / (10 ** (num_len - 6))
                seconds += fraction
        elif num_len == 5:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:5])
        elif num_len == 4:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = 0
        elif num_len == 3:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:3])
            seconds = 0
        else:
            degrees = int(digit_string)
            minutes = 0
            seconds = 0

        if minutes >= 60 or seconds >= 60:
            return None

        decimal_degrees = degrees + minutes / 60.0 + seconds / 3600.0
        return decimal_degrees

    # For columns: DDDMMSS format
    elif max_digits_before_decimal == 3:
        best_result = None

        if num_len >= 7:
            degrees = int(digit_string[:3])
            minutes = int(digit_string[3:5])
            seconds = int(digit_string[5:7])
            if degrees < 180 and minutes < 60 and seconds < 60:
                fraction = 0
                if num_len > 7:
                    fraction = int(digit_string[7:]) / (10 ** (num_len - 7))
                best_result = degrees + minutes / 60.0 + (seconds + fraction) / 3600.0

        if best_result is None and num_len >= 6:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:6])
            if degrees < 180 and minutes < 60 and seconds < 60:
                fraction = 0
                if num_len > 6:
                    fraction = int(digit_string[6:]) / (10 ** (num_len - 6))
                best_result = degrees + minutes / 60.0 + (seconds + fraction) / 3600.0

        if best_result is not None:
            return best_result

        if num_len == 6:
            degrees = int(digit_string[:2])
            minutes = int(digit_string[2:4])
            seconds = int(digit_string[4:6])
            if degrees < 180 and minutes < 60 and seconds < 60:
                return degrees + minutes / 60.0 + seconds / 3600.0

    return None


def get_timezone(lat: float, lon: float) -> Tuple[str, float]:
    """Get timezone name and GMT offset for given coordinates."""
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)

    if tz_name:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        offset_seconds = now.utcoffset().total_seconds()
        offset_hours = offset_seconds / 3600.0
        return tz_name, offset_hours
    return None, None


def find_cities_along_line(fixed_coord: float, is_latitude: bool, num_points: int = 10) -> List[Dict]:
    """Find cities along a latitude or longitude line.
    
    Args:
        fixed_coord: The fixed latitude or longitude value
        is_latitude: True if fixed_coord is latitude (search along longitude), False if longitude (search along latitude)
        num_points: Number of points to sample along the line
    """
    geolocator = Nominatim(user_agent="city_finder")
    cities = []
    seen_cities = set()

    try:
        if is_latitude:
            # Search along longitude (latitude is fixed)
            # Sample points from -180 to 180 longitude, focusing on populated areas
            # Skip ocean areas by sampling more densely in mid-latitudes
            sample_lons = []
            # Create strategic sampling: more points in populated regions
            for i in range(num_points):
                lon = -180 + (360 * i / (num_points - 1))
                if abs(lon) > 180:
                    lon = 180 if lon > 180 else -180
                sample_lons.append(lon)
            
            print(f"    Sampling {len(sample_lons)} points...", end="", flush=True)
            
            for i, lon in enumerate(sample_lons):
                try:
                    location = geolocator.reverse((fixed_coord, lon), timeout=5, exactly_one=True)
                    if location:
                        address = location.raw.get("address", {})
                        city_name = (
                            address.get("city")
                            or address.get("town")
                            or address.get("village")
                            or address.get("municipality")
                            or address.get("county")
                            or address.get("state")
                            or address.get("country")
                        )
                        if city_name and city_name not in seen_cities:
                            seen_cities.add(city_name)
                            city_lat = location.latitude
                            city_lon = location.longitude
                            # Distance from the line (for latitude line, measure longitude difference)
                            lon_diff = abs(city_lon - lon)
                            if lon_diff > 180:
                                lon_diff = 360 - lon_diff
                            distance = lon_diff * 111.0 * abs(fixed_coord / 90.0) if abs(fixed_coord) < 90 else lon_diff * 111.0
                            tz_name, offset = get_timezone(city_lat, city_lon)
                            cities.append({
                                "name": city_name,
                                "lat": city_lat,
                                "lon": city_lon,
                                "distance": distance,
                                "timezone": tz_name,
                                "offset": offset,
                                "address": location.address
                            })
                except Exception as e:
                    pass
                
                print(".", end="", flush=True)
                time.sleep(0.5)  # Be respectful to API
            print()  # New line after progress dots
        else:
            # Search along latitude (longitude is fixed)
            # Sample points from -90 to 90 latitude
            sample_lats = []
            for i in range(num_points):
                lat = -90 + (180 * i / (num_points - 1))
                if abs(lat) > 90:
                    lat = 90 if lat > 90 else -90
                sample_lats.append(lat)
            
            print(f"    Sampling {len(sample_lats)} points...", end="", flush=True)
            
            for i, lat in enumerate(sample_lats):
                try:
                    location = geolocator.reverse((lat, fixed_coord), timeout=5, exactly_one=True)
                    if location:
                        address = location.raw.get("address", {})
                        city_name = (
                            address.get("city")
                            or address.get("town")
                            or address.get("village")
                            or address.get("municipality")
                            or address.get("county")
                            or address.get("state")
                            or address.get("country")
                        )
                        if city_name and city_name not in seen_cities:
                            seen_cities.add(city_name)
                            city_lat = location.latitude
                            city_lon = location.longitude
                            # Distance from the line (for longitude line, measure latitude difference)
                            distance = abs(city_lat - lat) * 111.0
                            tz_name, offset = get_timezone(city_lat, city_lon)
                            cities.append({
                                "name": city_name,
                                "lat": city_lat,
                                "lon": city_lon,
                                "distance": distance,
                                "timezone": tz_name,
                                "offset": offset,
                                "address": location.address
                            })
                except Exception as e:
                    pass
                
                print(".", end="", flush=True)
                time.sleep(0.5)  # Be respectful to API
            print()  # New line after progress dots

    except Exception as e:
        print(f"\n  Error finding cities: {e}")

    # Sort by distance and return top 3
    cities.sort(key=lambda x: x["distance"])
    return cities[:3]


def main():
    # Read data file
    try:
        with open("data.txt", "r") as f:
            lines = [line.rstrip("\n") for line in f.readlines()]
    except FileNotFoundError:
        print("Error: data.txt not found")
        return

    # Find separator
    separator_idx = None
    for i, line in enumerate(lines):
        if not line.strip():
            separator_idx = i
            break

    if separator_idx is None:
        print("Error: Could not find separator")
        return

    # Extract columns
    column_lines = lines[:separator_idx]
    cleaned_column_lines = []
    for line in column_lines:
        cleaned = line.replace("_", "").strip()
        if cleaned:
            cleaned_column_lines.append(cleaned)

    # Read offsets
    column_signs = []
    row_signs = []
    try:
        with open("offests.txt", "r") as f:
            offset_lines = [line.strip() for line in f.readlines() if line.strip()]
        if len(offset_lines) >= 1:
            column_signs = [-1 if c == "+" else 1 for c in offset_lines[0]]
        if len(offset_lines) >= 2:
            row_signs = [-1 if c == "+" else 1 for c in offset_lines[1]]
    except FileNotFoundError:
        print("Warning: offests.txt not found")

    # Extract columns - get all 12 columns
    columns = []
    for col_idx in range(12):
        col_digits = []
        for cleaned_line in cleaned_column_lines:
            if col_idx < len(cleaned_line):
                col_digits.append(cleaned_line[col_idx])
        if col_digits:
            digit_string = "".join(col_digits)
            coord = parse_coordinate_from_digits(digit_string, 180.0, 3)
            if coord is not None:
                columns.append((digit_string, abs(coord)))
            else:
                # Even if parsing fails, keep the column with a placeholder
                # Try to extract a reasonable coordinate value
                # Use last 2 digits as seconds, next 2 as minutes, rest as degrees
                if len(digit_string) >= 4:
                    try:
                        seconds = int(digit_string[-2:])
                        minutes = int(digit_string[-4:-2])
                        degrees = int(digit_string[:-4]) if len(digit_string) > 4 else 0
                        # Normalize if seconds >= 60
                        if seconds >= 60:
                            minutes += seconds // 60
                            seconds = seconds % 60
                        # Normalize if minutes >= 60
                        if minutes >= 60:
                            degrees += minutes // 60
                            minutes = minutes % 60
                        # Cap degrees at 180
                        if degrees > 180:
                            degrees = degrees % 180
                        coord = degrees + minutes/60.0 + seconds/3600.0
                        columns.append((digit_string, abs(coord)))
                    except:
                        # If all else fails, use a default value
                        columns.append((digit_string, 0.0))
                else:
                    columns.append((digit_string, 0.0))

    # Extract rows - get all 12 rows
    row_lines = lines[separator_idx + 1 :]
    rows = []
    for row_idx, line in enumerate(row_lines):
        if line.strip():
            cleaned = line.replace("_", "").strip()
            if cleaned:
                coord = parse_coordinate_from_digits(cleaned, 90.0, 2)
                if coord is not None:
                    rows.append((cleaned, abs(coord)))
                else:
                    # Even if parsing fails, keep the row with a placeholder
                    # Try to extract a reasonable coordinate value
                    if len(cleaned) >= 4:
                        try:
                            seconds = int(cleaned[-2:])
                            minutes = int(cleaned[-4:-2])
                            degrees = int(cleaned[:-4]) if len(cleaned) > 4 else 0
                            # Normalize if seconds >= 60
                            if seconds >= 60:
                                minutes += seconds // 60
                                seconds = seconds % 60
                            # Normalize if minutes >= 60
                            if minutes >= 60:
                                degrees += minutes // 60
                                minutes = minutes % 60
                            # Cap degrees at 90
                            if degrees > 90:
                                degrees = degrees % 90
                            coord = degrees + minutes/60.0 + seconds/3600.0
                            rows.append((cleaned, abs(coord)))
                        except:
                            rows.append((cleaned, 0.0))
                    else:
                        rows.append((cleaned, 0.0))
    # Ensure we have exactly 12 rows
    while len(rows) < 12:
        rows.append(("000000", 0.0))
    rows = rows[:12]
    
    # Ensure we have exactly 12 columns
    while len(columns) < 12:
        columns.append(("0000000", 0.0))
    columns = columns[:12]

    print(f"Found {len(columns)} columns and {len(rows)} rows\n")
    print("=" * 80)

    all_sections_data = []

    # Process latitude lines (from rows)
    print("\n=== LATITUDE LINES (from rows) ===\n")
    for idx, (row_str, row_val) in enumerate(rows):
        # Apply row sign
        lat_sign = row_signs[idx] if idx < len(row_signs) else 1
        lat_val = row_val * lat_sign

        if abs(lat_val) > 90:
            print(f"Latitude Line {idx + 1} (row={row_str}): {lat_val:+.6f}° (INVALID - skipping)")
            print()
            continue

        print(f"Latitude Line {idx + 1} (row={row_str}): {lat_val:+.6f}°")
        print(f"  Finding cities along this latitude...")

        # Find cities along this latitude line
        cities = find_cities_along_line(lat_val, is_latitude=True, num_points=20)
        
        if cities:
            print(f"  Top {len(cities)} cities/regions:")
            for i, city in enumerate(cities, 1):
                print(f"    {i}. {city['name']}")
                print(f"       Distance from line: {city['distance']:.2f} km")
                print(f"       Timezone: {city['timezone']}")
                if city['offset'] is not None:
                    print(f"       GMT Offset: {city['offset']:+.2f} hours")
                print(f"       Location: ({city['lat']:.6f}, {city['lon']:.6f})")
            
            all_sections_data.append({
                "type": "latitude",
                "index": idx + 1,
                "fixed_coord": lat_val,
                "label": f"Lat {idx + 1} ({lat_val:+.2f}°)",
                "cities": cities
            })
        else:
            print(f"  No cities found")
        print()

    # Process longitude lines (from columns)
    print("\n=== LONGITUDE LINES (from columns) ===\n")
    for idx, (col_str, col_val) in enumerate(columns):
        # Apply column sign
        lon_sign = column_signs[idx] if idx < len(column_signs) else 1
        lon_val = col_val * lon_sign

        if abs(lon_val) > 180:
            print(f"Longitude Line {idx + 1} (col={col_str}): {lon_val:+.6f}° (INVALID - skipping)")
            print()
            continue

        print(f"Longitude Line {idx + 1} (col={col_str}): {lon_val:+.6f}°")
        print(f"  Finding cities along this longitude...")

        # Find cities along this longitude line
        cities = find_cities_along_line(lon_val, is_latitude=False, num_points=20)
        
        if cities:
            print(f"  Top {len(cities)} cities/regions:")
            for i, city in enumerate(cities, 1):
                print(f"    {i}. {city['name']}")
                print(f"       Distance from line: {city['distance']:.2f} km")
                print(f"       Timezone: {city['timezone']}")
                if city['offset'] is not None:
                    print(f"       GMT Offset: {city['offset']:+.2f} hours")
                print(f"       Location: ({city['lat']:.6f}, {city['lon']:.6f})")
            
            all_sections_data.append({
                "type": "longitude",
                "index": idx + 1,
                "fixed_coord": lon_val,
                "label": f"Lon {idx + 1} ({lon_val:+.2f}°)",
                "cities": cities
            })
        else:
            print(f"  No cities found")
        print()

    # Create map
    if all_sections_data:
        print("\nCreating map visualization...")
        
        # Calculate center from all cities
        all_lats = []
        all_lons = []
        for data in all_sections_data:
            for city in data["cities"]:
                all_lats.append(city["lat"])
                all_lons.append(city["lon"])
        
        if all_lats and all_lons:
            avg_lat = sum(all_lats) / len(all_lats)
            avg_lon = sum(all_lons) / len(all_lons)
        else:
            avg_lat, avg_lon = 0, 0

        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=2)

        # Color scheme for latitude lines (red tones) and longitude lines (blue tones)
        lat_colors = ['red', 'darkred', 'crimson', 'firebrick', 'indianred', 'lightcoral', 
                      'salmon', 'tomato', 'orangered', 'chocolate', 'sienna', 'maroon']
        lon_colors = ['blue', 'darkblue', 'navy', 'mediumblue', 'royalblue', 'steelblue',
                      'cornflowerblue', 'skyblue', 'lightblue', 'dodgerblue', 'deepskyblue', 'cyan']

        for data in all_sections_data:
            section_type = data["type"]
            index = data["index"]
            fixed_coord = data["fixed_coord"]
            label = data["label"]
            cities = data["cities"]
            
            if section_type == "latitude":
                color = lat_colors[(index - 1) % len(lat_colors)]
                # Draw latitude line
                line_coords = [[fixed_coord, -180], [fixed_coord, 180]]
                folium.PolyLine(
                    line_coords,
                    color=color,
                    weight=2,
                    opacity=0.5,
                    popup=f"Latitude Line {index}: {fixed_coord:+.6f}°"
                ).add_to(m)
            else:  # longitude
                color = lon_colors[(index - 1) % len(lon_colors)]
                # Draw longitude line
                line_coords = [[-90, fixed_coord], [90, fixed_coord]]
                folium.PolyLine(
                    line_coords,
                    color=color,
                    weight=2,
                    opacity=0.5,
                    popup=f"Longitude Line {index}: {fixed_coord:+.6f}°"
                ).add_to(m)

            # Mark each city
            for i, city in enumerate(cities):
                marker_color = 'darkgreen' if i == 0 else 'green' if i == 1 else 'lightgreen'
                popup_text = f"""
                <b>{city['name']}</b><br>
                {label}, Rank {i+1}<br>
                Distance from line: {city['distance']:.2f} km<br>
                Timezone: {city['timezone']}<br>
                GMT Offset: {city['offset']:+.2f} hours<br>
                Coordinates: ({city['lat']:.6f}, {city['lon']:.6f})
                """
                
                folium.Marker(
                    location=[city['lat'], city['lon']],
                    popup=folium.Popup(popup_text, max_width=300),
                    icon=folium.Icon(color=marker_color, icon='info-sign'),
                    tooltip=f"{label}: {city['name']} ({city['timezone']})"
                ).add_to(m)

        # Add legend
        legend_html = """
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 250px; height: 200px; 
                    background-color: white; z-index:9999; font-size:14px;
                    border:2px solid grey; border-radius:5px; padding: 10px">
        <p><b>Legend</b></p>
        <p><b>Latitude Lines:</b></p>
        <p style="color:red">━━━ Red lines (from rows)</p>
        <p><b>Longitude Lines:</b></p>
        <p style="color:blue">━━━ Blue lines (from columns)</p>
        <p><b>Cities:</b></p>
        <p>🟢 Dark Green = Rank 1</p>
        <p>🟢 Green = Rank 2</p>
        <p>🟢 Light Green = Rank 3</p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        # Save map
        output_file = "cities_map.html"
        m.save(output_file)
        print(f"Map saved to: {output_file}")
        print(f"Open {output_file} in your web browser to view the map")
        print(f"\nTotal sections: {len(all_sections_data)} (12 latitude + {len(columns)} longitude lines)")


if __name__ == "__main__":
    main()
