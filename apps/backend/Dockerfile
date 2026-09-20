# Builder: compiles any dependency that ships no wheel for the target platform.
# gcc — and the kernel headers in linux-libc-dev that it pulls in through
# libc6-dev — stay in this stage, so the runtime image below carries neither.
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# A virtualenv keeps the dependencies under one directory the runtime stage can
# copy wholesale, instead of picking them out of the system site-packages.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# The base image pins pip 24.0 and setuptools 79.0.1, both of which carry
# reported vulnerabilities, and a fresh venv inherits them. Upgrade before
# installing anything: setuptools also vendors wheel and jaraco.context, so
# these three cover the whole packaging toolchain.
RUN pip install --upgrade pip setuptools wheel

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim

WORKDIR /app

# Install system dependencies. Only postgresql-client: entrypoint.sh waits on
# pg_isready, and nothing at runtime compiles anything.
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# The runtime stage carries its own copy of the packaging toolchain in the
# system site-packages, at the same vulnerable versions. Nothing here installs
# packages, but the scanner still sees them, so upgrade these too.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Take the dependencies built above. Same base image, so the virtualenv's links
# back to the interpreter resolve unchanged.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy entrypoint script and make it executable
COPY entrypoint.sh .
RUN chmod +x /app/entrypoint.sh

# Copy application code
COPY . .

# Create directory for document storage
RUN mkdir -p /data/documents

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
