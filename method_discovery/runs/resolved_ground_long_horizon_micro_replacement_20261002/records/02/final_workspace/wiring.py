def home():
    return 'home page'

def missing():
    return 'not found'

ROUTES = {'/': home}

def resolve(path):
    return missing
