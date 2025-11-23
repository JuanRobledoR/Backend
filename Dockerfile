# Usamos una imagen de Python ligera
FROM python:3.10-slim

# Instalar dependencias del sistema necesarias para LIBROSA y AUDIO
# libsndfile1 es obligatorio para soundfile/librosa
# ffmpeg ayuda a leer mp3 sin problemas
RUN apt-get update && apt-get install -y \
    gcc \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos los requerimientos e instalamos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el código del backend a la carpeta /app
COPY . .

# Comando para correr el servidor
# Usamos 0.0.0.0 para que sea accesible desde fuera del contenedor
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
