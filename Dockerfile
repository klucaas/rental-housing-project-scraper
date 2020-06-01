FROM python:3.8-slim
WORKDIR /app
COPY requirements.txt main.py templates.py app/
RUN pip install -r app/requirements.txt
ENTRYPOINT ["python", "app/main.py"]