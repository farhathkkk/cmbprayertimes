# Use stable Python version
FROM python:3.11

# Set working directory
WORKDIR /app

# Copy all project files into container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for Flask
EXPOSE 8080

# Run your bot
CMD ["python", "main.py"]
