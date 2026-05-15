import asyncio
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession
import os
import urllib.request, urllib.parse, json

env_path = 'backend/.env'
# load env from common locations (no python-dotenv dependency)
ENV_PATHS = ['.env', 'backend/.env', '../backend/.env']
for p in ENV_PATHS:
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        break

async def go():
    data = urllib.parse.urlencode({'grant_type':'client_credentials','client_id':os.environ['APALEO_CLIENT_ID'],'client_secret':os.environ['APALEO_CLIENT_SECRET']}).encode()
    req = urllib.request.Request('https://identity.apaleo.com/connect/token', data=data, method='POST', headers={'Content-Type':'application/x-www-form-urlencoded'})
    tok = json.loads(urllib.request.urlopen(req).read())['access_token']
    async with streamablehttp_client(os.environ['APALEO_MCP_SERVER_URL'], headers={'Authorization': f'Bearer {tok}'}) as (r,w,_):
        async with ClientSession(r,w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print(f'Total tools: {len(tools.tools)}')
            for t in tools.tools:
                print(t.name)

if __name__ == '__main__':
    asyncio.run(go())
