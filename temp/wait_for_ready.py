import httpx
import asyncio
import time

async def wait_for_ready():
    url = "http://127.0.0.1:8000/health"
    print(f"Waiting for server at {url}...")
    async with httpx.AsyncClient() as client:
        for i in range(60): # 60 seconds
            try:
                resp = await client.get(url, timeout=1.0)
                if resp.status_code == 200:
                    print("Server is READY!")
                    return True
            except Exception:
                pass
            print(".", end="", flush=True)
            await asyncio.sleep(1)
    print("\nServer timed out.")
    return False

if __name__ == "__main__":
    asyncio.run(wait_for_ready())
