def home():
    return 'home page'

def missing():
    return 'not found'

# Route table used by resolve.
ROUTES = {'/': home}

def resolve(path):
    return ROUTES.get(path, missing)
