# 1. Base Image: Use a slim Python image for smaller size.
FROM python:3.10-slim

# 2. Set Working Directory
WORKDIR /app

# 3. Install dependencies needed for system operations (specifically curl)
RUN apt-get update &&     apt-get install -y curl &&     rm -rf /var/lib/apt/lists/*

# 4. Download astronomy data file directly to /app (the WORKDIR).
# CRITICAL FIX: The de421 link is broken (404). Switching to a reliable de430 link.
RUN curl -o /app/de430.bsp -fL https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de430.bsp

# 5. Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy your application code
COPY . .

# 7. Define the default command to run your application using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "your_main_script:app"]
