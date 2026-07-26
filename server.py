from fastapi import FastAPI
import uvicorn

app = FastAPI(
    title="URL Shortener",
    description="A MVP evolving URL shortener system"
)


@app.get("/")
def read_root():
    return {"message": "Hello World"}


# You can launch the script directly using 'python server.py'
if __name__ == "__main__":
    print("🚀 Launching Stage 0 Base Server...")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)