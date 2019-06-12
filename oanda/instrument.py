from . import APIGroup, Response
from . import moderate, setcontext


@moderate
@setcontext
class Group(APIGroup):

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
