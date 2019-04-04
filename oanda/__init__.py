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

    def path(self):
        return urlparse(self.response.url).path

    def clearpath(self):
        return re.sub(
            r'accounts/([^/]*)(\/|$)',
            lambda sub: sub.group(0).replace(sub.group(1), '<ACCOUNT>'),
            self.path()
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

        self.order = Order(self)
        self.trade = Trade(self)
        self.account = Account(self)
        self.pricing = Pricing(self)
        self.position = Position(self)
        self.instrument = Instrument(self)
        self.transaction = Transaction(self)

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
class Category:
    context: Context


@moderate
@setcontext
class Account(Category):

    def accounts(self) -> Response:
        """
        Get a list of all accounts authorized for the provided token.
        """
        return self.get(self.url('/accounts'))

    def details(self, accountID: str) -> Response:
        """
        Get the full details for a single account that a client has access to.

        Full pending order, open trade and open position representations are
        provided.

        Parameters
        ----------
            accountID: str
                Account identifier.
        """
        return self.get(self.url(f'/accounts/{accountID}'))

    def summary(self, accountID: str) -> Response:
        """
        Get a summary for a single account that a client has access to.

        Parameters
        ----------
            accountID: str
                Account identifier.
        """
        return self.get(self.url(f'/accounts/{accountID}/summary'))

    def instruments(self, accountID: str, *args) -> Response:
        """
        Get the list of tradeable instruments for the given account.

        The list of tradeable instruments is dependent on the regulatory
        division that the account is located in, thus should be the same for
        all accounts owned by a single user.

        Parameters
        ----------
            accountID: str
                Account identifier.

        Positional arguments
        --------------------
            List of instruments to query specifically.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/instruments'),
            params={'instruments': args}
        )

    def configuration(self, accountID: str, **kwargs) -> Response:
        """
        Set the client-configurable portions of an account.

        Parameters
        ----------
            accountID: str
                Account identifier.

        Keyword arguments
        -----------------
            alias: str
                Client-defined alias (name) for the account.
            marginRate: float
                Leverage for margin trading.
        """
        return self.patch(
            self.url(f'/accounts/{accountID}/configuration'), json=kwargs
        )

    def changes(self, accountID: str, transactionID: int) -> Response:
        """
        Endpoint used to poll an account for its current state and changes
        since a specified `transactionID`.

        Parameters
        ----------
            accountID: str
                Account identifier.
            transactionID: int
                ID of the transaction to get account changes since.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/changes'),
            params={'sinceTransactionID': transactionID}
        )


@moderate
@setcontext
class Instrument(Category):

    def candles(self, instrument: str, **kwargs) -> Response:
        """
        Fetch candlestick data for an `instrument`.

        Parameters
        ----------
            instrument: str
                Name of the instrument.

        Keyword arguments
        -----------------
            price: str
                The Price component(s) to get candlestick data for. Can
                contain any combination of the characters "M" (midpoint
                candles, default), "B" (bid candles) and "A" (ask candles).
            granularity: str
                The granularity of the candlesticks to fetch. "S5" by default.
            count: int
                The number of candlesticks to return in the reponse. Count
                should not be specified if both the start and end parameters
                are provided, as the time range combined with the graularity
                will determine the number of candlesticks to return.
                500 by default, maximum is 5000.
            since: str
                The start of the time range to fetch candlesticks for.
            until: str
                The end of the time range to fetch candlesticks for.
            smooth: bool
                A flag that controls whether the candlestick is "smoothed" or
                not. A smoothed candlestick uses the previous candle’s close
                price as its open price, while an unsmoothed candlestick uses
                the first price from its time range as its open price.
                False by default.
            includeFirst: bool
                A flag that controls whether the candlestick that is covered
                by the from time should be included in the results. This flag
                enables clients to use the timestamp of the last completed
                candlestick received to poll for future candlesticks but avoid
                receiving the previous candlestick repeatedly. True by default.
            dailyAlignment: int
                The hour of the day (in the specified timezone) to use for
                granularities that have daily alignments. From 0 to 23
                inclusive, 17 by default.
            alignmentTimezone: str
                The timezone to use for the dailyAlignment parameter.
                Candlesticks with daily alignment will be aligned to the
                dailyAlignment hour within the alignmentTimezone. Note that
                the returned times will still be represented in UTC.
                "America/New_York" by default.
            weeklyAlignment: str
                The day of the week used for granularities that have weekly
                alignment. "Friday" by default.
        """
        return self.get(
            self.url(f'/instruments/{instrument}/candles'), params=kwargs
        )

    def orderBook(self, instrument: str, time: str = None) -> Response:
        """
        Fetch an order book for an `instrument`.

        Parameters
        ----------
            instrument: str
                Name of the instrument.
            time: str, optional
                The time of the snapshot to fetch. If not specified, then the
                most recent snapshot is fetched.

        """
        return self.get(
            self.url(f'/instruments/{instrument}/orderBook'),
            params={'time': time}
        )

    def positionBook(self, instrument: str, time: str = None) -> Response:
        """
        Fetch a position book for an `instrument`.

        Parameters
        ----------
            instrument: str
                Name of the instrument.
            time: str, optional
                The time of the snapshot to fetch. If not specified, then the
                most recent snapshot is fetched.
        """
        return self.get(
            self.url(f'/instruments/{instrument}/positionBook'),
            params={'time': time}
        )


