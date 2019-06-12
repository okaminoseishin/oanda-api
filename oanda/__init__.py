import re
import json
import wrapt
from requests import Response
from dataclasses import dataclass
from urllib.parse import urlparse
from requests.sessions import Session


def classdecorator(decorator):
    """
    Decorates all public methods of `target` class with `decorator`.
    """
    def decorated(target):
        for name, value in target.__dict__.items():
            if callable(value) and not name.startswith('_'):
                setattr(target, name, decorator(value))
        return target
    return decorated


@classdecorator
@wrapt.decorator
def setcontext(wrapped, instance, args, kwargs):
    """
    Makes `wrapped` bounded with initial `context` instead of `instance`.
    """
    return wrapped.__func__(instance.context, *args, **kwargs)


@classdecorator
@wrapt.decorator
def moderate(wrapped, instance, args, kwargs):
    """
    Prepares request parameters and checks if response status is OK.

    Returns
    -------
        APIResponse or response.json()
            Return prepared and checked Response with additional features,
            or, depending on unpack attribute of context, loaded body.
            Stream response always returned as APIResponse object.

    Raises
    ------
        APIError
            If response status code is not 200(read OK) or 201(write OK).
            There are only success response codes for Oanda v20 API.
    """
    if 'since' in kwargs:
        kwargs['from'] = kwargs.pop('since')
    if 'until' in kwargs:
        kwargs['to'] = kwargs.pop('until')
    args = [
        str(item) if isinstance(item, (int, float)) else item for item in args
    ]
    kwargs = {
        key: (str(value) if isinstance(value, (int, float)) else value)
        for (key, value) in kwargs.items()
    }

    response = APIResponse.convert(wrapped(*args, **kwargs))
    if response.status_code not in (200, 201):
        raise APIError(response)
    if instance.context.unpack and 'stream' not in response.url:
        return response.json()
    return response


