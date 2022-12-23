class UnsafeInputException(Exception):
    pass


def check_request_body(req):
    unsafe_phrases = ["javascript://", "data://"]

    for key in req.data.keys():
        data = req.data[key]
        if isinstance(data, str):
            data = data.lower()
            for phrase in unsafe_phrases:
                if phrase in data:
                    raise UnsafeInputException()
