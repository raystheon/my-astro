# -*- coding: utf-8 -*-
"""Magi Astrology Calculator (astro_calculator.py) - Flask Web Service Edition

This script calculates planetary positions, natal aspects, and inter-chart linkages,
and exposes the results via a simple Flask web service endpoint.
"""

import ephem
import datetime
import pandas as pd
from skyfield.api import load, Topos
from flask import Flask
import os
import io

# --- FLASK APP SETUP ---
app = Flask(__name__)

# --- USER INPUT DATA (Hardcoded for this example) ---
person1_data = {
    'name': 'Madonna',
    'date': '1958-08-16',
    'time': '00:00',
    'latitude': 42.65,
    'longitude': -83.89,
    'timezone_offset': -5
}

person2_data = {
    'name': 'Sean Penn',
    'date': '1960-08-17',
    'time': '00:00',
    'latitude': 34.05,
    'longitude': -118.24,
    'timezone_offset': -7
}

# --- Ephemeris and Setup ---
# Setup ephemeris paths for skyfield (Chiron) and pyephem (standard planets)
EPHEM_DIR = 'skyfield-data'
EPHEM_FILE = 'de421.bsp'
EPHEM_PATH = os.path.join(EPHEM_DIR, EPHEM_FILE)

# Ensure pyephem is correctly initialized with the current date/time
observer = ephem.Observer()

# Initialize skyfield ephemeris for Chiron
# This path is relative to the container's working directory /app
try:
    eph = load(EPHEM_PATH)
    ts = load.timescale()
    # Define Chiron position using skyfield
    chiron_skyfield = eph['chiron']
except Exception as e:
    # Handle error gracefully if ephemeris download failed during build
    print(f"Error loading skyfield ephemeris: {e}")
    eph, ts, chiron_skyfield = None, None, None

# --- CONSTANTS ---
PLANETS = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron']
# Magi Astrology Aspect Orbs (in degrees)
ORBS = {
    'Major_Natal': 3.0,
    'Minor_Natal': 1.0,
    'Major_Synastry': 1.0, # Often tighter orbs for synastry
    'Minor_Synastry': 0.5
}
# Standard Magi Aspects (Hard = 0, 90, 180; Soft = 30, 60, 120, 150)
ASPECTS = {
    0: {'name': 'Conjunction', 'type': 'Hard', 'symbol': '☌'},
    30: {'name': 'Semi-Sextile', 'type': 'Soft', 'symbol': '⚹'},
    60: {'name': 'Sextile', 'type': 'Soft', 'symbol': '⚹'},
    90: {'name': 'Square', 'type': 'Hard', 'symbol': '□'},
    120: {'name': 'Trine', 'type': 'Soft', 'symbol': '△'},
    150: {'name': 'Quincunx', 'type': 'Soft', 'symbol': '⚻'},
    180: {'name': 'Opposition', 'type': 'Hard', 'symbol': '☍'}
}

# --- CORE FUNCTIONS ---

def get_pyephem_body(planet_name):
    """Returns the pyephem object for a given planet name."""
    if planet_name == 'Sun': return ephem.Sun()
    if planet_name == 'Moon': return ephem.Moon()
    if planet_name == 'Mercury': return ephem.Mercury()
    if planet_name == 'Venus': return ephem.Venus()
    if planet_name == 'Mars': return ephem.Mars()
    if planet_name == 'Jupiter': return ephem.Jupiter()
    if planet_name == 'Saturn': return ephem.Saturn()
    if planet_name == 'Uranus': return ephem.Uranus()
    if planet_name == 'Neptune': return ephem.Neptune()
    if planet_name == 'Pluto': return ephem.Pluto()
    return None

def calculate_positions(person_data):
    """Calculates geocentric longitude, position, and retrograde status for all planets."""
    positions = {}
    
    # Set observer location and time for pyephem
    observer.lat = str(person_data['latitude'])
    observer.lon = str(person_data['longitude'])
    
    # Calculate UTC time
    dt_local = datetime.datetime.strptime(f"{person_data['date']} {person_data['time']}", '%Y-%m-%d %H:%M')
    dt_utc = dt_local - datetime.timedelta(hours=person_data['timezone_offset'])
    observer.date = dt_utc.strftime('%Y/%m/%d %H:%M:%S')

    # Get pyephem positions
    for p_name in PLANETS:
        if p_name == 'Chiron':
            if eph and chiron_skyfield:
                # Skyfield requires its own time object
                t = ts.utc(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour, dt_utc.minute, dt_utc.second)
                astrometric = observer.at(t).observe(chiron_skyfield)
                long_deg = astrometric.apparent().lon.degrees
            else:
                long_deg = 0
                print(f"Warning: Chiron skipped for {person_data['name']} due to ephemeris error.")
        else:
            body = get_pyephem_body(p_name)
            if body:
                body.compute(observer)
                long_deg = body.hlong * 180 / ephem.pi # Geocentric Apparent Longitude

                # Determine Retrograde (Rx) status
                # Calculate position 1 hour later
                future_date = dt_utc + datetime.timedelta(hours=1)
                observer_future = ephem.Observer()
                observer_future.lat = str(person_data['latitude'])
                observer_future.lon = str(person_data['longitude'])
                observer_future.date = future_date.strftime('%Y/%m/%d %H:%M:%S')
                body_future = get_pyephem_body(p_name)
                body_future.compute(observer_future)

                current_long = body.hlong * 180 / ephem.pi
                future_long = body_future.hlong * 180 / ephem.pi

                # Handle 0/360 boundary crossing for longitude check
                diff = future_long - current_long
                if diff < -180:
                    diff += 360
                elif diff > 180:
                    diff -= 360

                is_retrograde = diff < 0
            else:
                continue

        positions[p_name] = {
            'longitude': long_deg,
            'is_retrograde': is_retrograde if p_name != 'Chiron' and p_name not in ['Sun', 'Moon'] else False,
            'Rx_symbol': 'Rx' if p_name not in ['Sun', 'Moon'] and is_retrograde else ''
        }
    return positions