class AttributeDictionary(dict):
    """
    Dictionary with keys accessible as nested attributes.

    Warning
    -------
        Neither keys equal to dict attribute names nor invalid attribute
        names(e.g. integers) supported.

    Examples
    --------
        >>> object = AttributeDictionary({'foo': {'bar': 'ABC'}})
        >>> print(object.foo.bar)
        ABC

        >>> object = AttributeDictionary({
        ...     'foo': [{'bar': 'DEF'}, {'baz': 'GHI'}]
        ... })
        >>> print(object.foo[0].bar)
        DEF

        >>> object = AttributeDictionary({'items': ...})
        Traceback (most recent call last):
        AttributeError: key name equal to dict attribute

        >>> object = AttributeDictionary({'123': ...})
        Traceback (most recent call last):
        AttributeError: key name is not a valid identifier
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, value in self.items():
            self.__setitem__(key, value)

    def __setitem__(self, key, value):
        if key in set(*map(dir, super().__self_class__.__bases__)):
            raise AttributeError('key name equal to dict attribute')
        elif not key.isidentifier():
            raise AttributeError('key name is not a valid identifier')
        if isinstance(value, super().__self_class__.__bases__):
            value = type(self)(value)
        elif isinstance(value, list):
            value = type(value)([
                type(self)(item)
                if type(item) in
                super(type(self), self).__self_class__.__bases__
                else item for item in value
            ])
        super().__setitem__(key, value)
        super().__setattr__(key, value)

    def __delitem__(self, key):
        super().__delitem__(key)
        super().__delattr__(key)

    def __setattr__(self, name, value):
        self.__setitem__(name, value)

    def __delattr__(self, name):
        self.__delitem__(name)


class APIResponse(Response):
    @classmethod
    def convert(self, other):
        """
        Changes type of `other` to `APIResponse`.

        Due to the impossibility to make `requests.request` return `Response`
        subclass instance, there is this hack.
        """
        other.__class__ = self
        return other

    def json(self, nativetypes: bool = False, **kwargs):
        """
        Deserialises response body into data structure which type depends
        on `nativetypes` flag.

        Parameters
        ----------
            nativetypes: bool
                Determinates type of returned object.

        Keyword arguments
        -----------------
            Optional arguments that json.loads takes.

        Returns
        -------
            (dict or list) or AttributeDictionary
                If nativetypes set to True, return pure json.loads result.
                Else convert it to AttributeDictionary object.

        See also
        --------
            AttributeDictionary
                Description of one of response types.
        """
        body = super().json(**kwargs)
        return body if nativetypes else AttributeDictionary(body)

    def jsonlines(
        self, nativetypes: bool = False, heartbeat: bool = True, **kwargs
    ):
        """
        Deserialises stream lines into data structure which type depends
        on `nativetypes` flag.

        Parameters
        ----------
            heartbeat: bool
                Include heartbeat lines into result or not.

        See also
        --------
            APIResponse.json
                Result type and other parameters description.
        """
        for line in self.iter_lines():
            line = json.loads(line, **kwargs)
            if heartbeat or line.get('type') != 'HEARTBEAT':
                yield line if nativetypes else AttributeDictionary(line)

    def __iter__(self):
        return self.jsonlines()

    def __repr__(self):
        return f'<{type(self).__name__} [{self.status_code}]>'


class APIError(Exception):
    """
    Raises if request was rejected by some reason(i.e. bad request).

    Parameters
    ----------
        response: APIResponse
            Object with response details to analyse.

    Attributes
    ----------
        response: APIResponse
            Object with response details to analyse.
        body: AttributeDictionary or str
            Content of the response for reason description.
    """

    def __init__(self, response: APIResponse, *args):
        self.response = response

        try:
            self.body = self.response.json()
            message = self.body.errorMessage
        except json.decoder.JSONDecodeError:
            self.body = self.response.text
            message = self.response.reason
        finally:
            message = (
                f'{self.response.request.method} {self.clearpath()}: '
                f'{self.response.status_code} {message}'
            )

        super().__init__(message, *args)

    def clearpath(self):
        return re.sub(
            r'accounts/([^/]*)(\/|$)',
            lambda sub: sub.group(0).replace(sub.group(1), '<ACCOUNT>'),
            urlparse(self.response.url).path
        )


class Context(Session):
    """
    Oanda V20 API session.

    Provides user-specific, endpoint-independent configuration storage and
    hierarchical access to API methods.

    Parameters
    ----------
        token: str
            The authorization bearer token previously obtained by the client.
        timeformat: str, optional
            Format of DateTime fields in the request and response. May be
            'UNIX'(default) or 'RFC3339'.

    Keyword-only arguments
    ----------------------
        type: str
            Trading environment. May be 'trade' or 'practice'. Must be
            explicitly provided to ensure risks understanding.
        unpack: bool, optional
            If True, make methods return APIResponse.json result rather
            than APIResponse instance. True by default.

    Attributes
    ----------
        token: str
            The authorization bearer token previously obtained by the client.
        timeformat: str, optional
            Format of DateTime fields in the request and response. May be
            'UNIX'(default) or 'RFC3339'.
        type: str
            Trading environment. May be 'trade' or 'practice'. Must be
            explicitly provided to ensure risks understanding.
        unpack: bool, optional
            If True, make methods return APIResponse.json result rather
            than APIResponse instance. True by default.
        hostname: str
            Base URL with anonymous placeholder for subdomain and API
            version at the root of the path, without trailing slash.
            'https://{}.oanda.com/v3' by default.

    Warning
    -------
        Wrapper does not created for nor tested with V1 API, so change it
        in the hostname at your own risk.
    """

    hostname: str = 'https://{}.oanda.com/v3'

    def __init__(
        self, token: str, timeformat: str = 'UNIX',
        *, type: str, unpack: bool = True
    ):
        super().__init__()

        self.type = type
        self.token = token
        self.unpack = unpack
        self.timeformat = timeformat

        self.order = order.Group(self)
        self.trade = trade.Group(self)
        self.account = account.Group(self)
        self.pricing = pricing.Group(self)
        self.position = position.Group(self)
        self.instrument = instrument.Group(self)
        self.transaction = transaction.Group(self)

    def __setattr__(self, name, value):
        if name == 'token':
            self.headers.update({'Authorization': f'Bearer {value}'})
        elif name == 'timeformat':
            if value.upper() not in ('UNIX', 'RFC3339'):
                raise ValueError(f'incorrect time format: {value.upper()}')
            self.headers.update({'Accept-Datetime-Format': value.upper()})
        elif name == 'type' and value.lower() not in ('trade', 'practice'):
            raise ValueError(f'incorrect trade environment: {value.lower()}')
        super().__setattr__(name, value)

    def url(self, endpoint: str):
        return self.hostname.format(
            'stream-fx{}' if 'stream' in endpoint else 'api-fx{}'
        ).format(self.type) + endpoint


@dataclass
class APIGroup:
    context: Context


from . import account, instrument, order, trade
from . import position, transaction, pricing
