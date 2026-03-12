# Use the official lightweight Python image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and force stdout to log instantly
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your backend code into the container
COPY . .

# Google Cloud Run injects the $PORT environment variable dynamically.
# We must tell Uvicorn to listen on 0.0.0.0 and attach to that specific port.
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
