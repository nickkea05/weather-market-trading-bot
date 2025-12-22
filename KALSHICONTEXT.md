Python SDK Quick Start
Get started with the Kalshi Python SDK

​
Installation

Copy
pip install kalshi_python_sync
Or for async support:

Copy
pip install kalshi_python_async
The old kalshi-python package is deprecated. Please use kalshi_python_sync or kalshi_python_async instead.
​
Quick Start

Copy
from kalshi_python_sync import Configuration, KalshiClient

# Configure the client
config = Configuration(
    host="https://api.elections.kalshi.com/trade-api/v2"
)

# For authenticated requests
# Read private key from file
with open("path/to/private_key.pem", "r") as f:
    private_key = f.read()

config.api_key_id = "your-api-key-id"
config.private_key_pem = private_key

# Initialize the client
client = KalshiClient(config)

# Make API calls
balance = client.get_balance()
print(f"Balance: ${balance.balance / 100:.2f}")
​
Source Code
PyPI (sync): https://pypi.org/project/kalshi_python_sync/
PyPI (async): https://pypi.org/project/kalshi_python_async/

Portfolio
Python SDK methods for Portfolio operations

All URIs are relative to https://api.elections.kalshi.com/trade-api/v2
Method	HTTP request	Description
get_balance	GET /portfolio/balance	Get Balance
get_fills	GET /portfolio/fills	Get Fills
get_portfolio_resting_order_total_value	GET /portfolio/summary/total_resting_order_value	Get Total Resting Order Value
get_positions	GET /portfolio/positions	Get Positions
get_settlements	GET /portfolio/settlements	Get Settlements
​
get_balance
GetBalanceResponse get_balance()
Get Balance
Endpoint for getting the balance and portfolio value of a member. Both values are returned in cents.
​
Parameters
This endpoint does not need any parameter.
​
Return type
GetBalanceResponse
​
HTTP response details
Status code	Description
200	Balance retrieved successfully
401	Unauthorized - authentication required
500	Internal server error
​
get_fills
GetFillsResponse get_fills(ticker=ticker, order_id=order_id, min_ts=min_ts, max_ts=max_ts, limit=limit, cursor=cursor)
Get Fills
Endpoint for getting all fills for the member. A fill is when a trade you have is matched.
​
Parameters
Name	Type	Description	Notes
ticker	str	Filter by market ticker	[optional]
order_id	str	Filter by order ID	[optional]
min_ts	int	Filter items after this Unix timestamp	[optional]
max_ts	int	Filter items before this Unix timestamp	[optional]
limit	int	Number of results per page. Defaults to 100. Maximum value is 200.	[optional] [default to 100]
cursor	str	Pagination cursor. Use the cursor value returned from the previous response to get the next page of results. Leave empty for the first page.	[optional]
​
Return type
GetFillsResponse
​
HTTP response details
Status code	Description
200	Fills retrieved successfully
400	Bad request
401	Unauthorized
500	Internal server error
​
get_portfolio_resting_order_total_value
GetPortfolioRestingOrderTotalValueResponse get_portfolio_resting_order_total_value()
Get Total Resting Order Value
Endpoint for getting the total value, in cents, of resting orders. This endpoint is only intended for use by FCM members (rare). Note: If you’re uncertain about this endpoint, it likely does not apply to you.
​
Parameters
This endpoint does not need any parameter.
​
Return type
GetPortfolioRestingOrderTotalValueResponse
​
HTTP response details
Status code	Description
200	Total resting order value retrieved successfully
401	Unauthorized - authentication required
500	Internal server error
​
get_positions
GetPositionsResponse get_positions(cursor=cursor, limit=limit, count_filter=count_filter, settlement_status=settlement_status, ticker=ticker, event_ticker=event_ticker)
Get Positions
Restricts the positions to those with any of following fields with non-zero values, as a comma separated list. The following values are accepted: position, total_traded
​
Parameters
Name	Type	Description	Notes
cursor	str	The Cursor represents a pointer to the next page of records in the pagination. Use the value returned from the previous response to get the next page.	[optional]
limit	int	Parameter to specify the number of results per page. Defaults to 100.	[optional] [default to 100]
count_filter	str	Restricts the positions to those with any of following fields with non-zero values, as a comma separated list. The following values are accepted - position, total_traded	[optional]
settlement_status	str	Settlement status of the markets to return. Defaults to unsettled.	[optional] [default to unsettled]
ticker	str	Filter by market ticker	[optional]
event_ticker	str	Event ticker of desired positions. Multiple event tickers can be provided as a comma-separated list (maximum 10).	[optional]
​
Return type
GetPositionsResponse
​
HTTP response details
Status code	Description
200	Positions retrieved successfully
400	Bad request - invalid input
401	Unauthorized - authentication required
500	Internal server error
​
get_settlements
GetSettlementsResponse get_settlements(limit=limit, cursor=cursor, ticker=ticker, event_ticker=event_ticker, min_ts=min_ts, max_ts=max_ts)
Get Settlements
Endpoint for getting the member’s settlements historical track.
​
Parameters
Name	Type	Description	Notes
limit	int	Number of results per page. Defaults to 100. Maximum value is 200.	[optional] [default to 100]
cursor	str	Pagination cursor. Use the cursor value returned from the previous response to get the next page of results. Leave empty for the first page.	[optional]
ticker	str	Filter by market ticker	[optional]
event_ticker	str	Event ticker of desired positions. Multiple event tickers can be provided as a comma-separated list (maximum 10).	[optional]
min_ts	int	Filter items after this Unix timestamp	[optional]
max_ts	int	Filter items before this Unix timestamp	[optional]
​
Return type
GetSettlementsResponse
​
HTTP response details
Status code	Description
200	Settlements retrieved successfully
400	Bad request - invalid input
401	Unauthorized - authentication required
500	Internal server error

