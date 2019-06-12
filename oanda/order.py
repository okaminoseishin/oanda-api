from . import APIGroup, Response
from . import moderate, setcontext


@moderate
@setcontext
class Group(APIGroup):

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
