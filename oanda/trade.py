from . import APIGroup, Response
from . import moderate, setcontext


@moderate
@setcontext
class Group(APIGroup):

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