@moderate
@setcontext
class Order(Category):

    def create(self, accountID: str, **kwargs) -> Response:
        """
        Create an order for an account.

        Parameters
        ----------
            accountID: str
                Account identifier.

        Keyword arguments
        -----------------
            Order request parameters.

        See also
        --------
            Look at developer.oanda.com/rest-live-v20/order-df for
            order request parameters description.
        """
        return self.post(
            self.url(f'/accounts/{accountID}/orders'), json={'order': kwargs}
        )

    def orders(self, accountID: str, *args, **kwargs) -> Response:
        """
        Get a list of orders for an account.

        Parameters
        ----------
            accountID: str
                Account identifier.

        Positional arguments
        --------------------
            List of order IDs to retrieve.

        Keyword arguments
        -----------------
            state: str
                The state to filter the requested Orders by. May be
                "PENDING", "FILLED", "TRIGGERED", "CANCELLED" and "ALL".
                "PENDING" by default.
            instrument: str
                The instrument to filter the requested orders by.
            count: int
                The maximum number of Orders to return. 50 by default,
                maximum is 500.
            beforeID: int
                The maximum order ID to return. If not provided the most
                recent orders in the account are returned.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/orders'),
            params=dict({'ids': args}, **kwargs)
        )

    def pendingOrders(self, accountID: str) -> Response:
        """
        List all pending orders in an account.

        Parameters
        ----------
            accountID: str
                Account identifier.
        """
        return self.get(self.url(f'/accounts/{accountID}/pendingOrders'))

    def details(self, accountID: str, orderSpecifier: str) -> Response:
        """
        Get details for a single order in an account.

        Parameters
        ----------
            accountID: str
                Account identifier.
            orderSpecifier: str
                Either the order’s OANDA-assigned orderID or the order’s
                client-provided clientID prefixed by the “@” symbol.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/orders/{orderSpecifier}')
        )

    def replace(
        self, accountID: str, orderSpecifier: str, **kwargs
    ) -> Response:
        """
        Replace an order in an account by simultaneously cancelling it and
        creating a replacement order.

        Parameters
        ----------
            accountID: str
                Account identifier.
            orderSpecifier: str
                Either the order’s OANDA-assigned orderID or the order’s
                client-provided clientID prefixed by the “@” symbol.

        Keyword arguments
        -----------------
            Order request parameters.

        See also
        --------
            Look at developer.oanda.com/rest-live-v20/order-df for
            order request parameters description.
        """
        return self.put(
            self.url(f'/accounts/{accountID}/orders/{orderSpecifier}'),
            json={'order': kwargs}
        )

    def cancel(self, accountID: str, orderSpecifier: str) -> Response:
        """
        Cancel a pending order in an account.

        Parameters
        ----------
            accountID: str
                Account identifier.
            orderSpecifier: str
                Either the order’s OANDA-assigned orderID or the order’s
                client-provided clientID prefixed by the “@” symbol.
        """
        return self.put(
            self.url(f'/accounts/{accountID}/orders/{orderSpecifier}/cancel')
        )

    def extensions(
        self, accountID: str, orderSpecifier: str, **kwargs
    ) -> Response:
        """
        Update the client extensions for an order in an account.

        Parameters
        ----------
            accountID: str
                Account identifier.
            orderSpecifier: str
                Either the order’s OANDA-assigned orderID or the order’s
                client-provided clientID prefixed by the “@” symbol.

        Keyword arguments
        -----------------
            clientExtensions: dict
                The client extensions to update for the order.
            tradeClientExtensions: dict
                The client extensions to update for the trade created when the
                order is filled.

        Notes
        -----
            Extensions parameters:
                id: str, optional
                    The client ID of the order.
                tag: str, optional
                    A tag associated with the order.
                comment: str, optional
                    A comment associated with the order.

        Warning
        -------
            Do not set, modify, or delete client extensions if your account is
            associated with MT4.
        """
        return self.put(
            self.url((
                f'/accounts/{accountID}/orders/',
                f'{orderSpecifier}/clientExtensions'
            )), json=kwargs
        )