Markets
Python SDK methods for Markets operations

All URIs are relative to https://api.elections.kalshi.com/trade-api/v2
Method	HTTP request	Description
get_market	GET /markets/	Get Market
get_market_candlesticks	GET /series//markets//candlesticks	Get Market Candlesticks
get_market_orderbook	GET /markets//orderbook	Get Market Orderbook
get_markets	GET /markets	Get Markets
get_trades	GET /markets/trades	Get Trades
​
get_market
GetMarketResponse get_market(ticker)
Get Market
Get a single market by its ticker.
A market represents a specific binary outcome within an event that users can trade on (e.g., “Will candidate X win?”). Markets have yes/no positions, current prices, volume, and settlement rules.
​
Example

Copy
import kalshi_python
from kalshi_python.models.get_market_response import GetMarketResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)

# Read private key from file
with open('path/to/private_key.pem', 'r') as f:
    private_key = f.read()

# Configure API key authentication
configuration.api_key_id = "your-api-key-id"
configuration.private_key_pem = private_key

# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

ticker = 'ticker_example' # str | Market ticker

try:
    # Get Market
    api_response = client.get_market(ticker)
    print("The response of MarketsApi->get_market:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling MarketsApi->get_market: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
ticker	str	Market ticker	
​
Return type
GetMarketResponse
​
HTTP response details
Status code	Description
200	Market retrieved successfully
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error
[Back to top] [Back to API list] [Back to Model list] [Back to README]
​
get_market_candlesticks
GetMarketCandlesticksResponse get_market_candlesticks(ticker, market_ticker, start_ts=start_ts, end_ts=end_ts, period_interval=period_interval)
Get Market Candlesticks
Get candlestick data for a market within a series
​
Example

Copy
import kalshi_python
from kalshi_python.models.get_market_candlesticks_response import GetMarketCandlesticksResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)

# Read private key from file
with open('path/to/private_key.pem', 'r') as f:
    private_key = f.read()

# Configure API key authentication
configuration.api_key_id = "your-api-key-id"
configuration.private_key_pem = private_key

# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

ticker = 'ticker_example' # str | The series ticker

market_ticker = 'market_ticker_example' # str | The market ticker

start_ts = 56 # int | Start timestamp for the range (optional)

end_ts = 56 # int | End timestamp for the range (optional)

period_interval = 'period_interval_example' # str | Period interval for candlesticks (e.g., 1m, 5m, 1h, 1d) (optional)

try:
    # Get Market Candlesticks
    api_response = client.get_market_candlesticks(ticker, market_ticker, start_ts=start_ts, end_ts=end_ts, period_interval=period_interval)
    print("The response of MarketsApi->get_market_candlesticks:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling MarketsApi->get_market_candlesticks: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
ticker	str	The series ticker	
market_ticker	str	The market ticker	
start_ts	int	Start timestamp for the range	[optional]
end_ts	int	End timestamp for the range	[optional]
period_interval	str	Period interval for candlesticks (e.g., 1m, 5m, 1h, 1d)	[optional]
​
Return type
GetMarketCandlesticksResponse
​
HTTP response details
Status code	Description
200	Candlesticks retrieved successfully
400	Bad request - invalid input
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error
[Back to top] [Back to API list] [Back to Model list] [Back to README]
​
get_market_orderbook
GetMarketOrderbookResponse get_market_orderbook(ticker, depth=depth)
Get Market Orderbook
Get the orderbook for a market
​
Example

Copy
import kalshi_python
from kalshi_python.models.get_market_orderbook_response import GetMarketOrderbookResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)

# Read private key from file
with open('path/to/private_key.pem', 'r') as f:
    private_key = f.read()

# Configure API key authentication
configuration.api_key_id = "your-api-key-id"
configuration.private_key_pem = private_key

# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

ticker = 'ticker_example' # str | Market ticker

depth = 10 # int | Depth of the orderbook to retrieve (optional) (default to 10)

try:
    # Get Market Orderbook
    api_response = client.get_market_orderbook(ticker, depth=depth)
    print("The response of MarketsApi->get_market_orderbook:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling MarketsApi->get_market_orderbook: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
ticker	str	Market ticker	
depth	int	Depth of the orderbook to retrieve	[optional] [default to 10]
​
Return type
GetMarketOrderbookResponse
​
HTTP response details
Status code	Description
200	Orderbook retrieved successfully
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error
[Back to top] [Back to API list] [Back to Model list] [Back to README]
​
get_markets
GetMarketsResponse get_markets(limit=limit, cursor=cursor, event_ticker=event_ticker, series_ticker=series_ticker, max_close_ts=max_close_ts, min_close_ts=min_close_ts, status=status, tickers=tickers)
Get Markets
List and discover markets on Kalshi.
A market represents a specific binary outcome within an event that users can trade on (e.g., “Will candidate X win?”). Markets have yes/no positions, current prices, volume, and settlement rules.
This endpoint returns a paginated response. Use the ‘limit’ parameter to control page size (1-1000, defaults to 100). The response includes a ‘cursor’ field - pass this value in the ‘cursor’ parameter of your next request to get the next page. An empty cursor indicates no more pages are available.
​
Example

Copy
import kalshi_python
from kalshi_python.models.get_markets_response import GetMarketsResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)

# Read private key from file
with open('path/to/private_key.pem', 'r') as f:
    private_key = f.read()

