import httpx

async def helper(method, headers, body, target_url):
    async with httpx.AsyncClient(timeout=15) as client:
        return await client.request(method=method,url=target_url,headers=headers,content=body)