import hashlib
from backends import BACKENDS
from fastapi import HTTPException

def server_indexing(idem_key):
    
    hash = hashlib.sha256(str.encode(idem_key))
    digest = int(hash.hexdigest(), 16) # hexdigest gives the hex string. then convt to int
    
    alive_backends = []
    for server in BACKENDS:
        if server["alive"]:
            alive_backends.append(server)
    
    if not alive_backends:
        raise HTTPException(status_code=503, detail="No alive backends available")
    
    index = digest % len(alive_backends)
    
    return alive_backends[index]['url']