# Configure API key authentication
configuration.api_key_id = "your-api-key-id"
configuration.private_key_pem = private_key

# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

limit = 100 # int | Number of results per page. Defaults to 100. Maximum value is 1000. (optional) (default to 100)

cursor = 'cursor_example' # str | Pagination cursor. Use the cursor value returned from the previous response to get the next page of results. Leave empty for the first page. (optional)

event_ticker = 'event_ticker_example' # str | Filter by event ticker (optional)

series_ticker = 'series_ticker_example' # str | Filter by series ticker (optional)

max_close_ts = 56 # int | Filter items that close before this Unix timestamp (optional)

min_close_ts = 56 # int | Filter items that close after this Unix timestamp (optional)

status = 'status_example' # str | Filter by market status. Comma-separated list. Possible values are 'initialized', 'open', 'closed', 'settled', 'determined'. Note that the API accepts 'open' for filtering but returns 'active' in the response. Leave empty to return markets with any status. (optional)

tickers = 'tickers_example' # str | Filter by specific market tickers. Comma-separated list of market tickers to retrieve. (optional)

try:
    # Get Markets
    api_response = client.get_markets(limit=limit, cursor=cursor, event_ticker=event_ticker, series_ticker=series_ticker, max_close_ts=max_close_ts, min_close_ts=min_close_ts, status=status, tickers=tickers)
    print("The response of MarketsApi->get_markets:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling MarketsApi->get_markets: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
limit	int	Number of results per page. Defaults to 100. Maximum value is 1000.	[optional] [default to 100]
cursor	str	Pagination cursor. Use the cursor value returned from the previous response to get the next page of results. Leave empty for the first page.	[optional]
event_ticker	str	Filter by event ticker	[optional]
series_ticker	str	Filter by series ticker	[optional]
max_close_ts	int	Filter items that close before this Unix timestamp	[optional]
min_close_ts	int	Filter items that close after this Unix timestamp	[optional]
status	str	Filter by market status. Comma-separated list. Possible values are ‘initialized’, ‘open’, ‘closed’, ‘settled’, ‘determined’. Note that the API accepts ‘open’ for filtering but returns ‘active’ in the response. Leave empty to return markets with any status.	[optional]
tickers	str	Filter by specific market tickers. Comma-separated list of market tickers to retrieve.	[optional]
​
Return type
GetMarketsResponse
​
HTTP response details
Status code	Description
200	Markets retrieved successfully
400	Bad request - invalid input
401	Unauthorized - authentication required
500	Internal server error
[Back to top] [Back to API list] [Back to Model list] [Back to README]
​
get_trades
GetTradesResponse get_trades(limit=limit, cursor=cursor, ticker=ticker, min_ts=min_ts, max_ts=max_ts)
Get Trades
Get all trades for all markets.
A trade represents a completed transaction between two users on a specific market. Each trade includes the market ticker, price, quantity, and timestamp information.
This endpoint returns a paginated response. Use the ‘limit’ parameter to control page size (1-1000, defaults to 100). The response includes a ‘cursor’ field - pass this value in the ‘cursor’ parameter of your next request to get the next page. An empty cursor indicates no more pages are available.
​
Example

Copy
import kalshi_python
from kalshi_python.models.get_trades_response import GetTradesResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)


# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

limit = 100 # int | Number of results per page. Defaults to 100. Maximum value is 1000. (optional) (default to 100)

cursor = 'cursor_example' # str | Pagination cursor. Use the cursor value returned from the previous response to get the next page of results. Leave empty for the first page. (optional)

ticker = 'ticker_example' # str | Filter by market ticker (optional)

min_ts = 56 # int | Filter items after this Unix timestamp (optional)

max_ts = 56 # int | Filter items before this Unix timestamp (optional)

