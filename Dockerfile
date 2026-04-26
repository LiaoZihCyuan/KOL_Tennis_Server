# Stage 1: Use the official Python image as a base image
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if needed (e.g., for psycopg3)
# RUN apt-get update && apt-get install -y ...

# Stage 2: Install dependencies
FROM base as builder

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Create the final application image
FROM base

# Copy the installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy the application code into the container
COPY . .

# Make the entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Expose the port the app runs on
EXPOSE 5000

# Set the entrypoint to our script
ENTRYPOINT ["/app/entrypoint.sh"]

# Define the command to run the application using Gunicorn
# This will be passed to the entrypoint script
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "manage:app"]