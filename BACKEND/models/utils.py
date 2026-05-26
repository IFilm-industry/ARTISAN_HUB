from bson import ObjectId
from datetime import datetime

def format_datetime(dt):
    if isinstance(dt, datetime):
        # Format: 2026-05-26T13:11:17.123Z
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return dt

def serialize_doc(doc):
    """
    Recursively converts ObjectId to string and formats datetime to ISO strings to match Mongoose outputs.
    """
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(x) for x in doc]
    if isinstance(doc, dict):
        new_doc = {}
        for k, v in doc.items():
            if k == "_id" and isinstance(v, ObjectId):
                new_doc["_id"] = str(v)
            elif isinstance(v, ObjectId):
                new_doc[k] = str(v)
            elif isinstance(v, datetime):
                new_doc[k] = format_datetime(v)
            elif isinstance(v, (dict, list)):
                new_doc[k] = serialize_doc(v)
            else:
                new_doc[k] = v
        return new_doc
    if isinstance(doc, ObjectId):
        return str(doc)
    return doc
