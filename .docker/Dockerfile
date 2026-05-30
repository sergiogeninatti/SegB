FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

WORKDIR /app

# Agregar repositorio de NVIDIA
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    wget \
    gnupg2 \
    && wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin \
    && mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600 \
    && wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb \
    && dpkg -i cuda-keyring_1.1-1_all.deb \
    && rm cuda-keyring_1.1-1_all.deb \
    && apt-get update

# Instalar dependencias del sistema necesarias
RUN apt-get install -y --no-install-recommends \
    python3-pip \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Configurar variables de entorno para CUDA
ENV PATH=/usr/local/cuda/bin:${PATH}
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:${LD_LIBRARY_PATH}

# Establecer variables de entorno para optimizar Poetry
ENV POETRY_VERSION=1.8.5
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VIRTUALENVS_CREATE=false
ENV POETRY_NO_INTERACTION=1

# Instalar Poetry
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Copiar archivos de dependencias
COPY pyproject.toml ./

# Instalar dependencias con Poetry
RUN poetry install --no-root --without dev --no-interaction

# Crear directorios necesarios
RUN mkdir -p /app/model /app/test /app/debug /app/fotos

# Copiar el código fuente
COPY model/ /app/model/
COPY test/ /app/test/
COPY src/ /app/src/
COPY .env /app/.env

# Copiar archivo inicial de usuarios
COPY src/initial_users.json /app/src/initial_users.json
# Asegurar que el archivo de datos exista al iniciar
RUN if [ ! -f /app/debug/users_data.json ]; then cp /app/src/initial_users.json /app/debug/users_data.json; fi

# Comando por defecto
CMD ["poetry", "run", "python3", "src/app.py"]
