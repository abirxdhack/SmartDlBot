# Use the full official Python 3.10 image
FROM python:3.10

# Set the working directory
WORKDIR /app

# Install system dependencies (only ffmpeg now)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set Flask app environment (only needed if using `flask run`)
ENV FLASK_APP=main.py

# Expose the port your app uses
EXPOSE 8000

# Command to run the bot and Flask app together
CMD flask run -h 0.0.0.0 -p 8000 & python3 main.py
