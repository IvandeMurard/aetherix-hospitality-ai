import httpx
import asyncio
import uuid

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def test_auth_flow():
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    password = "password123"
    
    print(f"--- Starting Auth Flow Test for {email} ---")
    
    async with httpx.AsyncClient() as client:
        # 1. Register
        print("1. Registering new user...")
        reg_response = await client.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": email,
                "password": "password123",
                "full_name": "Test User",
                "department_role": "operations"
            }
        )
        if reg_response.status_code != 201:
            print(f"FAILED: Register status {reg_response.status_code}")
            print(f"Response: {reg_response.text}")
            return
        print("SUCCESS: User registered.")
        user_id = reg_response.json()["id"]

        # 2. Login
        print("2. Logging in...")
        login_response = await client.post(
            f"{BASE_URL}/auth/jwt/login",
            data={
                "username": email,
                "password": password
            }
        )
        if login_response.status_code != 200:
            print(f"FAILED: Login status {login_response.status_code}")
            return
        token = login_response.json()["access_token"]
        print("SUCCESS: Token retrieved.")

        # 3. Access guarded endpoint (expect 404 since no property linked yet)
        print("3. Accessing /pms/status (expecting 404 No property linked)...")
        status_response = await client.get(
            f"{BASE_URL}/pms/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        print(f"RESULT: Status {status_response.status_code}, Detail: {status_response.json().get('detail') or status_response.json().get('property_name')}")
        
        # 4. Access /auth/me
        print("4. Accessing /auth/me...")
        me_response = await client.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        print(f"RESULT: Me profile: {me_response.json()}")

if __name__ == "__main__":
    asyncio.run(test_auth_flow())