@moderate
@setcontext
class Trade(Category):

    def trades(self, accountID: str, *args, **kwargs) -> Response:
        """
        Get a list of trades for an account.

        Parameters
        ----------
            accountID: str
                Account identifier.

        Positional arguments
        --------------------
            List of trade IDs to retrieve.

        Keyword arguments
        -----------------
            state: str
                The state to filter the requested trades by. May be
                "OPEN", "CLOSED", "CLOSE_WHEN_TRADEABLE" and "ALL".
                "OPEN" by default.
            instrument: str
                The instrument to filter the requested trades by.
            count: int
                The maximum number of trades to return. 50 by default,
                maximum is 500.
            beforeID: int
                The maximum trade ID to return. If not provided the most
                recent trades in the account are returned.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/trades'),
            params=dict({'ids': args}, **kwargs)
        )

    def openTrades(self, accountID: str) -> Response:
        """
        Get the list of open trades for an account.

        Parameters
        ----------
            accountID: str
                Account identifier.
        """
        return self.get(self.url(f'/accounts/{accountID}/openTrades'))

    def details(self, accountID: str, tradeSpecifier: str) -> Response:
        """
        Get the details of a specific trade in an account.

        Parameters
        ----------
            accountID: str
                Account identifier.
            tradeSpecifier: str
                Either the trade’s OANDA-assigned tradeID or the trade’s
                client-provided clientID prefixed by the “@” symbol.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/trades/{tradeSpecifier}')
        )

    def close(
        self, accountID: str, tradeSpecifier: str, units: float = 'ALL'
    ) -> Response:
        """
        Close (partially or fully) a specific open trade in an account.

        Parameters
        ----------
            accountID: str
                Account identifier.
            tradeSpecifier: str
                Either the trade’s OANDA-assigned tradeID or the trade’s
                client-provided clientID prefixed by the “@” symbol.
            units: float, optional
                Representing the number of units of the open trade to close
                using a trade close market order. The units specified must
                always be positive, and the magnitude of the value cannot
                exceed the magnitude of the trade’s open units.
                Default is "ALL".
        """
        return self.put(
            self.url(f'/accounts/{accountID}/trades/{tradeSpecifier}/close'),
            json={'units': units}
        )

    def extensions(
        self, accountID: str, tradeSpecifier: str, **kwargs
    ) -> Response:
        """
        Update the client extensions for a trade.

        Parameters
        ----------
            accountID: str
                Account identifier.
            tradeSpecifier: str
                Either the trade’s OANDA-assigned tradeID or the trade’s
                client-provided clientID prefixed by the “@” symbol.

        Keyword arguments
        -----------------
            id: str
                The client ID of the trade.
            tag: str
                A tag associated with the trade.
            comment: str
                A comment associated with the trade.

        Warning
        -------
            Do not add, update, or delete the client extensions if your
            account is associated with MT4.
        """
        return self.put(
            self.url((
                f'/accounts/{accountID}/trades/',
                f'{tradeSpecifier}/clientExtensions'
            )), json={'clientExtensions': kwargs}
        )

    def orders(
        self, accountID: str, tradeSpecifier: str, **kwargs
    ) -> Response:
        """
        Create, replace and cancel a trade’s dependent orders (take profit,
        stop loss and trailing stop loss) through the trade itself.

        Parameters
        ----------
            accountID: str
                Account identifier.
            tradeSpecifier: str
                Either the trade’s OANDA-assigned tradeID or the trade’s
                client-provided clientID prefixed by the “@” symbol.

        Keyword arguments
        -----------------
            takeProfit: dict
                The specification of the take profit to create/modify/cancel.
            stopLoss: dict
                The specification of the stop loss to create/modify/cancel.
            trailingStopLoss: dict
                The specification of the trailing stop loss to create/modify/
                cancel.

        Notes
        -----
            If keyword argument is set to None, the relative order will be
            cancelled if it exists. If keyword argument is not provided, the
            exisiting relative order will not be modified. If a sub
            field of argument is not specified, that field will be set
            to a default value on create, and be inherited by the
            replacing order on modify.

            Look at developer.oanda.com/rest-live-v20/transaction-df for
            keyword arguments body details.
        """
        return self.put(
            self.url(f'/accounts/{accountID}/trades/{tradeSpecifier}/orders'),
            json=kwargs
        )


