FROM python:3.12.11

# Install system dependencies required by Playwright
RUN apt-get update && apt-get install -y \
    wget curl gnupg unzip \
    libnss3 libatk-bridge2.0-0 libgtk-3-0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libasound2 libxshmfence1 libxss1 fonts-liberation libappindicator3-1 libatk1.0-0 \
    libdbus-glib-1-2 xdg-utils \
    libgstreamer1.0-0 gstreamer1.0-libav gstreamer1.0-tools gstreamer1.0-alsa \
    libflite1 libopus0 libvpx7 libx264-dev libwoff1 \
    libenchant-2-2 libsecret-1-0 libhyphen0 libmanette-0.2-0 libavif13 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy app code
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Install Playwright and required browsers
RUN pip install playwright && playwright install --with-deps

# Expose Gradio port
EXPOSE 7860

# Run the Gradio app
CMD ["python", "app.py"]
