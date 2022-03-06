import typing

def isfloat(input):
    try:
        float(input)
    except:
        return False
    else:
        return True

def invert_dict(dict: typing.Dict) -> typing.Dict:
    inverted_dict = {value: key for key, value in dict.items()}
    return inverted_dict
