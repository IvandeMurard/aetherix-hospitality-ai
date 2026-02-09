---
title: F&B Agent API
emoji: 🍽️
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: "4.0.0"
python_version: "3.11"
app_port: 7860
pinned: false
---

# Aetherix – F&B Ambient Agent  
**PMS-agnostic intelligence layer to anticipate staffing & F&B needs in hotels**

> (AI) Insights come to and learn from you (WhatsApp, Slack, Teams) instead of yet another dashboard to onboard.  
> Contextual predictions + feedback loop + explainability, no vendor lock-in.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-Live-orange?logo=streamlit)](https://aetherix.streamlit.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![HF Spaces](https://img.shields.io/badge/HuggingFace-Spaces-blueviolet)](https://huggingface.co/spaces/ivandemurard/fb-agent-api)

**Live Dashboard (Phase 3, early prototype)** → https://aetherix.streamlit.app/

### Real Problem (Hospitality 2026)
Restaurant managers spend **5–8 hours/week** on manual forecasting with ~**70%** accuracy → over/under-staffing, food waste, operational stress.

### Solution: A new (AI) Colleague
or agent, that:
- **Anticipates** demand (covers, staffing, purchases) using RAG + external signals (weather, events, holidays, and real-time social sentiment)
- **Explains** its predictions (impact %, confidence score) for transparency and adoption
- **Learns** from your corrections and PMS data (feedback loop) for continuous and autonomous improvement
- **Delivers where you work**: WhatsApp/Slack for quick briefs, dashboard for adoption, config & deep dive
- **PMS-agnostic**: using a semantic layer connecting Mews, Opera, Apaleo, Cloudbeds, etc. without lock-in. Smart!

| Classic Dashboard            | Ambient Agent (Aetherix)              |
|------------------------------|----------------------------------------|
| You have to remember to check| Agent proactively sends you the brief |
| Painful context switching    | Integrated into your daily tools       |
| Feedback = separate step     | Natural correction in conversation     |
| PMS + external data silos    | Semantic unification + contextual RAG  |

### Architecture (3 Layers)

Voir le diagramme SVG ci-dessous dans la section Architecture.

---

## 💡 The solution I'm working on:

An **intelligence layer** for hotel managers that:
- **Connects to any PMS** through a semantic abstraction layer (Mews, Opera, Apaleo, Protel, Cloudbeds, ...)
- **Predicts demand** using RAG architecture with internal and external historical pattern matching
- **Explains reasoning** so managers can trust and correct predictions (transparency)
- **Learns from feedback** to improve accuracy over time (feedback loop)
- **Lives where you work** : via a dashboard for analytics, and messaging apps for daily operations

---

## 🏗️ Architecture

<img src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA3MDAgODAwIiB3aWR0aD0iNDIwIiBoZWlnaHQ9IjQ4MCI+CiAgPGRlZnM+CiAgICA8c3R5bGU+CiAgICAgIC50aXRsZSB7IGZvbnQtZmFtaWx5OiAnU2Vnb2UgVUknLCBBcmlhbCwgc2Fucy1zZXJpZjsgZm9udC1zaXplOiAxOHB4OyBmb250LXdlaWdodDogYm9sZDsgZmlsbDogI2ZmZmZmZjsgfQogICAgICAuc3VidGl0bGUgeyBmb250LWZhbWlseTogJ1NlZ29lIFVJJywgQXJpYWwsIHNhbnMtc2VyaWY7IGZvbnQtc2l6ZTogMTBweDsgZmlsbDogIzk0YTNiODsgfQogICAgICAubGF5ZXItbGFiZWwgeyBmb250LWZhbWlseTogJ1NlZ29lIFVJJywgQXJpYWwsIHNhbnMtc2VyaWY7IGZvbnQtc2l6ZTogOHB4OyBmb250LXdlaWdodDogNjAwOyBmaWxsOiAjZmZmZmZmOyBsZXR0ZXItc3BhY2luZzogMS41cHg7IH0KICAgICAgLmNvbXBvbmVudCB7IGZvbnQtZmFtaWx5OiAnU2Vnb2UgVUknLCBBcmlhbCwgc2Fucy1zZXJpZjsgZm9udC1zaXplOiA5cHg7IGZvbnQtd2VpZ2h0OiA1MDA7IGZpbGw6ICNmZmZmZmY7IH0KICAgICAgLmNvbXBvbmVudC1kYXJrIHsgZm9udC1mYW1pbHk6ICdTZWdvZSBVSScsIEFyaWFsLCBzYW5zLXNlcmlmOyBmb250LXNpemU6IDlweDsgZm9udC13ZWlnaHQ6IDUwMDsgZmlsbDogIzFlMjkzYjsgfQogICAgICAuY2VudGVyLXRpdGxlIHsgZm9udC1mYW1pbHk6ICdTZWdvZSBVSScsIEFyaWFsLCBzYW5zLXNlcmlmOyBmb250LXNpemU6IDEzcHg7IGZvbnQtd2VpZ2h0OiBib2xkOyBmaWxsOiAjZmZmZmZmOyB9CiAgICAgIC5jZW50ZXItc3ViIHsgZm9udC1mYW1pbHk6ICdTZWdvZSBVSScsIEFyaWFsLCBzYW5zLXNlcmlmOyBmb250LXNpemU6IDdweDsgZmlsbDogIzk0YTNiODsgfQogICAgICAubGVnZW5kLXRleHQgeyBmb250LWZhbWlseTogJ1NlZ29lIFVJJywgQXJpYWwsIHNhbnMtc2VyaWY7IGZvbnQtc2l6ZTogOHB4OyBmaWxsOiAjOTRhM2I4OyB9CiAgICAgIC50YWdsaW5lIHsgZm9udC1mYW1pbHk6ICdTZWdvZSBVSScsIEFyaWFsLCBzYW5zLXNlcmlmOyBmb250LXNpemU6IDEwcHg7IGZvbnQtc3R5bGU6IGl0YWxpYzsgZmlsbDogI2Y1OWUwYjsgfQogICAgICAuZmVlZGJhY2stbGFiZWwgeyBmb250LWZhbWlseTogJ1NlZ29lIFVJJywgQXJpYWwsIHNhbnMtc2VyaWY7IGZvbnQtc2l6ZTogOXB4OyBmb250LXdlaWdodDogNjAwOyBmaWxsOiAjZjU5ZTBiOyB9CiAgICA8L3N0eWxlPgogICAgPG1hcmtlciBpZD0iYXJyb3doZWFkLWZlZWRiYWNrIiBtYXJrZXJXaWR0aD0iOCIgbWFya2VySGVpZ2h0PSI2IiByZWZYPSI3IiByZWZZPSIzIiBvcmllbnQ9ImF1dG8iPgogICAgICA8cG9seWdvbiBwb2ludHM9IjAgMCwgOCAzLCAwIDYiIGZpbGw9IiNmNTllMGIiLz4KICAgIDwvbWFya2VyPgogIDwvZGVmcz4KICAKICA8IS0tIEJhY2tncm91bmQgLS0+CiAgPHJlY3Qgd2lkdGg9IjcwMCIgaGVpZ2h0PSI4MDAiIGZpbGw9IiMwZjE3MmEiLz4KICAKICA8IS0tIFRpdGxlIC0tPgogIDx0ZXh0IHg9IjM1MCIgeT0iMjgiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGNsYXNzPSJ0aXRsZSI+QWV0aGVyaXggQXJjaGl0ZWN0dXJlPC90ZXh0PgogIDx0ZXh0IHg9IjM1MCIgeT0iNDQiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGNsYXNzPSJzdWJ0aXRsZSI+SW50ZWxsaWdlbmNlIGxheWVyIGNvbm5lY3RpbmcgZXhpc3RpbmcgaG90ZWwgc3lzdGVtczwvdGV4dD4KICAKICA8IS0tIE1haW4gdmlzdWFsaXphdGlvbiBncm91cCAtLT4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgwLCAyNCkiPgogICAgCiAgICA8IS0tIERlbGl2ZXJ5IExheWVyIChvdXRlciByaW5nKSAtLT4KICAgIDxjaXJjbGUgY3g9IjM1MCIgY3k9IjI2NCIgcj0iMjAwIiBmaWxsPSJub25lIiBzdHJva2U9IiM5MjQwMGUiIHN0cm9rZS13aWR0aD0iNTIiLz4KICAgIDx0ZXh0IHg9IjM1MCIgeT0iNzYiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGNsYXNzPSJsYXllci1sYWJlbCI+REVMSVZFUlk8L3RleHQ+CiAgICAKICAgIDwhLS0gSW50ZWxsaWdlbmNlIExheWVyIC0tPgogICAgPGNpcmNsZSBjeD0iMzUwIiBjeT0iMjY0IiByPSIxNDgiIGZpbGw9IiMxZTNhNWYiIHN0cm9rZT0iIzI1NjNlYiIgc3Ryb2tlLXdpZHRoPSIyIi8+CiAgICA8dGV4dCB4PSIzNTAiIHk9IjEyOCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImxheWVyLWxhYmVsIj5JTlRFTExJR0VOQ0U8L3RleHQ+CiAgICAKICAgIDwhLS0gU2VtYW50aWMgTGF5ZXIgLS0+CiAgICA8Y2lyY2xlIGN4PSIzNTAiIGN5PSIyNjQiIHI9Ijk2IiBmaWxsPSIjMDY0ZTNiIiBzdHJva2U9IiMwNTk2NjkiIHN0cm9rZS13aWR0aD0iMiIvPgogICAgPHRleHQgeD0iMzUwIiB5PSIxODAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGNsYXNzPSJsYXllci1sYWJlbCI+U0VNQU5USUMgTEFZRVI8L3RleHQ+CiAgICAKICAgIDwhLS0gQ2VudGVyIC0gSG90ZWwgU3lzdGVtcyAtLT4KICAgIDxjaXJjbGUgY3g9IjM1MCIgY3k9IjI2NCIgcj0iNDgiIGZpbGw9IiMxZTI5M2IiIHN0cm9rZT0iIzQ3NTU2OSIgc3Ryb2tlLXdpZHRoPSIyIi8+CiAgICA8dGV4dCB4PSIzNTAiIHk9IjI1OCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImNlbnRlci10aXRsZSI+SE9URUw8L3RleHQ+CiAgICA8dGV4dCB4PSIzNTAiIHk9IjI3MCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImNlbnRlci1zdWIiPkV4aXN0aW5nIFN5c3RlbXM8L3RleHQ+CiAgICA8dGV4dCB4PSIzNTAiIHk9IjI4MiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImNlbnRlci1zdWIiPlBNUyAiIFBPUyAiIFJNUzwvdGV4dD4KICAgIAogICAgPCEtLSBTZW1hbnRpYyBMYXllciBDb21wb25lbnRzIC0tPgogICAgPHJlY3QgeD0iMjMyIiB5PSIxOTIiIHdpZHRoPSI5NiIgaGVpZ2h0PSIyMSIgcng9IjEwIiBmaWxsPSIjMDU5NjY5Ii8+CiAgICA8dGV4dCB4PSIyODAiIHk9IjIwNiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImNvbXBvbmVudCI+VW5pZmllZCBNb2RlbDwvdGV4dD4KICAgIAogICAgPHJlY3QgeD0iMzQ0IiB5PSIyNTQiIHdpZHRoPSI2NCIgaGVpZ2h0PSIyMSIgcng9IjEwIiBmaWxsPSIjMDU5NjY5Ii8+CiAgICA8dGV4dCB4PSIzNzYiIHk9IjI2OCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImNvbXBvbmVudCI+QWRhcHRlcnM8L3RleHQ+CiAgICAKICAgIDxyZWN0IHg9IjE1MiIgeT0iMjU0IiB3aWR0aD0iNTYiIGhlaWdodD0iMjEiIHJ4PSIxMCIgZmlsbD0iIzA1OTY2OSIvPgogICAgPHRleHQgeD0iMTgwIiB5PSIyNjgiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGNsYXNzPSJjb21wb25lbnQiPkV2ZW50czwvdGV4dD4KICAgIAogICAgPHJlY3QgeD0iMjI4IiB5PSIzMjAiIHdpZHRoPSI4OCIgaGVpZ2h0PSIyMSIgcng9IjEwIiBmaWxsPSIjMDU5NjY5Ii8+CiAgICA8dGV4dCB4PSIyNzIiIHk9IjMzNCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImNvbXBvbmVudCI+RXh0ZXJuYWwgQVBJczwvdGV4dD4KICAgIAogICAgPCEtLSBJbnRlbGxpZ2VuY2UgTGF5ZXIgQ29tcG9uZW50cyAtLT4KICAgIDxyZWN0IHg9IjE2NCIgeT0iMTU2IiB3aWR0aD0iNzIiIGhlaWdodD0iMjIiIHJ4PSIxMSIgZmlsbD0iIzNiODJmNiIvPgogICAgPHRleHQgeD0iMjAwIiB5PSIxNzEiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGNsYXNzPSJjb21wb25lbnQiPlJlYXNvbmluZzwvdGV4dD4KICAgIAogICAgPHJlY3QgeD0iMzI0IiB5PSIxNTYiIHdpZHRoPSI3MiIgaGVpZ2h0PSIyMiIgcng9IjExIiBmaWxsPSIjM2I4MmY2Ii8+CiAgICA8dGV4dCB4PSIzNjAiIHk9IjE3MSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImNvbXBvbmVudCI+UHJlZGljdGlvbjwvdGV4dD4KICAgIAogICAgPHJlY3QgeD0iMTQ0IiB5PSIzNDgiIHdpZHRoPSI3NiIgaGVpZ2h0PSIyMiIgcng9IjExIiBmaWxsPSIjM2I4MmY2Ii8+CiAgICA8dGV4dCB4PSIxODIiIHk9IjM2MyIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImNvbXBvbmVudCI+Q29uZmlkZW5jZTwvdGV4dD4KICAgIAogICAgPHJlY3QgeD0iMzQwIiB5PSIzNDgiIHdpZHRoPSI1NiIgaGVpZ2h0PSIyMiIgcng9IjExIiBmaWxsPSIjM2I4MmY2Ii8+CiAgICA8dGV4dCB4PSIzNjgiIHk9IjM2MyIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImNvbXBvbmVudCI+UkFHPC90ZXh0PgogICAgCiAgICA8IS0tIERlbGl2ZXJ5IExheWVyIENvbXBvbmVudHMgLS0+CiAgICA8cmVjdCB4PSIyMzIiIHk9IjgwIiB3aWR0aD0iODAiIGhlaWdodD0iMjIiIHJ4PSIxMSIgZmlsbD0iI2Y1OWUwYiIvPgogICAgPHRleHQgeD0iMjcyIiB5PSI5NSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImNvbXBvbmVudC1kYXJrIj5EYXNoYm9hcmQ8L3RleHQ+CiAgICAKICAgIDxyZWN0IHg9IjQ0OCIgeT0iMjU0IiB3aWR0aD0iNTYiIGhlaWdodD0iMjIiIHJ4PSIxMSIgZmlsbD0iI2Y1OWUwYiIvPgogICAgPHRleHQgeD0iNDc2IiB5PSIyNjkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGNsYXNzPSJjb21wb25lbnQtZGFyayI+U2xhY2s8L3RleHQ+CiAgICAKICAgIDxyZWN0IHg9IjU2IiB5PSIyNTQiIHdpZHRoPSI3MiIgaGVpZ2h0PSIyMiIgcng9IjExIiBmaWxsPSIjZjU5ZTBiIi8+CiAgICA8dGV4dCB4PSI5MiIgeT0iMjY5IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBjbGFzcz0iY29tcG9uZW50LWRhcmsiPldoYXRzQXBwPC90ZXh0PgogICAgCiAgICA8cmVjdCB4PSIyNDQiIHk9IjQzNiIgd2lkdGg9IjU2IiBoZWlnaHQ9IjIyIiByeD0iMTEiIGZpbGw9IiNmNTllMGIiLz4KICAgIDx0ZXh0IHg9IjI3MiIgeT0iNDUxIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBjbGFzcz0iY29tcG9uZW50LWRhcmsiPlZvaWNlPC90ZXh0PgogICAgCiAgICA8IS0tIEZFRURCQUNLIExPT1AgLSBQcm9taW5lbnQgY3VydmVkIGFycm93IC0tPgogICAgPHBhdGggZD0iTSA0NjQgMzA0IAogICAgICAgICAgICAgUSA0OTYgMzA0LCA0OTYgMzM2IAogICAgICAgICAgICAgTCA0OTYgNDE2IAogICAgICAgICAgICAgUSA0OTYgNDQ4LCA0NjQgNDQ4IAogICAgICAgICAgICAgTCAxNjAgNDQ4IAogICAgICAgICAgICAgUSAxMjggNDQ4LCAxMjggNDE2IAogICAgICAgICAgICAgTCAxMjggMzM2IAogICAgICAgICAgICAgUSAxMjggMzA0LCAxNjAgMzA0IiAKICAgICAgICAgIGZpbGw9Im5vbmUiIAogICAgICAgICAgc3Ryb2tlPSIjZjU5ZTBiIiAKICAgICAgICAgIHN0cm9rZS13aWR0aD0iMi41IiAKICAgICAgICAgIHN0cm9rZS1kYXNoYXJyYXk9IjYsMyIKICAgICAgICAgIG1hcmtlci1lbmQ9InVybCgjYXJyb3doZWFkLWZlZWRiYWNrKSIvPgogICAgCiAgICA8IS0tIEZlZWRiYWNrIExvb3AgTGFiZWwgLS0+CiAgICA8cmVjdCB4PSIyMzIiIHk9IjQ4MCIgd2lkdGg9IjExMiIgaGVpZ2h0PSIyMiIgcng9IjUiIGZpbGw9IiNmNTllMGIiLz4KICAgIDx0ZXh0IHg9IjI4OCIgeT0iNDk1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBjbGFzcz0iY29tcG9uZW50LWRhcmsiPkZFRURCQUNLIExPT1A8L3RleHQ+CiAgICAKICAgIDwhLS0gRmVlZGJhY2sgZGVzY3JpcHRpb24gLS0+CiAgICA8dGV4dCB4PSIzNTAiIHk9IjUyMCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgY2xhc3M9ImZlZWRiYWNrLWxhYmVsIj5Db250aW51b3VzIGxlYXJuaW5nIGZyb20gYWN0dWFsIHJlc3VsdHM8L3RleHQ+CiAgICAKICA8L2c+CiAgCiAgPCEtLSBMZWdlbmQgLS0+CiAgPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoODAsIDU2OCkiPgogICAgPHJlY3QgeD0iMCIgeT0iMCIgd2lkdGg9IjEzIiBoZWlnaHQ9IjEwIiByeD0iMiIgZmlsbD0iI2Y1OWUwYiIvPgogICAgPHRleHQgeD0iMTgiIHk9IjgiIGNsYXNzPSJsZWdlbmQtdGV4dCI+RGVsaXZlcnkgLSBBbWJpZW50IEV4cGVyaWVuY2U8L3RleHQ+CiAgICAKICAgIDxyZWN0IHg9IjE2MCIgeT0iMCIgd2lkdGg9IjEzIiBoZWlnaHQ9IjEwIiByeD0iMiIgZmlsbD0iIzNiODJmNiIvPgogICAgPHRleHQgeD0iMTc4IiB5PSI4IiBjbGFzcz0ibGVnZW5kLXRleHQiPkludGVsbGlnZW5jZSAtIFJBRyArIFJlYXNvbmluZzwvdGV4dD4KICAgIAogICAgPHJlY3QgeD0iMzM2IiB5PSIwIiB3aWR0aD0iMTMiIGhlaWdodD0iMTAiIHJ4PSIyIiBmaWxsPSIjMDU5NjY5Ii8+CiAgICA8dGV4dCB4PSIzNTQiIHk9IjgiIGNsYXNzPSJsZWdlbmQtdGV4dCI+U2VtYW50aWMgTGF5ZXI8L3RleHQ+CiAgPC9nPgogIAogIDxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKDIwMCwgNTg4KSI+CiAgICA8cmVjdCB4PSIwIiB5PSIwIiB3aWR0aD0iMTMiIGhlaWdodD0iMTAiIHJ4PSIyIiBmaWxsPSIjNDc1NTY5Ii8+CiAgICA8dGV4dCB4PSIxOCIgeT0iOCIgY2xhc3M9ImxlZ2VuZC10ZXh0Ij5FeGlzdGluZyBTeXN0ZW1zPC90ZXh0PgogICAgCiAgICA8bGluZSB4MT0iOTYiIHkxPSI1IiB4Mj0iMTIwIiB5Mj0iNSIgc3Ryb2tlPSIjZjU5ZTBiIiBzdHJva2Utd2lkdGg9IjEuNSIgc3Ryb2tlLWRhc2hhcnJheT0iMywyIi8+CiAgICA8dGV4dCB4PSIxMjgiIHk9IjgiIGNsYXNzPSJsZWdlbmQtdGV4dCI+RmVlZGJhY2sgTG9vcDwvdGV4dD4KICA8L2c+CiAgCiAgPCEtLSBUYWdsaW5lIC0tPgogIDx0ZXh0IHg9IjM1MCIgeT0iNjIwIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBjbGFzcz0idGFnbGluZSI+IkdsdWUsIG5vdCByZXBsYWNlbWVudCI8L3RleHQ+Cjwvc3ZnPgo=" width="100%" alt="Aetherix Architecture Value Diagram showing layered architecture with feedback loop" loading="lazy">
---

## ✨ Key Features

**🧠 Contextual Predictions**
- Combines external signals (city events, weather, holidays, real-time social sentiment) with internal data (occupancy, past demand)
- Qdrant vector search finds similar historical patterns
- Claude AI generates explainable reasoning

**🔍 Transparent Reasoning**
- Every prediction shows WHY with a clear breakdown of impact percentages
- Confidence scoring based on pattern match quality

**🔄 Learning Feedback Loop**
- Pre-service validation: "Does 26 covers look right to you?"
- Post-service feedback: Actual covers input
- Visible accuracy improvement: "Your feedback improved accuracy: 68% → 74%"

**🔗 PMS-Agnostic Integration**
- Semantic layer abstracts any PMS API
- No vendor lock-in, it will work with Mews, Opera, Protel, Cloudbeds
- Adding new PMS = new adapter, not agent rewrite

**📱 Ambient Experience**
- Dashboard-first design (Aetherix UI live)
- Dashboard for transparency, settings, analytics, and complex planning
- Voice/chat in messaging apps (WhatsApp, Slack, Teams) planned for Phase 5

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI + Python 3.11 | REST API, multi-agent orchestration |
| **AI/ML** | Claude Sonnet 4 (Anthropic) | Reasoning engine, natural language explanations |
| **Embeddings** | Mistral Embed | Vector embeddings for semantic search (1024 dim) |
| **Vector DB** | Qdrant Cloud | Semantic pattern search (495 patterns) |
| **Database** | Supabase (PostgreSQL) | Restaurant profiles, predictions, feedback, accuracy |
| **Cache** | Redis (Upstash) | Session state, conversation context |
| **Frontend** | Streamlit (MVP) / Next.js (v2) | Dashboard interface |
| **Deployment** | HuggingFace Spaces (Docker) | Cloud hosting, auto-scaling |

---

## 🚀 Live Demo

**Primary dashboard:** [https://aetherix.streamlit.app](https://aetherix.streamlit.app) (Streamlit Cloud)  
**Also:** [https://ivandemurard-fb-agent-api.hf.space](https://ivandemurard-fb-agent-api.hf.space) (HuggingFace Space: dashboard + API; API docs at `/docs`)

### Deployment

| Component | Status | URL |
|-----------|--------|-----|
| **Dashboard (primary)** | ✅ Live | [aetherix.streamlit.app](https://aetherix.streamlit.app) |
| HF Space (dashboard + API) | ✅ Live | [ivandemurard-fb-agent-api.hf.space](https://ivandemurard-fb-agent-api.hf.space) |
| Vector DB | ✅ Live | Qdrant Cloud (495 patterns) |

**Sync:** One push to `main` updates both: a GitHub Action syncs `main` → `master`, so Streamlit Cloud (on `master`) and the HF Space (on `main`) deploy the same code.

**Docker:** The default `Dockerfile` runs API (port 8000) + Streamlit dashboard (port 7860) for the HF Space. For API-only deployment use `Dockerfile.api`.

---

## 📈 Roadmap

### ✅ Phase 1 - Backend API (Complete)

Delivered:
- Multi-agent system (Demand Predictor, Staff Recommender, Reasoning Engine)
- Context-aware prediction with mock patterns
- Confidence scoring + explainable reasoning
- HuggingFace Spaces deployment

### ✅ Phase 2 - RAG Implementation (Complete)

Delivered:
- Kaggle Hotel Booking dataset processed (119K reservations → 495 F&B patterns)
- Qdrant vector database with Mistral embeddings
- Semantic similarity search powering predictions
- Live API with real vector search

### 🔄 Phase 3 - Dashboard & Feedback Loop (Current)

In progress:
- **Restaurant Profile**: Capacity, breakeven, staff ratios configuration
- **Post-service Feedback**: Actual covers input to close the loop
- **Accuracy Tracking**: Real MAPE calculation, visible learning progress
- **UI Anti-Slop**: Factor visibility, human context, contextual recommendations
- **Data Sources UI**: Transparent architecture roadmap in Settings

Linear issues: IVA-52, IVA-53, IVA-54, IVA-55, IVA-56

### 📋 Phase 4 - Feedback Loop + Accuracy (Next)

Planned:
- **Post-service Feedback**: Actual covers input to close the loop
- **MAPE Tracking**: Real accuracy calculation and display
- **Prediction History**: Accuracy history view
- **Continuous Learning**: Pipeline from feedback to model improvement

### 🔮 Phase 5 - Integrations (Future)

Vision:
- **PMS Connectors**: Mews, Opera, Protel adapters
- **POS Auto-sync**: Real cover data from Toast, Square, etc.
- **Voice/Chat Interface**: WhatsApp, Slack, Teams (ambient AX)
- **What-if Scenario Modeling**

---

## ⚙️ Configuration

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...          # Claude AI
QDRANT_API_KEY=...                    # Vector database
QDRANT_URL=https://...                # Qdrant cluster URL
MISTRAL_API_KEY=...                   # Embeddings generation

# Database
SUPABASE_URL=...                      # PostgreSQL
SUPABASE_KEY=...                      # Database auth

# Optional (for enhanced features)
REDIS_URL=...                         # Session cache
PREDICTHQ_API_KEY=...                 # Events data
OPENWEATHER_API_KEY=...               # Weather data
ELEVENLABS_API_KEY=...                # Voice interface
```

### Tech Stack

- **Backend**: FastAPI · Python 3.11
- **AI**: Claude Sonnet 4 (Anthropic) · Mistral Embeddings
- **Vector DB**: Qdrant Cloud (495 patterns indexed)
- **Storage**: Supabase (PostgreSQL) · Redis (cache & sessions)
- **Frontend MVP**: Streamlit · (Next.js planned for v2)
- **Deploy**: Hugging Face Spaces (Docker)

## **Looking for**  
- **Feedback on project** DM me on X @ivandemurard or [Book a call](https://cal.com/ivandemurard/30min)
- Beta hotels or restaurants (currently using mock data to start)
- Tips
- A product / AI role in hospitality tech SaaS

**Say Hi!**

Built with ❤️ by Ivan de Murard for hotels, restaurants, and those who love them
[Portfolio](https://ivandemurard.com) · [X](https://x.com/ivandemurard) · [LinkedIn](https://linkedin.com/in/ivandemurard) · ivandemurard@gmail.com

MIT License

