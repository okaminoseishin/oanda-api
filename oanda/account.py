from . import APIGroup, Response
from . import moderate, setcontext


@moderate
@setcontext
class Group(APIGroup):

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
            params={'instruments': ','.join(args)}
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
