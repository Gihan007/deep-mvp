FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /home/GetDeep
COPY . .


# Install Python 3.12 and system tools
RUN apt-get update && \
    apt-get install -y python3.12 python3.12-venv python3.12-dev \
    build-essential libffi-dev libssl-dev git wget curl iputils-ping net-tools nano openssl tini && \
    ln -sf /usr/bin/python3.12 /usr/bin/python && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    echo "Python 3.12 and system packages installed successfully!"

# Create virtual environment and install Python dependencies inside it
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip && \
    # Needed for `cythonize -i` to build extension modules
    pip install --upgrade setuptools wheel && \
    pip install -r /home/GetDeep/requirements.txt && \
    echo "Python packages installed successfully inside venv!"

EXPOSE 8080


# Run Cythonization script
ENV DELETE_APP_PY=true

RUN python cythonizing_repo.py && \
    echo 'Cythonization complete.'


# Run as a non-root user in production
RUN useradd -m -u 10001 appuser && \
    chown -R appuser:appuser /home/GetDeep /opt/venv
USER appuser


# Use tini as PID 1 for proper signal handling and zombie reaping
ENTRYPOINT ["tini", "--"]

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2", "--app-dir", "src"]


# docker build -t dimuthsenz/getdeep:v3 .
