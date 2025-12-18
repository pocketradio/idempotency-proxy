import hashlib
def create_fingerprint(method, path, body):
    
    encoded_bytes = method.encode('utf-8') + path.encode('utf-8') + body # since body is already in bytes
    fingerprint = hashlib.sha256(encoded_bytes).hexdigest()
    return fingerprint