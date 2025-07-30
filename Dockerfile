# Use Python 3.11
FROM python:3.11

# Set working directory
WORKDIR /app

# Copy all files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for Flask
EXPOSE 8080

# Start the app
CMD ["python", "main.py"]
