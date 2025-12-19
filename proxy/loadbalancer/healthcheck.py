import asyncio
import httpx
from httpx import RequestError

duration = 5 # health check refresh duration

async def health_check(backend_servers):
    while True:
        async with httpx.AsyncClient(timeout=0.5) as client:        
            for server in backend_servers:
                response = None

                try:
                    response = await client.request(method='GET', url=server['url'] + '/health')
                    
                    if response.status_code < 500: # success
                        server['alive'] = True
                    else:
                        server['alive'] = False
                
                except RequestError as e:
                    server["alive"] = False
        
        await asyncio.sleep(duration)