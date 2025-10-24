import os
import json
from flask import Flask, request, jsonify
from skyfield.api import load, EarthSatellite, Topos
from skyfield.timelib import Time
from skyfield.framelib import itrs

# --- Configuration ---
# Cloud Run sets the PORT environment variable. We default to 8080 for local testing.
PORT = int(os.environ.get('PORT', 8080))

# The path where the Dockerfile downloaded the ephemeris file. 
# CRITICAL FIX: The path is now simplified to the root working directory /app.
EPHEMERIS_PATH = 'de430.bsp' 

# --- App Initialization ---
app = Flask(__name__)

# Load the ephemeris (planetary data) once when the service starts
# This uses the data file we downloaded in the Dockerfile.
try:
    ts = load.timescale()
    planets = load(EPHEMERIS_PATH)
    earth = planets['earth']
    moon = planets['moon']
    app.logger.info(f"Skyfield ephemeris loaded successfully from {EPHEMERIS_PATH}")
except Exception as e:
    # Log the failure for troubleshooting, and set 'planets' to None to signal an error state
    app.logger.error(f"FATAL ERROR: Could not load Skyfield data. Check Dockerfile and path. Error: {e}")
    planets = None 

# --- Health Check Route ---
@app.route('/', methods=['GET'])
def health_check():
    """A simple route to confirm the service is alive and the ephemeris is loaded."""
    # Check if the loading step above failed
    if planets is None:
        return jsonify({"status": "error", "message": "Skyfield data not loaded. Check logs for FATAL ERROR."}), 500
    
    # Success response
    return jsonify({
        "status": "ok",
        "message": "Astro Calculator is running and Skyfield data is ready.",
        "ephemeris_path_used": EPHEMERIS_PATH
    })

# --- Calculation Endpoint ---
@app.route('/calculate/moon-altaz', methods=['GET'])
def calculate_moon_position():
    """Calculates the Moon's altitude and azimuth from Washington, D.C. at a specific time."""
    if planets is None:
        return jsonify({"error": "Service not ready. Ephemeris failed to load."}), 503

    try:
        # 1. Define Observer Location (Washington, D.C. as default)
        observer_lat = 38.9072
        observer_lon = -77.0369
        observer_elevation = 100 # meters
        
        # 2. Get Time from Request Query Parameters
        # Use current UTC time as a fallback if parameters are missing
        now_utc = ts.now().utc
        year = int(request.args.get('year', now_utc[0]))
        month = int(request.args.get('month', now_utc[1]))
        day = int(request.args.get('day', now_utc[2]))
        # Default to 12:00 UTC if 'hour' is not provided
        hour = int(request.args.get('hour', 12)) 
        
        # Create a Skyfield Time object
        t = ts.utc(year, month, day, hour)
        
        # 3. Define the Observer's location object
        location = earth + Topos(latitude_degrees=observer_lat, longitude_degrees=observer_lon, elevation_m=observer_elevation)
        
        # 4. Compute the position of the Moon relative to the observer
        astrometric = location.at(t).observe(moon).apparent()
        alt, az, distance = astrometric.altaz()
        
        # 5. Format the output
        result = {
            "target": "Moon",
            "observer": f"Lat: {observer_lat}, Lon: {observer_lon}, Elev: {observer_elevation}m",
            "time_utc": t.utc_jpl(),
            "altitude": f"{alt.degrees:.4f} degrees",
            "azimuth": f"{az.degrees:.4f} degrees",
            "distance_km": f"{distance.km:.2f}",
        }
        
        return jsonify(result)

    except Exception as e:
        app.logger.error(f"Calculation Error: {e}")
        return jsonify({"error": "An internal server error occurred during calculation.", "details": str(e)}), 500

# --- Standard Gunicorn Startup ---
if __name__ == '__main__':
    # Run the application (used when running 'python your_main_script.py' locally)
    app.run(debug=False, host='0.0.0.0', port=PORT)
