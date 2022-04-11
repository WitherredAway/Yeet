import typing


class Gist:
    def __init__(self, data: typing.Dict):
        self.data = data
        # Set the data dict's items as attributes
        self.__dict__.update(data)

        self.request_url = "gists/%s" % self.id

    def _update(self, data: typing.Dict):
        self.__dict__.update(data)
