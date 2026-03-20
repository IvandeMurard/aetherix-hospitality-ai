# Dashboard Streamlit - Aetherix
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# Écoute sur toutes les interfaces pour être joignable depuis l’extérieur du conteneur
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