try:
    # Get Trades
    api_response = client.get_trades(limit=limit, cursor=cursor, ticker=ticker, min_ts=min_ts, max_ts=max_ts)
    print("The response of MarketsApi->get_trades:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling MarketsApi->get_trades: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
limit	int	Number of results per page. Defaults to 100. Maximum value is 1000.	[optional] [default to 100]
cursor	str	Pagination cursor. Use the cursor value returned from the previous response to get the next page of results. Leave empty for the first page.	[optional]
ticker	str	Filter by market ticker	[optional]
min_ts	int	Filter items after this Unix timestamp	[optional]
max_ts	int	Filter items before this Unix timestamp	[optional]
​
Return type
GetTradesResponse
​
HTTP response details
Status code	Description
200	Trades retrieved successfully
400	Bad request - invalid input
500	Internal server error

Communications
Python SDK methods for Communications operations

All URIs are relative to https://api.elections.kalshi.com/trade-api/v2
Method	HTTP request	Description
accept_quote	PUT /communications/quotes//accept	Accept Quote
confirm_quote	PUT /communications/quotes//confirm	Confirm Quote
create_quote	POST /communications/quotes	Create Quote
create_rfq	POST /communications/rfqs	Create RFQ
delete_quote	DELETE /communications/quotes/	Delete Quote
delete_rfq	DELETE /communications/rfqs/	Delete RFQ
get_communications_id	GET /communications/id	Get Communications ID
get_quote	GET /communications/quotes/	Get Quote
get_quotes	GET /communications/quotes	Get Quotes
get_rfq	GET /communications/rfqs/	Get RFQ
get_rfqs	GET /communications/rfqs	Get RFQs
​
accept_quote
accept_quote(quote_id, accept_quote_request)
Accept Quote
Endpoint for accepting a quote. This will require the quoter to confirm
​
Parameters
Name	Type	Description	Notes
quote_id	str	Quote ID	
accept_quote_request	AcceptQuoteRequest		
​
Return type
void (empty response body)
​
HTTP response details
Status code	Description
204	Quote accepted successfully
400	Bad request - invalid input
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error
​
confirm_quote
confirm_quote(quote_id, body=body)
Confirm Quote
Endpoint for confirming a quote. This will start a timer for order execution
​
Parameters
Name	Type	Description	Notes
quote_id	str	Quote ID	
body	object		[optional]
​
Return type
void (empty response body)
​
HTTP response details
Status code	Description
204	Quote confirmed successfully
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error
​
create_quote
CreateQuoteResponse create_quote(create_quote_request)
Create Quote
Endpoint for creating a quote in response to an RFQ
​
Parameters
Name	Type	Description	Notes
create_quote_request	CreateQuoteRequest		
​
Return type
CreateQuoteResponse
​
HTTP response details
Status code	Description
201	Quote created successfully
400	Bad request - invalid input
401	Unauthorized - authentication required
500	Internal server error
​
create_rfq
CreateRFQResponse create_rfq(create_rfq_request)
Create RFQ
Endpoint for creating a new RFQ. You can have a maximum of 100 open RFQs at a time.
​
Parameters
Name	Type	Description	Notes
create_rfq_request	CreateRFQRequest		
​
Return type
CreateRFQResponse
​
HTTP response details
Status code	Description
201	RFQ created successfully
400	Bad request - invalid input
401	Unauthorized - authentication required
409	Conflict - resource already exists or cannot be modified
500	Internal server error
​
delete_quote
delete_quote(quote_id)
Delete Quote
Endpoint for deleting a quote, which means it can no longer be accepted.
​
Parameters
Name	Type	Description	Notes
quote_id	str	Quote ID	
​
Return type
void (empty response body)
​
HTTP response details
Status code	Description
204	Quote deleted successfully
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error
​
delete_rfq
delete_rfq(rfq_id)
Delete RFQ
Endpoint for deleting an RFQ by ID
​
Parameters
Name	Type	Description	Notes
rfq_id	str	RFQ ID	
​
Return type
void (empty response body)
​
HTTP response details
Status code	Description
204	RFQ deleted successfully
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error
​
get_communications_id
GetCommunicationsIDResponse get_communications_id()
Get Communications ID
Endpoint for getting the communications ID of the logged-in user.
​
Parameters
This endpoint does not need any parameter.
​
Return type
GetCommunicationsIDResponse
​
HTTP response details
Status code	Description
200	Communications ID retrieved successfully
401	Unauthorized - authentication required
500	Internal server error
​
get_quote
GetQuoteResponse get_quote(quote_id)
Get Quote
Endpoint for getting a particular quote
​
Parameters
Name	Type	Description	Notes
quote_id	str	Quote ID	
​
Return type
GetQuoteResponse
​
HTTP response details
Status code	Description
200	Quote retrieved successfully
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error
​
get_quotes
GetQuotesResponse get_quotes(cursor=cursor, event_ticker=event_ticker, market_ticker=market_ticker, limit=limit, status=status, quote_creator_user_id=quote_creator_user_id, rfq_creator_user_id=rfq_creator_user_id, rfq_creator_subtrader_id=rfq_creator_subtrader_id, rfq_id=rfq_id)
Get Quotes
Endpoint for getting quotes
​
Parameters
Name	Type	Description	Notes
cursor	str	Pagination cursor. Use the cursor value returned from the previous response to get the next page of results. Leave empty for the first page.	[optional]
event_ticker	str	Event ticker of desired positions. Multiple event tickers can be provided as a comma-separated list (maximum 10).	[optional]
market_ticker	str	Filter by market ticker	[optional]
limit	int	Parameter to specify the number of results per page. Defaults to 500.	[optional] [default to 500]
status	str	Filter quotes by status	[optional]
quote_creator_user_id	str	Filter quotes by quote creator user ID	[optional]
rfq_creator_user_id	str	Filter quotes by RFQ creator user ID	[optional]
rfq_creator_subtrader_id	str	Filter quotes by RFQ creator subtrader ID (FCM members only)	[optional]
rfq_id	str	Filter quotes by RFQ ID	[optional]
​
Return type
GetQuotesResponse
​
HTTP response details
Status code	Description
200	Quotes retrieved successfully
401	Unauthorized - authentication required
500	Internal server error
​
get_rfq
GetRFQResponse get_rfq(rfq_id)
Get RFQ
Endpoint for getting a single RFQ by id
​
Parameters
Name	Type	Description	Notes
rfq_id	str	RFQ ID	
​
Return type
GetRFQResponse
​
HTTP response details
Status code	Description
200	RFQ retrieved successfully
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error
​
get_rfqs
GetRFQsResponse get_rfqs(cursor=cursor, event_ticker=event_ticker, market_ticker=market_ticker, limit=limit, status=status, creator_user_id=creator_user_id)
Get RFQs
Endpoint for getting RFQs
​
Parameters
Name	Type	Description	Notes
cursor	str	Pagination cursor. Use the cursor value returned from the previous response to get the next page of results. Leave empty for the first page.	[optional]
event_ticker	str	Event ticker of desired positions. Multiple event tickers can be provided as a comma-separated list (maximum 10).	[optional]
market_ticker	str	Filter by market ticker	[optional]
limit	int	Parameter to specify the number of results per page. Defaults to 100.	[optional] [default to 100]
status	str	Filter RFQs by status	[optional]
creator_user_id	str	Filter RFQs by creator user ID	[optional]
​
Return type
GetRFQsResponse
​
HTTP response details
Status code	Description
200	RFQs retrieved successfully
401	Unauthorized - authentication required
500	Internal server error

Events
Python SDK methods for Events operations

All URIs are relative to https://api.elections.kalshi.com/trade-api/v2
Method	HTTP request	Description
get_event	GET /events/	Get Event
get_event_forecast_percentiles_history	GET /series//events//forecast_percentile_history	Get Event Forecast Percentile History
get_event_metadata	GET /events//metadata	Get Event Metadata
get_events	GET /events	Get Events
get_market_candlesticks_by_event	GET /series//events//candlesticks	Get Event Candlesticks
get_multivariate_events	GET /events/multivariate	Get Multivariate Events
​
get_event
GetEventResponse get_event(event_ticker, with_nested_markets=with_nested_markets)
Get Event
Endpoint for getting data about an event by its ticker. An event represents a real-world occurrence that can be traded on, such as an election, sports game, or economic indicator release. Events contain one or more markets where users can place trades on different outcomes.
​
Parameters
Name	Type	Description	Notes
event_ticker	str	Event ticker	
with_nested_markets	bool	If true, markets are included within the event object. If false (default), markets are returned as a separate top-level field in the response.	[optional] [default to False]
​
Return type
GetEventResponse
​
HTTP response details
Status code	Description
200	Event retrieved successfully
400	Bad request
404	Event not found
401	Unauthorized
500	Internal server error
​
get_event_forecast_percentiles_history
GetEventForecastPercentilesHistoryResponse get_event_forecast_percentiles_history(ticker, series_ticker, percentiles, start_ts, end_ts, period_interval)
Get Event Forecast Percentile History
Endpoint for getting the historical raw and formatted forecast numbers for an event at specific percentiles.
​
Parameters
Name	Type	Description	Notes
ticker	str	The event ticker	
series_ticker	str	The series ticker	
percentiles	List[int]	Array of percentile values to retrieve (0-10000, max 10 values)	
start_ts	int	Start timestamp for the range	
end_ts	int	End timestamp for the range	
period_interval	int	Specifies the length of each forecast period, in minutes. 0 for 5-second intervals, or 1, 60, or 1440 for minute-based intervals.	
​
Return type
GetEventForecastPercentilesHistoryResponse
​
HTTP response details
Status code	Description
200	Event forecast percentile history retrieved successfully
400	Bad request
401	Unauthorized
500	Internal server error
​
get_event_metadata
GetEventMetadataResponse get_event_metadata(event_ticker)
Get Event Metadata
Endpoint for getting metadata about an event by its ticker. Returns only the metadata information for an event.
​
Parameters
Name	Type	Description	Notes
event_ticker	str	Event ticker	
​
Return type
GetEventMetadataResponse
​
HTTP response details
Status code	Description
200	Event metadata retrieved successfully
400	Bad request
404	Event not found
401	Unauthorized
500	Internal server error
​
get_events
GetEventsResponse get_events(limit=limit, cursor=cursor, with_nested_markets=with_nested_markets, with_milestones=with_milestones, status=status, series_ticker=series_ticker, min_close_ts=min_close_ts)
Get Events
Filter by event status. Possible values: ‘open’, ‘closed’, ‘settled’. Leave empty to return events with any status.
​
Parameters
Name	Type	Description	Notes
limit	int	Parameter to specify the number of results per page. Defaults to 200. Maximum value is 200.	[optional] [default to 200]
cursor	str	Parameter to specify the pagination cursor. Use the cursor value returned from the previous response to get the next page of results. Leave empty for the first page.	[optional]
with_nested_markets	bool	Parameter to specify if nested markets should be included in the response. When true, each event will include a ‘markets’ field containing a list of Market objects associated with that event.	[optional] [default to False]
with_milestones	bool	If true, includes related milestones as a field alongside events.	[optional] [default to False]
status	str	Filter by event status. Possible values are ‘open’, ‘closed’, ‘settled’. Leave empty to return events with any status.	[optional]
series_ticker	str	Filter by series ticker	[optional]
min_close_ts	int	Filter events with at least one market with close timestamp greater than this Unix timestamp (in seconds).	[optional]
​
Return type
GetEventsResponse
​
HTTP response details
Status code	Description
200	Events retrieved successfully
400	Bad request
401	Unauthorized
500	Internal server error
​
get_market_candlesticks_by_event
GetEventCandlesticksResponse get_market_candlesticks_by_event(ticker, series_ticker, start_ts, end_ts, period_interval)
Get Event Candlesticks
End-point for returning aggregated data across all markets corresponding to an event.
​
Parameters
Name	Type	Description	Notes
ticker	str	The event ticker	
series_ticker	str	The series ticker	
start_ts	int	Start timestamp for the range	
end_ts	int	End timestamp for the range	
period_interval	int	Specifies the length of each candlestick period, in minutes. Must be one minute, one hour, or one day.	
​
Return type
GetEventCandlesticksResponse
​
HTTP response details
Status code	Description
200	Event candlesticks retrieved successfully
400	Bad request
401	Unauthorized
500	Internal server error
​
get_multivariate_events
GetMultivariateEventsResponse get_multivariate_events(limit=limit, cursor=cursor, series_ticker=series_ticker, collection_ticker=collection_ticker, with_nested_markets=with_nested_markets)
Get Multivariate Events
Retrieve multivariate (combo) events. These are dynamically created events from multivariate event collections. Supports filtering by series and collection ticker.
​
Parameters
Name	Type	Description	Notes
limit	int	Number of results per page. Defaults to 100. Maximum value is 200.	[optional] [default to 100]
cursor	str	Pagination cursor. Use the cursor value returned from the previous response to get the next page of results.	[optional]
series_ticker	str	Filter by series ticker	[optional]
collection_ticker	str	Filter events by collection ticker. Returns only multivariate events belonging to the specified collection. Cannot be used together with series_ticker.	[optional]
with_nested_markets	bool	Parameter to specify if nested markets should be included in the response. When true, each event will include a ‘markets’ field containing a list of Market objects associated with that event.	[optional] [default to False]
​
Return type
GetMultivariateEventsResponse
​
HTTP response details
Status code	Description
200	Multivariate events retrieved successfully
400	Bad request - invalid parameters
401	Unauthorized
500	Internal server error

Series
Python SDK methods for Series operations

All URIs are relative to https://api.elections.kalshi.com/trade-api/v2
Method	HTTP request	Description
get_series	GET /series	Get Series
get_series_by_ticker	GET /series/	Get Series by Ticker
​
get_series
GetSeriesResponse get_series(status=status)
Get Series
Get all market series
​
Example

Copy
import kalshi_python
from kalshi_python.models.get_series_response import GetSeriesResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)

