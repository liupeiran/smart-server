# smart-server

A basic HTTP server built with Python 3 and FastAPI that returns "Hello World".

## Requirements

- Python 3.8+
- FastAPI
- Uvicorn

## Setup
```
PROMPT="%1d %1v> "
```

Create an environment
```
python3 -m venv venv
```

Python env activate
```
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

```bash
uvicorn server:app --reload
```

The server will be available at http://localhost:8000. The root endpoint (`GET /`) returns:

```json
{"message": "Hello World"}
```

## Run tests

```bash
pytest test_main.py -v
```