@moderate
@setcontext
class Position(Category):

    def positions(self, accountID: str) -> Response:
        """
        List all positions for an account.

        The positions returned are for every instrument that has had a
        position during the lifetime of an the account.

        Parameters
        ----------
            accountID: str
                Account identifier.
        """
        return self.get(self.url(f'/accounts/{accountID}/positions'))

    def openPositions(self, accountID: str) -> Response:
        """
        List all open positions for an account.

        An open position is a position in an account that currently has a
        trade opened for it.

        Parameters
        ----------
            accountID: str
                Account identifier.
        """
        return self.get(self.url(f'/accounts/{accountID}/openPositions'))

    def details(self, accountID: str, instrument: str) -> Response:
        """
        Get the details of a single instrument’s position in an account.
        The position may by open or not.

        Parameters
        ----------
            accountID: str
                Account identifier.
            instrument: str
                Name of the instrument.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/positions/{instrument}')
        )

    def close(self, accountID: str, instrument: str, **kwargs) -> Response:
        """
        Closeout the open position for a specific instrument in an account.

        Parameters
        ----------
            accountID: str
                Account identifier.
            instrument: str
                Name of the instrument.

        Keyword arguments
        -----------------
            longUnits: int
                Indication of how much of the long position to closeout.
            longClientExtensions: dict
                The client extensions to add to the market order used to
                close the long position.
            shortUnits: int
                Indication of how much of the short position to closeout.
            shortClientExtensions: dict
                The client extensions to add to the market order used to
                close the short position.

        See also
        --------
            Order.extensions
                longClientExtensions, shortClientExtensions value

        Notes
        -----
            longUnits, shortUnits value
                Either the string “ALL”, the string “NONE”, or a float
                representing how many units of the position to close using a
                position closeout market order. The units specified
                must always be positive. Default is "ALL".
        """
        return self.put(
            self.url(f'/accounts/{accountID}/positions/{instrument}/close'),
            json=kwargs
        )


@moderate
@setcontext
class Transaction(Category):

    def transactions(self, accountID: str, *args, **kwargs) -> Response:
        """
        Get a list of transactions pages that satisfy a time-based transaction
        query.

        Parameters
        ----------
            accountID: str
                Account identifier.

        Positional arguments
        --------------------
            A filter for restricting the types of transactions to retreive.

        Keyword arguments
        -----------------
            since: str
                The starting time (inclusive) of the time range for the
                transactions being queried. Account creation time by default.
            until: str
                The ending time (inclusive) of the time range for the
                transactions being queried. Request time by default.
            pageSize: int
                The number of transactions to include in each page of the
                results. 100 by default, maximum is 1000.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/transactions'),
            params=dict({'type': args}, **kwargs)
        )

    def details(self, accountID: str, transactionID: int) -> Response:
        """
        Get the details of a single account transaction.

        Parameters
        ----------
            accountID: str
                Account identifier.
            transactionID: int
                A transaction ID.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/transactions/{transactionID}')
        )

    def idrange(
        self, accountID: str, since: int, until: int, *args
    ) -> Response:
        """
        Get a range of transactions for an account based on the transaction
        IDs.

        Parameters
        ----------
            accountID: str
                Account identifier.
            since: int
                The starting transacion ID (inclusive) to fetch.
            until: int
                The ending transacion ID (inclusive) to fetch.

        Positional arguments
        --------------------
            The filter that restricts the types of transactions to retreive.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/transactions/idrange'),
            params={'from': since, 'to': until, 'type': args}
        )

    def sinceid(self, accountID: str, transactionID: int) -> Response:
        """
        Get a range of transactions for an account starting at (but not
        including) a provided transaction ID.

        Parameters
        ----------
            accountID: str
                Account identifier.
            transactionID: int
                A transaction ID.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/transactions/sinceid'),
            params={'id': transactionID}
        )

    def stream(self, accountID: str) -> Response:
        """
        Get a stream of transactions for an account starting from when the
        request is made.

        Parameters
        ----------
            accountID: str
                Account identifier.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/transactions/stream'),
            stream=True
        )


