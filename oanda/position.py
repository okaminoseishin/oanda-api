from . import APIGroup, Response
from . import moderate, setcontext


@moderate
@setcontext
class Group(APIGroup):

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
