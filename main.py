"""Dev entrypoint: run the API with `python main.py` (uses uvicorn)."""

import uvicorn


def main() -> None:
    uvicorn.run("croco_sign.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
