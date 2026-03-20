# F&B Operations Agent - Dashboard

Streamlit MVP for prediction visualization.

## Quick Start

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

The dashboard will open in your browser at `http://localhost:8501`.

## Features

- **Prediction Card** with covers, confidence, and method
- **Staff Recommendation** display (servers, hosts, kitchen)
- **Confidence Gauge** visualization (Plotly)
- **Expandable AI Reasoning** with similar patterns
- **Raw API Response** (debug mode)

## API Integration

The dashboard connects to the backend API deployed on HuggingFace:
- **API URL**: `https://ivandemurard-fb-agent-api.hf.space/predict`
- **Endpoint**: `POST /predict`
- **Request**: `{restaurant_id, service_date, service_type}`
- **Response**: Prediction with covers, confidence, reasoning, and staff recommendations

## Service Types

The API accepts the following service types:
- `lunch`
- `dinner`
- `brunch`

## Deployment

### Streamlit Cloud

1. Push to GitHub
2. Connect repository at [share.streamlit.io](https://share.streamlit.io)
3. Set main file: `frontend/app.py`
4. Add environment variables if needed

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run dashboard
streamlit run app.py
```

## Troubleshooting

**API Connection Error:**
- Verify the API is running at the HuggingFace URL
- Check network connectivity
- Review API documentation at `/docs` endpoint

**Import Errors:**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version (3.8+ required)

## Structure

```
frontend/
├── app.py              # Main Streamlit dashboard
├── requirements.txt    # Python dependencies
└── README.md          # This file
```