# Read private key from file
with open('path/to/private_key.pem', 'r') as f:
    private_key = f.read()

# Configure API key authentication
configuration.api_key_id = "your-api-key-id"
configuration.private_key_pem = private_key

# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

status = 'status_example' # str | Filter by series status (optional)

try:
    # Get Series
    api_response = client.get_series(status=status)
    print("The response of SeriesApi->get_series:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling SeriesApi->get_series: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
status	str	Filter by series status	[optional]
​
Return type
GetSeriesResponse
​
HTTP response details
Status code	Description
200	Series retrieved successfully
401	Unauthorized - authentication required
500	Internal server error
[Back to top] [Back to API list] [Back to Model list] [Back to README]
​
get_series_by_ticker
GetSeriesByTickerResponse get_series_by_ticker(ticker)
Get Series by Ticker
Get a single series by its ticker
​
Example

Copy
import kalshi_python
from kalshi_python.models.get_series_by_ticker_response import GetSeriesByTickerResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)

# Read private key from file
with open('path/to/private_key.pem', 'r') as f:
    private_key = f.read()

# Configure API key authentication
configuration.api_key_id = "your-api-key-id"
configuration.private_key_pem = private_key

# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

ticker = 'ticker_example' # str | The series ticker

try:
    # Get Series by Ticker
    api_response = client.get_series_by_ticker(ticker)
    print("The response of SeriesApi->get_series_by_ticker:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling SeriesApi->get_series_by_ticker: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
ticker	str	The series ticker	
​
Return type
GetSeriesByTickerResponse
​
HTTP response details
Status code	Description
200	Series retrieved successfully
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error

Milestones
Python SDK methods for Milestones operations

All URIs are relative to https://api.elections.kalshi.com/trade-api/v2
Method	HTTP request	Description
get_milestone	GET /milestones/	Get Milestone
get_milestones	GET /milestones	Get Milestones
​
get_milestone
GetMilestoneResponse get_milestone(milestone_id)
Get Milestone
Get a single milestone by ID
​
Example

Copy
import kalshi_python
from kalshi_python.models.get_milestone_response import GetMilestoneResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)

