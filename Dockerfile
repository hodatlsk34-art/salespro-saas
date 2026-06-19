FROM python:3.11-slim

WORKDIR /app

# Copy và cài đặt dependencies trước (tận dụng cache layer)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy toàn bộ code
COPY . .

# Railway tự inject biến PORT
ENV PORT=8000
EXPOSE 8000

WORKDIR /app/backend
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
