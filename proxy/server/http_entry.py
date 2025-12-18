from fastapi import FastAPI, Request, HTTPException
from proxy.idempotency.validator import validation
from proxy.idempotency.fingerprint import create_fingerprint
from contextlib import asynccontextmanager
import redis.asyncio as redis
from dotenv import load_dotenv
load_dotenv()
import aiofiles
import os
from redis.exceptions import RedisError, NoScriptError
from proxy.upstream.httpx_helper import helper
import json
from fastapi import Response
import httpx

redis_port = os.getenv("REDIS_PORT", 6379)
redis_host = os.getenv("REDIS_HOST", "localhost")
base_url = "http://localhost:5000"

# app = FastAPI()

@asynccontextmanager
async def lifespan(app: FastAPI):

    client = redis.Redis(
        port=int(redis_port),
        host=redis_host,
    )
    print(f"Ping successful: {await client.ping()}")
    
    app.state.redis_client = client


    async with aiofiles.open('../redis/scripts/verify_fingerprint.lua', mode='r') as f:
        verify_script = await f.read()
    
    verify_script_sha1 = await client.script_load(verify_script)
    
    
    app.state.verify_script = verify_script
    app.state.verify_script_sha1 = verify_script_sha1



    yield 
    
    await client.aclose()
    
app = FastAPI(lifespan=lifespan)



@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def catchall(request : Request, path_name : str):
    
    method = request.method
    headers = request.headers
    body = await request.body()
    path = path_name
    
    TTL = 60
    incoming_path = f"/{path}"
    target = base_url + incoming_path
    upstream_response = None
    
    
    redis_client = request.app.state.redis_client
    boolean_result = validation(method, headers)

    
    if boolean_result:
        if method == "GET":
            try:
                upstream_response = await helper(method, headers, body, target_url=target) # pass get req directly since it doesnt affect server state
            except httpx.TimeoutException:
                return Response(
                    status_code=504,
                    content='upstream timeout',
                    headers={'content-type': 'text/plain'}
                )
                
            return Response(
                status_code=upstream_response.status_code,
                content=upstream_response.content,
                headers=dict(upstream_response.headers)
            )
            
        else:
            fingerprint = create_fingerprint(method, path, body)
            try:
                result = await redis_client.evalsha(request.app.state.verify_script_sha1,1, headers['idempotency-key'], fingerprint, TTL)
            except NoScriptError as e:
                verify_script_sha1 = await redis_client.script_load(request.app.state.verify_script)
                result = await redis_client.evalsha(verify_script_sha1, 1, headers["idempotency-key"], fingerprint, TTL)
                request.app.state.verify_script_sha1 = verify_script_sha1
            except RedisError as e:
                raise HTTPException(status_code= 429, detail= 'redis unavailable.')
            
            
            if result == "REJECT":
                    return Response(
                        status_code=425,
                        content='request is in progress',
                        headers={'content-type': 'text/plain'}
                    )

            elif result == "EXECUTING":
                
                try:
                    upstream_response = await helper(method, headers, body, target_url=target)
                except httpx.TimeoutException:
                    return Response(
                        status_code=504,
                        content='upstream timeout',
                        headers={'content-type': 'text/plain'}
                    )
                await redis_client.hset(headers['idempotency-key'], mapping = {
                    'state': 'COMPLETED', 
                    'body': upstream_response.content,
                    'headers': json.dumps(dict(upstream_response.headers)),
                    'status-code': upstream_response.status_code
                })
                
                return Response(
                    content= upstream_response.content,
                    status_code=upstream_response.status_code,
                    headers= dict(upstream_response.headers)
                )
                
            elif result == 'REPLAY':
                
                upstream_response = await redis_client.hmget(headers['idempotency-key'], ['body', 'headers', 'status-code'])
                
                return Response(
                    content=upstream_response[0],
                    status_code= int(upstream_response[2]),
                    headers = json.loads(upstream_response[1].decode('utf-8'))
                )
                
            elif result == 'CONFLICT':
                return Response(
                    status_code=409,
                    content='rejected',
                    headers={'content-type': "text/plain"}
                )
    
    else:
        return Response(
            status_code=400,
            content="idempotency-key header missing",
            headers={"content-type": "text/plain"}
        )