# Read private key from file
with open('path/to/private_key.pem', 'r') as f:
    private_key = f.read()

# Configure API key authentication
configuration.api_key_id = "your-api-key-id"
configuration.private_key_pem = private_key

# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

milestone_id = 'milestone_id_example' # str | Milestone ID

try:
    # Get Milestone
    api_response = client.get_milestone(milestone_id)
    print("The response of MilestonesApi->get_milestone:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling MilestonesApi->get_milestone: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
milestone_id	str	Milestone ID	
​
Return type
GetMilestoneResponse
​
HTTP response details
Status code	Description
200	Milestone retrieved successfully
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error
[Back to top] [Back to API list] [Back to Model list] [Back to README]
​
get_milestones
GetMilestonesResponse get_milestones(status=status, limit=limit)
Get Milestones
Get all milestones
​
Example

Copy
import kalshi_python
from kalshi_python.models.get_milestones_response import GetMilestonesResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)

# Read private key from file
with open('path/to/private_key.pem', 'r') as f:
    private_key = f.read()

# Configure API key authentication
configuration.api_key_id = "your-api-key-id"
configuration.private_key_pem = private_key

# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

status = 'status_example' # str | Filter by milestone status (optional)

limit = 100 # int | Number of items per page (minimum 1, maximum 500) (optional) (default to 100)

try:
    # Get Milestones
    api_response = client.get_milestones(status=status, limit=limit)
    print("The response of MilestonesApi->get_milestones:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling MilestonesApi->get_milestones: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
status	str	Filter by milestone status	[optional]
limit	int	Number of items per page (minimum 1, maximum 500)	[optional] [default to 100]
​
Return type
GetMilestonesResponse
​
HTTP response details
Status code	Description
200	Milestones retrieved successfully
401	Unauthorized - authentication required
500	Internal server error

MultivariateCollections
Python SDK methods for MultivariateCollections operations

All URIs are relative to https://api.elections.kalshi.com/trade-api/v2
Method	HTTP request	Description
get_multivariate_event_collection	GET /multivariate_event_collections/	Get Multivariate Event Collection
get_multivariate_event_collections	GET /multivariate_event_collections	Get Multivariate Event Collections
lookup_multivariate_event_collection_bundle	POST /multivariate_event_collections//lookup	Lookup Multivariate Event Collection Bundle
​
get_multivariate_event_collection
GetMultivariateEventCollectionResponse get_multivariate_event_collection(collection_ticker)
Get Multivariate Event Collection
Get a single multivariate event collection by ticker
​
Example

Copy
import kalshi_python
from kalshi_python.models.get_multivariate_event_collection_response import GetMultivariateEventCollectionResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)

