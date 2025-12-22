"""
DataStream module - processes WebSocket data and maintains state
Tracks: best ask prices, liquidity, combined cost
"""

import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class MarketState:
    """Current state of the market - accessible by bot"""
    up_best_ask: Optional[float] = None
    up_ask_liquidity: Optional[float] = None
    down_best_ask: Optional[float] = None
    down_ask_liquidity: Optional[float] = None
    combined_cost: Optional[float] = None
    last_update: Optional[str] = None
    
    def is_arb_opportunity(self) -> bool:
        """Check if combined cost is under $1.00"""
        return self.combined_cost is not None and self.combined_cost < 1.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "up_best_ask": self.up_best_ask,
            "up_ask_liquidity": self.up_ask_liquidity,
            "down_best_ask": self.down_best_ask,
            "down_ask_liquidity": self.down_ask_liquidity,
            "combined_cost": self.combined_cost,
            "last_update": self.last_update,
            "is_arb": self.is_arb_opportunity(),
        }


class DataStream:
    """
    Processes WebSocket messages and maintains market state.
    State is stored and accessible for bot logic.
    """
    
    def __init__(self, up_token: str, down_token: str, verbose: bool = True):
        self.up_token = up_token
        self.down_token = down_token
        self.verbose = verbose
        
        # Current market state - this is what the bot reads
        self.state = MarketState()
        
        # Callbacks for state changes
        self._on_state_change_callback = None
    
    def set_state_change_callback(self, callback):
        """Set callback for when state changes (optional)"""
        self._on_state_change_callback = callback
    
    def process_message(self, raw_message: str):
        """
        Process a WebSocket message and update state.
        Called by connection module.
        """
        if raw_message == "PONG":
            return
        
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            return
        
        event_type = data.get("event_type", "")
        
        if event_type == "book":
            self._handle_book(data)
        elif event_type == "price_change":
            self._handle_price_change(data)
    
    def _handle_book(self, data: dict):
        """Extract best ask and liquidity from full order book"""
        asset_id = data.get("asset_id", "")
        asks = data.get("asks", [])
        
        if not asks:
            return
        
        # Find best (lowest) ask price and total liquidity at that price
        best_ask = None
        best_ask_liquidity = 0.0
        
        for ask in asks:
            try:
                price = float(ask.get("price", 999))
                size = float(ask.get("size", 0))
                
                if best_ask is None or price < best_ask:
                    best_ask = price
                    best_ask_liquidity = size
                elif price == best_ask:
                    best_ask_liquidity += size
            except (ValueError, TypeError):
                continue
        
        if best_ask is not None:
            self._update_state(asset_id, best_ask, best_ask_liquidity)
    
    def _handle_price_change(self, data: dict):
        """Extract best ask from price change events"""
        for change in data.get("price_changes", []):
            if not isinstance(change, dict):
                continue
            
            asset_id = change.get("asset_id", "")
            best_ask_str = change.get("best_ask")
            
            if best_ask_str:
                try:
                    best_ask = float(best_ask_str)
                    # Price change doesn't give liquidity, pass None to keep existing
                    self._update_state(asset_id, best_ask, None)
                except (ValueError, TypeError):
                    pass
    
    def _update_state(self, asset_id: str, best_ask: float, liquidity: Optional[float]):
        """Update state if values changed"""
        changed = False
        
        if asset_id == self.up_token:
            if best_ask != self.state.up_best_ask:
                self.state.up_best_ask = best_ask
                changed = True
            if liquidity is not None and liquidity != self.state.up_ask_liquidity:
                self.state.up_ask_liquidity = liquidity
                changed = True
                
        elif asset_id == self.down_token:
            if best_ask != self.state.down_best_ask:
                self.state.down_best_ask = best_ask
                changed = True
            if liquidity is not None and liquidity != self.state.down_ask_liquidity:
                self.state.down_ask_liquidity = liquidity
                changed = True
        
        if changed:
            # Update combined cost
            if self.state.up_best_ask and self.state.down_best_ask:
                self.state.combined_cost = self.state.up_best_ask + self.state.down_best_ask
            
            # Update timestamp
            self.state.last_update = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            # Log if verbose
            if self.verbose:
                self._log_state()
            
            # Trigger callback if set
            if self._on_state_change_callback:
                self._on_state_change_callback(self.state)
    
    def _log_state(self):
        """Print current state to console"""
        up_str = f"${self.state.up_best_ask:.3f}" if self.state.up_best_ask else "---"
        down_str = f"${self.state.down_best_ask:.3f}" if self.state.down_best_ask else "---"
        
        up_liq = f"{self.state.up_ask_liquidity:.1f}" if self.state.up_ask_liquidity else "?"
        down_liq = f"{self.state.down_ask_liquidity:.1f}" if self.state.down_ask_liquidity else "?"
        
        combined = ""
        if self.state.combined_cost:
            combined = f" | Combined: ${self.state.combined_cost:.3f}"
            if self.state.is_arb_opportunity():
                combined += " ✓ ARB"
        
        print(f"[STREAM] [{self.state.last_update}] Up: {up_str} ({up_liq}) | Down: {down_str} ({down_liq}){combined}")
    
    def get_state(self) -> MarketState:
        """Get current market state - for bot logic"""
        return self.state
    
    def reset(self):
        """Reset state for new market"""
        self.state = MarketState()
        print("[STREAM] State reset")

