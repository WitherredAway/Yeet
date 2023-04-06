import typing
import cProfile


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

def profile(func):
    def decorator(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()
        pr.print_stats(sort='tottime')
        return result
    return decorator

def async_profile(func):
    async def decorator(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = await func(*args, **kwargs)
        pr.disable()
        pr.print_stats(sort='tottime')
        return result
    return decorator
