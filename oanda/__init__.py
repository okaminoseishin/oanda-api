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

    Parameters
    ----------
        wrapped: method
            Request wrapper for specified endpoint.
        instance: Context
            Previously replaced by @setcontext class instance for wrapped.
            Actually contains Context object in which method's class instance
            was created.
        args: tuple
            Positional arguments for wrapped.
        kwargs: dict
            Keyword arguments for wrapped.

    Returns
    -------
        response: APIResponse
            Prepared and checked Response with additional features.

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
    return response


class APIResponse(Response):
    @classmethod
    def convert(self, other):
        """
        Changes `other` type to `APIResponse`.

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
                Determinates type of returned object
            kwargs: dict
                Optional arguments that json.loads takes.

        Returns
        -------
            (dict or list) or AttributeDictionary
                If nativetypes set to True, return pure json.loads result.
                Else return AttributeDictionary object which supports keys
                access through attributes('namespaces').
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
                f'{self.response.status_code} {message} ({self.body})'
            )

        super().__init__(message, *args)

    def path(self):
        return urlparse(self.response.url).path

    def clearpath(self):
        return re.sub(
            r'accounts/([^/]*)(\/|$)',
            lambda sub: sub.group(0).replace(sub.group(1), '<ACCOUNT>'),
            self.path()
        )


@dataclass
class Context(Session):
    token: str
    timeformat: str = 'UNIX'
    environment: str = 'practice'
    hostname: str = 'https://{}.oanda.com'

    def __post_init__(self):
        super().__init__()
        self.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Accept-Datetime-Format': self.timeformat
        })

        self.order = Order(self)
        self.trade = Trade(self)
        self.account = Account(self)
        self.pricing = Pricing(self)
        self.position = Position(self)
        self.instrument = Instrument(self)
        self.transaction = Transaction(self)

    def url(self, endpoint: str):
        return self.hostname.format(
            'stream-fx{}' if 'stream' in endpoint else 'api-fx{}'
        ).format(self.environment) + f'/v3{endpoint}'


@moderate
@dataclass
@setcontext
class Account:
    context: Context

    def accounts(self) -> Response:
        """
        Get a list of all Accounts authorized for the provided token.
        """
        return self.get(self.url('/accounts'))

    def details(self, accountID: str) -> Response:
        """
        Get the full details for a single Account that a client has access to.

        Full pending Order, open Trade and open Position representations are
        provided.

        Parameters
        ----------
            accountID: str
                Account identifier.
        """
        return self.get(self.url(f'/accounts/{accountID}'))

    def summary(self, accountID: str) -> Response:
        """
        Get a summary for a single Account that a client has access to.

        Parameters
        ----------
            accountID: str
                Account identifier.
        """
        return self.get(self.url(f'/accounts/{accountID}/summary'))

    def instruments(self, accountID: str, *args) -> Response:
        """
        Get the list of tradeable instruments for the given Account.

        The list of tradeable instruments is dependent on the regulatory
        division that the Account is located in, thus should be the same for
        all Accounts owned by a single user.

        Parameters
        ----------
            accountID: str
                Account identifier.
            args: list, optional
                List of instruments to query specifically.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/instruments'),
            params={'instruments': args}
        )

    def configuration(self, accountID: str, **kwargs) -> Response:
        """
        Set the client-configurable portions of an Account.

        Parameters
        ----------
            accountID: str
                Account identifier.

        Keyword arguments
        -----------------
            alias: str
                Client-defined alias (name) for the Account
            marginRate: float
                Leverage for margin trading
        """
        return self.patch(
            self.url(f'/accounts/{accountID}/configuration'), json=kwargs
        )

    def changes(self, accountID: str, transactionID: int) -> Response:
        """
        Endpoint used to poll an Account for its current state and changes
        since a specified TransactionID.

        Parameters
        ----------
            accountID: str
                Account identifier.
            transactionID: int or str
                ID of the Transaction to get Account changes since.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/changes'),
            params={'sinceTransactionID': transactionID}
        )


@moderate
@dataclass
@setcontext
class Instrument:
    context: Context

    def candles(self, instrument: str, **kwargs) -> Response:
        return self.get(
            self.url(f'/instruments/{instrument}/candles'), params=kwargs
        )

    def orderBook(self, instrument: str, **kwargs) -> Response:
        return self.get(
            self.url(f'/instruments/{instrument}/orderBook'), params=kwargs
        )

    def positionBook(self, instrument: str, **kwargs) -> Response:
        return self.get(
            self.url(f'/instruments/{instrument}/positionBook'), params=kwargs
        )


@moderate
@dataclass
@setcontext
class Order:
    context: Context

    def create(self, accountID: str, **kwargs) -> Response:
        return self.post(
            self.url(f'/accounts/{accountID}/orders'), json={'order': kwargs}
        )

    def orders(self, accountID: str, **kwargs) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/orders'), params=kwargs
        )

    def pendingOrders(self, accountID: str) -> Response:
        return self.get(self.url(f'/accounts/{accountID}/pendingOrders'))

    def details(self, accountID: str, orderSpecifier: str) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/orders/{orderSpecifier}')
        )

    def replace(
        self, accountID: str, orderSpecifier: str, **kwargs
    ) -> Response:
        return self.put(
            self.url(f'/accounts/{accountID}/orders/{orderSpecifier}'),
            json={'order': kwargs}
        )

    def cancel(self, accountID: str, orderSpecifier: str) -> Response:
        return self.put(
            self.url(f'/accounts/{accountID}/orders/{orderSpecifier}/cancel')
        )

    def extensions(
        self, accountID: str, orderSpecifier: str, **kwargs
    ) -> Response:
        return self.put(
            self.url((
                f'/accounts/{accountID}/orders/',
                f'{orderSpecifier}/clientExtensions'
            )), json=kwargs
        )


@moderate
@dataclass
@setcontext
class Trade:
    context: Context

    def trades(self, accountID: str, **kwargs) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/trades'), params=kwargs
        )

    def openTrades(self, accountID: str) -> Response:
        return self.get(self.url(f'/accounts/{accountID}/openTrades'))

    def details(self, accountID: str, tradeSpecifier: str) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/trades/{tradeSpecifier}')
        )

    def close(self, accountID: str, tradeSpecifier: str, **kwargs) -> Response:
        return self.put(
            self.url(f'/accounts/{accountID}/trades/{tradeSpecifier}/close'),
            json=kwargs
        )

    def extensions(
        self, accountID: str, tradeSpecifier: str, **kwargs
    ) -> Response:
        return self.put(
            self.url((
                f'/accounts/{accountID}/trades/',
                f'{tradeSpecifier}/clientExtensions'
            )), json={'clientExtensions': kwargs}
        )

    def orders(
        self, accountID: str, tradeSpecifier: str, **kwargs
    ) -> Response:
        return self.put(
            self.url(f'/accounts/{accountID}/trades/{tradeSpecifier}/orders'),
            json=kwargs
        )


@moderate
@dataclass
@setcontext
class Position:
    context: Context

    def positions(self, accountID: str) -> Response:
        return self.get(self.url(f'/accounts/{accountID}/positions'))

    def openPositions(self, accountID: str) -> Response:
        return self.get(self.url(f'/accounts/{accountID}/openPositions'))

    def details(self, accountID: str, instrument: str) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/positions/{instrument}')
        )

    def close(self, accountID: str, instrument: str, **kwargs) -> Response:
        return self.put(
            self.url(f'/accounts/{accountID}/positions/{instrument}/close'),
            json=kwargs
        )


@moderate
@dataclass
@setcontext
class Transaction:
    context: Context

    def transactions(self, accountID: str, **kwargs) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/transactions'), params=kwargs
        )

    def details(self, accountID: str, transactionID: str) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/transactions/{transactionID}')
        )

    def idrange(
        self, accountID: str, since: str, until: str, *args
    ) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/transactions/idrange'),
            params={'from': since, 'to': until, 'type': args}
        )

    def sinceid(self, accountID: str, transactionID: str) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/transactions/sinceid'),
            params={'id': transactionID}
        )

    def stream(self, accountID: str) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/transactions/stream'),
            stream=True
        )


@moderate
@dataclass
@setcontext
class Pricing:
    context: Context

    def pricing(self, accountID: str, instruments: list, **kwargs) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/pricing'), params=dict(
                {'instruments': instruments}, **kwargs
            )
        )

    def stream(self, accountID: str, instruments: list, **kwargs) -> Response:
        return self.get(
            self.url(f'/accounts/{accountID}/pricing/stream'),
            params=dict({'instruments': instruments}, **kwargs),
            stream=True
        )


class AttributeDictionary(dict):
    """
    Makes dict keys accessible as object attributes with 'namespace' support
    Do not support keys equal to dict attribute names or non-supported
    attribute names(e.g. integers)

    {'first': [{'foo': '...'}, {'bar': '...'}]} -> obj.first[0].foo == '...'
    {'first': {'foo': 'bar'}} -> obj.first.foo == 'bar'
    {'items': '...'}, {'123': '...'} -> AttributeError
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