# Read private key from file
with open('path/to/private_key.pem', 'r') as f:
    private_key = f.read()

# Configure API key authentication
configuration.api_key_id = "your-api-key-id"
configuration.private_key_pem = private_key

# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

collection_ticker = 'collection_ticker_example' # str | Collection ticker

try:
    # Get Multivariate Event Collection
    api_response = client.get_multivariate_event_collection(collection_ticker)
    print("The response of MultivariateCollectionsApi->get_multivariate_event_collection:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling MultivariateCollectionsApi->get_multivariate_event_collection: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
collection_ticker	str	Collection ticker	
​
Return type
GetMultivariateEventCollectionResponse
​
HTTP response details
Status code	Description
200	Collection retrieved successfully
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error
[Back to top] [Back to API list] [Back to Model list] [Back to README]
​
get_multivariate_event_collections
GetMultivariateEventCollectionsResponse get_multivariate_event_collections(status=status)
Get Multivariate Event Collections
Get all multivariate event collections
​
Example

Copy
import kalshi_python
from kalshi_python.models.get_multivariate_event_collections_response import GetMultivariateEventCollectionsResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)

# Read private key from file
with open('path/to/private_key.pem', 'r') as f:
    private_key = f.read()

# Configure API key authentication
configuration.api_key_id = "your-api-key-id"
configuration.private_key_pem = private_key

# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

status = 'status_example' # str | Filter by multivariate collection status (optional)

