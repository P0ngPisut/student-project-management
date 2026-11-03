
from fastapi import FastAPI

app = FastAPI(
    title="Student Project Management API",
    version="0.1.0"
)


@app.get("/")
def root():
    return {"message": "Backend is running"}
