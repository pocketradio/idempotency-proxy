def validation(method, headers):
    
    
    if method == "GET": return True
    
    
    if method in ["POST", "PUT", "PATCH", "DELETE"]:
        if "idempotency-key" in headers:
            return True
        
    return False