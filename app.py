from fastapi import FastAPI, Request
import os

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "myverifytoken")


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = None,
    hub_verify_token: str = None,
    hub_challenge: str = None,
):
    if (
        hub_mode == "subscribe"
        and hub_verify_token == VERIFY_TOKEN
    ):
        return int(hub_challenge)

    return {"error": "verification failed"}


@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()

    print("Webhook Event:")
    print(payload)

    return {"status": "ok"}