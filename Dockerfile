# Use official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PORT 1111

# Set workspace directory
WORKDIR /app

# Copy requirements file and install python packages with PyTorch CPU index (180MB instead of 4.5GB CUDA)
COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Copy all project files
COPY . .

# Expose port
EXPOSE 1111

# Command to run the application
CMD ["python", "main.py"]