try:
    # Get Multivariate Event Collections
    api_response = client.get_multivariate_event_collections(status=status)
    print("The response of MultivariateCollectionsApi->get_multivariate_event_collections:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling MultivariateCollectionsApi->get_multivariate_event_collections: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
status	str	Filter by multivariate collection status	[optional]
​
Return type
GetMultivariateEventCollectionsResponse
​
HTTP response details
Status code	Description
200	Collections retrieved successfully
401	Unauthorized - authentication required
500	Internal server error
[Back to top] [Back to API list] [Back to Model list] [Back to README]
​
lookup_multivariate_event_collection_bundle
LookupBundleResponse lookup_multivariate_event_collection_bundle(collection_ticker, lookup_bundle_request)
Lookup Multivariate Event Collection Bundle
Lookup a bundle in a multivariate event collection
​
Example

Copy
import kalshi_python
from kalshi_python.models.lookup_bundle_request import LookupBundleRequest
from kalshi_python.models.lookup_bundle_response import LookupBundleResponse
from kalshi_python.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.elections.kalshi.com/trade-api/v2
# See configuration.py for a list of all supported configuration parameters.
configuration = kalshi_python.Configuration(
    host = "https://api.elections.kalshi.com/trade-api/v2"
)

# Read private key from file
with open('path/to/private_key.pem', 'r') as f:
    private_key = f.read()

# Configure API key authentication
configuration.api_key_id = "your-api-key-id"
configuration.private_key_pem = private_key

# Initialize the Kalshi client
client = kalshi_python.KalshiClient(configuration)

collection_ticker = 'collection_ticker_example' # str | Collection ticker

lookup_bundle_request = kalshi_python.LookupBundleRequest() # LookupBundleRequest |

try:
    # Lookup Multivariate Event Collection Bundle
    api_response = client.lookup_multivariate_event_collection_bundle(collection_ticker, lookup_bundle_request)
    print("The response of MultivariateCollectionsApi->lookup_multivariate_event_collection_bundle:\n")
    pprint(api_response)
except Exception as e:
    print("Exception when calling MultivariateCollectionsApi->lookup_multivariate_event_collection_bundle: %s\n" % e)
​
Parameters
Name	Type	Description	Notes
collection_ticker	str	Collection ticker	
lookup_bundle_request	LookupBundleRequest		
​
Return type
LookupBundleResponse
​
HTTP response details
Status code	Description
200	Bundle lookup successful
400	Bad request - invalid input
401	Unauthorized - authentication required
404	Resource not found
500	Internal server error

StructuredTargets
Python SDK methods for StructuredTargets operations

All URIs are relative to https://api.elections.kalshi.com/trade-api/v2
Method	HTTP request	Description
get_structured_target	GET /structured_targets/	Get Structured Target
get_structured_targets	GET /structured_targets	Get Structured Targets
​
get_structured_target
GetStructuredTargetResponse get_structured_target(structured_target_id)
Get Structured Target
Endpoint for getting data about a specific structured target by its ID.
​
Parameters
Name	Type	Description	Notes
structured_target_id	str	Structured target ID	
​
Return type
GetStructuredTargetResponse
​
HTTP response details
Status code	Description
200	Structured target retrieved successfully
401	Unauthorized
404	Not found
500	Internal server error
​
get_structured_targets
GetStructuredTargetsResponse get_structured_targets(type=type, competition=competition, page_size=page_size, cursor=cursor)
Get Structured Targets
Page size (min: 1, max: 2000)
​
Parameters
Name	Type	Description	Notes
type	str	Filter by structured target type	[optional]
competition	str	Filter by competition	[optional]
page_size	int	Number of items per page (min 1, max 2000, default 100)	[optional] [default to 100]
cursor	str	Pagination cursor	[optional]
​
Return type
GetStructuredTargetsResponse
​
HTTP response details
Status code	Description
200	Structured targets retrieved successfully
401	Unauthorized
500	Internal server error

Exchange
Python SDK methods for Exchange operations

All URIs are relative to https://api.elections.kalshi.com/trade-api/v2
Method	HTTP request	Description
get_exchange_announcements	GET /exchange/announcements	Get Exchange Announcements
get_exchange_schedule	GET /exchange/schedule	Get Exchange Schedule
get_exchange_status	GET /exchange/status	Get Exchange Status
get_series_fee_changes	GET /series/fee_changes	Get Series Fee Changes
get_user_data_timestamp	GET /exchange/user_data_timestamp	Get User Data Timestamp
​
get_exchange_announcements
GetExchangeAnnouncementsResponse get_exchange_announcements()
Get Exchange Announcements
Endpoint for getting all exchange-wide announcements.
​
Parameters
This endpoint does not need any parameter.
​
Return type
GetExchangeAnnouncementsResponse
​
HTTP response details
Status code	Description
200	Exchange announcements retrieved successfully
500	Internal server error
​
get_exchange_schedule
GetExchangeScheduleResponse get_exchange_schedule()
Get Exchange Schedule
Endpoint for getting the exchange schedule.
​
Parameters
This endpoint does not need any parameter.
​
Return type
GetExchangeScheduleResponse
​
HTTP response details
Status code	Description
200	Exchange schedule retrieved successfully
500	Internal server error
​
get_exchange_status
ExchangeStatus get_exchange_status()
Get Exchange Status
Endpoint for getting the exchange status.
​
Parameters
This endpoint does not need any parameter.
​
Return type
ExchangeStatus
​
HTTP response details
Status code	Description
200	Exchange status retrieved successfully
500	Internal server error
503	Service unavailable
504	Gateway timeout
​
get_series_fee_changes
GetSeriesFeeChangesResponse get_series_fee_changes(series_ticker=series_ticker, show_historical=show_historical)
Get Series Fee Changes
​
Parameters
Name	Type	Description	Notes
series_ticker	str		[optional]
show_historical	bool		[optional] [default to False]
​
Return type
GetSeriesFeeChangesResponse
​
HTTP response details
Status code	Description
200	Series fee changes retrieved successfully
400	Bad request - invalid input
500	Internal server error
​
get_user_data_timestamp
GetUserDataTimestampResponse get_user_data_timestamp()
Get User Data Timestamp
There is typically a short delay before exchange events are reflected in the API endpoints. Whenever possible, combine API responses to PUT/POST/DELETE requests with websocket data to obtain the most accurate view of the exchange state. This endpoint provides an approximate indication of when the data from the following endpoints was last validated: GetBalance, GetOrder(s), GetFills, GetPositions
​
Parameters
This endpoint does not need any parameter.
​
Return type
GetUserDataTimestampResponse
​
HTTP response details
Status code	Description
200	User data timestamp retrieved successfully
500	Internal server error

ApiKeys
Python SDK methods for ApiKeys operations

All URIs are relative to https://api.elections.kalshi.com/trade-api/v2
Method	HTTP request	Description
create_api_key	POST /api_keys	Create API Key
delete_api_key	DELETE /api_keys/	Delete API Key
generate_api_key	POST /api_keys/generate	Generate API Key
get_api_keys	GET /api_keys	Get API Keys
​
create_api_key
CreateApiKeyResponse create_api_key(create_api_key_request)
Create API Key
Endpoint for creating a new API key with a user-provided public key. This endpoint allows users with Premier or Market Maker API usage levels to create API keys by providing their own RSA public key. The platform will use this public key to verify signatures on API requests.
​
Parameters
Name	Type	Description	Notes
create_api_key_request	CreateApiKeyRequest		
​
Return type
CreateApiKeyResponse
​
HTTP response details
Status code	Description
201	API key created successfully
400	Bad request - invalid input
401	Unauthorized
403	Forbidden - insufficient API usage level
500	Internal server error
​
delete_api_key
delete_api_key(api_key)
Delete API Key
Endpoint for deleting an existing API key. This endpoint permanently deletes an API key. Once deleted, the key can no longer be used for authentication. This action cannot be undone.
​
Parameters
Name	Type	Description	Notes
api_key	str	API key ID to delete	
​
Return type
void (empty response body)
​
HTTP response details
Status code	Description
204	API key successfully deleted
400	Bad request - invalid API key ID
401	Unauthorized
404	API key not found
500	Internal server error
​
generate_api_key
GenerateApiKeyResponse generate_api_key(generate_api_key_request)
Generate API Key
Endpoint for generating a new API key with an automatically created key pair. This endpoint generates both a public and private RSA key pair. The public key is stored on the platform, while the private key is returned to the user and must be stored securely. The private key cannot be retrieved again.
​
Parameters
Name	Type	Description	Notes
generate_api_key_request	GenerateApiKeyRequest		
​
Return type
GenerateApiKeyResponse
​
HTTP response details
Status code	Description
201	API key generated successfully
400	Bad request - invalid input
401	Unauthorized
500	Internal server error
​
get_api_keys
GetApiKeysResponse get_api_keys()
Get API Keys
Endpoint for retrieving all API keys associated with the authenticated user. API keys allow programmatic access to the platform without requiring username/password authentication. Each key has a unique identifier and name.
​
Parameters
This endpoint does not need any parameter.
​
Return type
GetApiKeysResponse
​
HTTP response details
Status code	Description
200	List of API keys retrieved successfully
401	Unauthorized
500	Internal server error