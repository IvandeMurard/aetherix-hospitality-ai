"""
Script de démarrage de l'API FastAPI
"""
import uvicorn

if __name__ == "__main__":
    print("🚀 Starting F&B Operations Agent API...")
    print("📍 API will be available at: http://localhost:8000")
    print("📚 Documentation at: http://localhost:8000/docs")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

