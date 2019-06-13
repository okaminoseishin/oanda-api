from . import APIGroup, Response
from . import moderate, setcontext


@moderate
@setcontext
class Group(APIGroup):

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
            params=dict({'type': ','.join(args)}, **kwargs)
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
            params={'from': since, 'to': until, 'type': ','.join(args)}
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
