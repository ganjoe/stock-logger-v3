"""
Verification script for IBKR Broker Connection.

Performs a READ-ONLY check of the broker connection:
1. Connects to the Gateway/TWS.
2. Sets MarketDataType to DELAYED (3).
3. Fetches and prints Account Summary (Cash, Equity).
4. Fetches and prints Open Positions.
5. Fetches a test ticker price (AAPL) to verify data flow.

Usage:
    python verify_broker_connection.py [--host HOST] [--port PORT] [--account ACCOUNT_ID]
"""
import argparse
import random
import sys
import time
try:
    from .broker_data_source import BrokerDataSource
except ImportError:
    from py_broker_captrader import BrokerDataSource

def main():
    parser = argparse.ArgumentParser(description='Verify IBKR Connection (Read-Only)')
    parser.add_argument('--host', default='127.0.0.1', help='IBKR Gateway/TWS Host')
    parser.add_argument('--port', type=int, default=7497, help='IBKR Gateway/TWS Port (7497=Paper, 7496=Live, 4002=Gateway Paper)')
    parser.add_argument('--account', help='Account ID (optional)')
    
    args = parser.parse_args()
    
    # Use random Client ID to avoid conflicts
    client_id = random.randint(1000, 9999)
    
    print(f"Connecting to {args.host}:{args.port} with ClientId {client_id}...")
    print("⚠️  SAFETY CHECK: This script is READ-ONLY. No value will be changed. No trades will be executed.")
    
    try:
        # Initialize DataSource (this connects and sets MarketDataType=3 automatically)
        ds = BrokerDataSource(
            host=args.host,
            port=args.port,
            client_id=client_id,
            account_id=args.account,
            auto_connect=True
        )
        
        ib = ds._connection.ib
        
        if ds.is_connected():
            print("✅ CONNECTION SUCCESSFUL")
            print(f"   Connected to: {args.host}:{args.port}")
            print(f"   ClientId: {ds._connection.config.client_id}")
            
            # Verify Market Data Type
            print("\n🔍 MARKET DATA TYPE")
            # We can't easily read it back synchronously without a request, 
            # but we can verify we triggered the request.
            print("   Requested: 3 (Delayed)")
            
            # 1. Account Summary
            print("\n💰 ACCOUNT SUMMARY (Read-Only)")
            metrics = ds.get_account_metrics()
            print(f"   Account: {ds._get_account()}")
            print(f"   Cash:    {metrics.cash:,.2f} USD")
            print(f"   Equity:  {metrics.equity:,.2f} USD")
            
            # 2. Positions
            print("\nYOUR PORTFOLIO HAS THE FOLLOWING POSITIONS:")
            print("-" * 60)
            print(f"{'SYMBOL':<10} {'QTY':<10} {'ENTRY PRICE':<15} {'CURRENCY':<10}")
            print("-" * 60)
            
            positions = ds.get_positions()
            if not positions:
                print("   (No open positions found)")
            else:
                for pos in positions:
                    print(f"{pos.symbol:<10} {pos.quantity:<10.2f} {pos.entry_price:<15.2f} {pos.currency:<10}")
            print("-" * 60)
            
            # 3. Test Market Data (Delayed)
            print("\n📉 TEST DATA FETCH (Delayed, Read-Only)")
            symbol = "AAPL"
            print(f"   Fetching delayed ticker for {symbol}...")
            
            from ib_insync import Stock
            contract = Stock(symbol, 'SMART', 'USD')
            ib.qualifyContracts(contract)
            
            # Request ticker (Snapshot)
            # snapshot=True is often required for delayed/frozen data when market is closed or 
            # for certain permission sets.
            ticker = ib.reqMktData(contract, '', True, False)
            
            # Wait a moment for data
            for _ in range(40): # Wait up to 4 seconds
                if ticker.last or ticker.close or (ticker.bid and ticker.ask):
                    break
                ib.sleep(0.1)
                
            price = ticker.last if ticker.last else ticker.close
            
            # Fallback to Bid/Ask Midpoint if no last price
            if (not price or price != price) and (ticker.bid and ticker.ask): # price != price check for NaN
                 price = (ticker.bid + ticker.ask) / 2
                 print(f"   {symbol} Bid: {ticker.bid}, Ask: {ticker.ask}")
                 print(f"   {symbol} Price: {price} (Midpoint)")
            else:
                 print(f"   {symbol} Price: {price}")
            
            if price and price > 0:
                 print("✅ DATA FLOW CONFIRMED")
            else:
                 print("⚠️ NO PRICE DATA RECEIVED")
                 print("   Possible reasons:")
                 print("   1. Missing 'Delayed Market Data' permission in Account Management")
                 print("   2. Missing 'Snapshot' permission")
                 print("   3. Market data subscription needed even for delayed data (sometimes)")

            # --- 5. DATA FETCHER CHECK (History) ---
            print("\n📜 HISTORICAL DATA TEST (DataFetcher)")
            try:
                from .data_provider import BrokerDataProvider
            except ImportError:
                from py_broker_captrader.data_provider import BrokerDataProvider
                # Re-use connection
                provider = BrokerDataProvider(ds._connection)
                
                print(f"   Fetching last 5 days for {contract.symbol}...")
                history = provider.get_daily_history(contract.symbol, days=5)
                
                if history:
                    print(f"   ✅ Received {len(history)} bars.")
                    last_bar = history[-1]
                    print(f"   Latest: {last_bar.date.date()} Close: {last_bar.close} Vol: {last_bar.volume:,.0f}")
                else:
                    print("   ⚠️ No history received (Check permissions/subscriptions).")
                    
            except Exception as e:
                print(f"   ❌ History Fetch Error: {e}")

            ds.disconnect()
            print("\n✅ Verification complete. Disconnected.")
            
        else:
            print("❌ CONNECTION FAILED (Unknown reason)")
            
    except ImportError:
        print("❌ CRITICAL ERROR: ib_insync not found.")
        print("   Please install: pip install ib_insync")
    except Exception as e:
        print(f"❌ CONNECTION ERROR: {e}")
        print("   Ensure TWS or Gateway is running and API is enabled.")
        print("   Check Host/Port settings.")

if __name__ == "__main__":
    main()
