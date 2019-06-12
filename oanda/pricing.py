from . import APIGroup, Response
from . import moderate, setcontext


@moderate
@setcontext
class Group(APIGroup):

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
