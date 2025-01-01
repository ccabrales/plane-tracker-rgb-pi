from datetime import datetime

def convert_unix_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).isoformat() + "Z"