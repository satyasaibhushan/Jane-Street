#!/usr/bin/env python3
"""
Plot locations from Regions.txt on a world map with timezone information.
"""

import sys
from typing import List, Dict, Tuple
from timezonefinder import TimezoneFinder
import pytz
from datetime import datetime
import folium

try:
    import folium
    folium_available = True
except ImportError:
    folium_available = False
    print("Warning: folium not available. Install with: pip install folium", file=sys.stderr)

try:
    import pytz
    pytz_available = True
except ImportError:
    pytz_available = False
    print("Warning: pytz not available. Install with: pip install pytz", file=sys.stderr)


def decimal_to_dms(decimal_degrees: float) -> Tuple[int, int, float]:
    """Convert decimal degrees to degrees, minutes, seconds."""
    degrees = int(decimal_degrees)
    minutes_float = abs(decimal_degrees - degrees) * 60.0
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60.0
    return (degrees, minutes, seconds)


def format_dms(degrees: int, minutes: int, seconds: float) -> str:
    """Format degrees, minutes, seconds as a string."""
    return f"{degrees}° {minutes}' {seconds:.2f}\""


def get_timezone(lat: float, lon: float) -> Tuple[str, float]:
    """Get timezone name and GMT offset for given coordinates."""
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)

    if tz_name and pytz_available:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        offset_seconds = now.utcoffset().total_seconds()
        offset_hours = offset_seconds / 3600.0
        return tz_name, offset_hours
    elif tz_name:
        return tz_name, None
    return None, None


def parse_coordinate(coord_str: str) -> float:
    """Parse coordinate string - can be decimal degrees or DMS format."""
    coord_str = coord_str.strip()
    
    # Try as decimal degrees first
    try:
        return float(coord_str)
    except ValueError:
        pass
    
    # Try DMS format (e.g., "32° 45' 6\"")
    try:
        # Remove degree, minute, second symbols and split
        parts = coord_str.replace("°", " ").replace("'", " ").replace("\"", " ").split()
        if len(parts) >= 1:
            degrees = float(parts[0])
            minutes = float(parts[1]) if len(parts) > 1 else 0
            seconds = float(parts[2]) if len(parts) > 2 else 0
            return degrees + minutes/60.0 + seconds/3600.0
    except:
        pass
    
    return None


def main():
    # Read Regions.txt
    try:
        with open("Regions.txt", "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        print("Error: Regions.txt not found")
        return

    if not lines:
        print("Error: Regions.txt is empty")
        return

    print(f"Reading {len(lines)} locations from Regions.txt...")
    print("=" * 80)

    locations = []
    all_lats = []
    all_lons = []

    # Parse each line - assume format: name, latitude, longitude (or similar)
    for idx, line in enumerate(lines, 1):
        parts = [p.strip() for p in line.split(",") if p.strip()]
        
        if len(parts) < 3:
            # Try tab or other separators
            parts = [p.strip() for p in line.split("\t") if p.strip()]
        
        if len(parts) >= 3:
            name = parts[0]
            lat_str = parts[1]
            lon_str = parts[2]
            
            lat = parse_coordinate(lat_str)
            lon = parse_coordinate(lon_str)
            
            if lat is not None and lon is not None:
                if abs(lat) <= 90 and abs(lon) <= 180:
                    tz_name, offset = get_timezone(lat, lon)
                    
                    lat_d, lat_m, lat_s = decimal_to_dms(abs(lat))
                    lon_d, lon_m, lon_s = decimal_to_dms(abs(lon))
                    lat_dir = "N" if lat >= 0 else "S"
                    lon_dir = "E" if lon >= 0 else "W"
                    
                    locations.append({
                        "name": name,
                        "lat": lat,
                        "lon": lon,
                        "timezone": tz_name,
                        "offset": offset,
                        "dms": f"{format_dms(lat_d, lat_m, lat_s)} {lat_dir}, {format_dms(lon_d, lon_m, lon_s)} {lon_dir}"
                    })
                    
                    all_lats.append(lat)
                    all_lons.append(lon)
                    
                    print(f"{idx}. {name}")
                    print(f"   Coordinates: {format_dms(lat_d, lat_m, lat_s)} {lat_dir}, {format_dms(lon_d, lon_m, lon_s)} {lon_dir}")
                    print(f"   (Decimal: {lat:.6f}, {lon:.6f})")
                    if tz_name:
                        print(f"   Timezone: {tz_name}")
                        if offset is not None:
                            print(f"   GMT Offset: {offset:+.2f} hours")
                    print()
                else:
                    print(f"{idx}. {name} - Invalid coordinates: ({lat}, {lon})")
                    print()
            else:
                print(f"{idx}. {name} - Could not parse coordinates: {lat_str}, {lon_str}")
                print()
        else:
            print(f"{idx}. Line format unclear: {line}")
            print()

    if not locations:
        print("No valid locations found to plot")
        return

    # Create map
    if folium_available:
        print("Creating map visualization...")
        
        # Calculate center
        avg_lat = sum(all_lats) / len(all_lats)
        avg_lon = sum(all_lons) / len(all_lons)

        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=2)

        # Color scheme
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 
                  'beige', 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple',
                  'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'white',
                  'lightgray', 'darkgray', 'yellow', 'cyan', 'magenta', 'lime']

        # Add markers for each location
        for i, loc in enumerate(locations):
            color = colors[i % len(colors)]
            
            popup_text = f"""
            <b>{loc['name']}</b><br>
            Coordinates: {loc['dms']}<br>
            Decimal: ({loc['lat']:.6f}, {loc['lon']:.6f})<br>
            """
            if loc['timezone']:
                popup_text += f"Timezone: {loc['timezone']}<br>"
                if loc['offset'] is not None:
                    popup_text += f"GMT Offset: {loc['offset']:+.2f} hours"
                else:
                    popup_text += "GMT Offset: N/A"
            else:
                popup_text += "Timezone: Not found"

            folium.CircleMarker(
                location=[loc['lat'], loc['lon']],
                radius=10,
                popup=folium.Popup(popup_text, max_width=300),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                weight=2,
                tooltip=f"{loc['name']} ({loc['timezone'] or 'No timezone'})"
            ).add_to(m)

        # Save map
        output_file = "regions_map.html"
        m.save(output_file)
        print(f"Map saved to: {output_file}")
        print(f"Open {output_file} in your web browser to view the map")
        print(f"\nTotal locations plotted: {len(locations)}")
    else:
        print("Note: Install folium to generate map visualization: pip install folium")


if __name__ == "__main__":
    main()