@moderate
@setcontext
class Pricing(Category):

    def pricing(
        self, accountID: str, *args, since: str = None, **kwargs
    ) -> Response:
        """
        Get pricing information for a specified list of instruments within an
        account.

        Parameters
        ----------
            accountID: str
                Account identifier.
            instrument: str
                Name of instrument to get pricing for.

        Positional arguments
        --------------------
            List of instruments to get pricing for. At least one is needed.

        Keyword-only arguments
        ----------------------
            since: str, optional
                DateTime filter to apply to the response. Only prices and
                home conversions(if requested) with a time later than this
                filter(i.e. the price has changed after the since time) will
                be provided, and are filtered independently.

        Keyword arguments
        -----------------
            includeHomeConversions: bool
                Flag that enables the inclusion of the homeConversions field
                in the returned response. An entry will be returned for each
                currency in the set of all base and quote currencies present
                in the requested instruments list. False by default.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/pricing'), params=dict(
                {'instruments': args, 'since': since}, **kwargs
            ))

    def stream(self, accountID: str, *args, snapshot: bool = True) -> Response:
        """
        Get a stream of account prices starting from when the request is made.

        This pricing stream does not include every single price created for
        the account, but instead will provide at most 4 prices per second
        (every 250 milliseconds) for each instrument being requested.
        If more than one price is created for an instrument during the 250
        millisecond window, only the price in effect at the end of the window
        is sent. This means that during periods of rapid price movement,
        subscribers to this stream will not be sent every price.
        Pricing windows for different connections to the price stream are not
        all aligned in the same way (i.e. they are not all aligned to the top
        of the second). This means that during periods of rapid price
        movement, different subscribers may observe different prices depending
        on their alignment.

        Parameters
        ----------
            accountID: str
                Account identifier.

        Positional arguments
        --------------------
            List of instruments to stream prices for. At least one is needed.

        Keyword-only arguments
        ----------------------
            snapshot: bool
                Flag that enables/disables the sending of a pricing snapshot
                when initially connecting to the stream. True by default.
        """
        return self.get(
            self.url(f'/accounts/{accountID}/pricing/stream'),
            params={'instruments': args, 'snapshot': snapshot}, stream=True
        )


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
