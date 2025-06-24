FROM python:3.10

# Install system dependencies required by Playwright
RUN apt-get update && apt-get install -y \
    wget curl gnupg unzip \
    libnss3 libatk-bridge2.0-0 libgtk-3-0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libasound2 libxshmfence1 libxss1 libnss3 fonts-liberation libappindicator3-1 libatk1.0-0 \
    libdbus-glib-1-2 xdg-utils

# Set working directory
WORKDIR /app

# Copy app code
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Install Playwright and browsers
RUN pip install playwright && playwright install 

# Expose Gradio port
EXPOSE 7860

# Run the Gradio app
CMD ["python", "app.py"]
