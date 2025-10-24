// CRITICAL: Replace this placeholder with your actual Cloud Run Service URL.
const API_BASE_URL = "https://astro-calculator-service-258592509159.us-central1.run.app";

function setStatus(message) {
    document.getElementById('status').textContent = message;
}

function displayResults(data) {
    // Check for an error message from the API
    if (data.error) {
        setStatus(`API Error: ${data.details || data.error}`);
        return;
    }

    // Display the successful calculation data
    document.getElementById('altitude').textContent = data.altitude;
    document.getElementById('azimuth').textContent = data.azimuth;
    document.getElementById('distance').textContent = `${data.distance_km} km`;
    setStatus(`Calculation successful for ${data.time_utc}`);
}

async function fetchCalculation() {
    setStatus("Fetching data from Cloud Run...");

    try {
        // 1. Read input values from the HTML form
        const year = document.getElementById('year').value;
        const month = document.getElementById('month').value;
        const day = document.getElementById('day').value;
        const hour = document.getElementById('hour').value;
        
        // 2. Construct the full URL with query parameters
        const url = `${API_BASE_URL}/calculate/moon-altaz?year=${year}&month=${month}&day=${day}&hour=${hour}`;
        
        // 3. Make the HTTP GET request
        const response = await fetch(url);
        
        // 4. Check if the HTTP status code indicates success
        if (!response.ok) {
            // Handle HTTP errors (e.g., 404, 500, 503)
            setStatus(`HTTP Error: ${response.status} ${response.statusText}`);
            return;
        }

        // 5. Parse the JSON response body
        const data = await response.json();
        
        // 6. Display the results
        displayResults(data);

    } catch (error) {
        // Handle network errors (e.g., disconnected, CORS issues)
        setStatus(`Network Error: Could not connect to API. Details: ${error.message}`);
    }
}
