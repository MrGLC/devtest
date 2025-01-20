FROM python:3.9-slim

WORKDIR /app

COPY solution/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY solution/app app/
COPY solution/notebooks notebooks/

CMD ["flask", "run", "--host=0.0.0.0"] 