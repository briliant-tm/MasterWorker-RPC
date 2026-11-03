FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m grpc_tools.protoc -I=proto --python_out=generated --grpc_python_out=generated proto/master_worker.proto
ENV PYTHONUNBUFFERED=1