def calculate_aspects(positions1, positions2=None):
    """
    Calculates aspects either within one chart (natal) or between two charts (synastry).
    positions1: Dictionary of planet longitudes for chart 1.
    positions2: Optional. Dictionary of planet longitudes for chart 2 (for synastry).
    """
    aspects_list = []
    
    # Determine the mode and orb type
    if positions2 is None:
        # Natal Mode (Intra-chart)
        mode = 'natal'
        planets1 = list(positions1.keys())
        planets2 = list(positions1.keys()) # Compare all pairs in one chart
        orb_type = 'Major_Natal' # Using only Major orb for simplicity
    else:
        # Synastry Mode (Inter-chart)
        mode = 'synastry'
        planets1 = list(positions1.keys())
        planets2 = list(positions2.keys())
        orb_type = 'Major_Synastry' # Using only Major Synastry orb

    orb = ORBS[orb_type]

    # Iterate through all unique pairs of planets
    for i, p1 in enumerate(planets1):
        for j, p2 in enumerate(planets2):
            if mode == 'natal' and i >= j: # Avoid duplicate pairs and self-comparison for natal
                continue
            
            long1 = positions1[p1]['longitude']
            long2 = positions2[p2]['longitude'] if positions2 else positions1[p2]['longitude']
            
            # Calculate difference (absolute difference is 0 to 180)
            diff = abs(long1 - long2)
            diff = min(diff, 360 - diff)

            # Check for aspect match
            for target_angle, aspect_data in ASPECTS.items():
                actual_angle_diff = abs(diff - target_angle)
                
                if actual_angle_diff <= orb:
                    aspect = {
                        'angle': target_angle,
                        'aspect_name': aspect_data['name'],
                        'aspect_type': aspect_data['type'],
                        'symbol': aspect_data['symbol'],
                        'orb': orb,
                        'actual_angle_diff': actual_angle_diff,
                        'chart1_planet': p1,
                        'chart2_planet': p2,
                        'aspect_dimension': 'H' if aspect_data['type'] == 'Hard' else 'S'
                    }
                    aspects_list.append(aspect)

    # Sort aspects by angle, then by planet name for consistency
    aspects_list.sort(key=lambda x: (x['angle'], x['chart1_planet'], x['chart2_planet']))
    return aspects_list

# --- WEB SERVICE ROUTE ---

@app.route("/")
@app.route("/run")
def calculate_astrology():
    # Capture the output in a buffer since the original script used print()
    buffer = io.StringIO()
    
    # Calculate positions
    positions1 = calculate_positions(person1_data)
    positions2 = calculate_positions(person2_data)

    buffer.write(f"--- Magi Astrology Report ---\n")
    buffer.write(f"Chart 1: {person1_data['name']} ({person1_data['date']})\n")
    buffer.write(f"Chart 2: {person2_data['name']} ({person2_data['date']})\n")
    buffer.write("--------------------------\n")

    # Display positions and Rx status
    def display_positions(data, positions):
        buffer.write(f"\nPlanetary Positions for {data['name']}:\n")
        for p, pos in positions.items():
            buffer.write(f"  {p:<10}: {pos['longitude']:>7.3f}° {pos['Rx_symbol']}\n")

    display_positions(person1_data, positions1)
    display_positions(person2_data, positions2)

    # Calculate and display Natal Aspects
    def display_natal_aspects(data, positions):
        natal_aspects = calculate_aspects(positions)
        buffer.write(f"\nNatal Aspects for {data['name']} (Orb: {ORBS['Major_Natal']}°):\n")
        if natal_aspects:
            for aspect in natal_aspects:
                 buffer.write(f"  {aspect['chart1_planet']:<10} {aspect['symbol']} {aspect['chart2_planet']:<10} ({aspect['aspect_name']}, {aspect['aspect_type']}, Orb: {aspect['actual_angle_diff']:.2f}°) [{aspect['aspect_dimension']}]\n")
        else:
            buffer.write("  No natal aspects found within the defined orbs.\n")

    display_natal_aspects(person1_data, positions1)
    display_natal_aspects(person2_data, positions2)

    # Calculate and display Synastry Aspects
    synastry_aspects = calculate_aspects(positions1, positions2)
    buffer.write(f"\nSynastry Aspects between {person1_data['name']} and {person2_data['name']} (Orb: {ORBS['Major_Synastry']}°):\n")
    if synastry_aspects:
        for aspect in synastry_aspects:
             buffer.write(f"  {person1_data['name']}'s {aspect['chart1_planet']:<10} {aspect['symbol']} {person2_data['name']}'s {aspect['chart2_planet']:<10} ({aspect['aspect_name']}, {aspect['aspect_type']}, Orb: {aspect['actual_angle_diff']:.2f}°) [{aspect['aspect_dimension']}]\n")
    else:
        buffer.write("  No synastry aspects found within the defined orbs.\n")
    
    # Return the entire report string
    return buffer.getvalue(), 200

if __name__ == '__main__':
    # This block is for local testing and will be ignored by the Flask CMD in Docker
    # The CMD instruction uses 'flask run', which handles starting the server.
    pass
