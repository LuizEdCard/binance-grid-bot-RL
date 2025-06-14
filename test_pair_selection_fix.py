#!/usr/bin/env python3
"""
Test script to verify that pair selection is working correctly after the fix.
"""

import sys
import os
import yaml

# Add src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.pair_selector import PairSelector
from utils.api_client import APIClient

def main():
    print("🔧 TESTING PAIR SELECTION FIX")
    print("=" * 50)
    
    # Load config
    config_path = os.path.join('src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    print(f"✅ Config loaded from: {config_path}")
    
    # Check preferred symbols in config
    preferred = config.get('pair_selection', {}).get('futures_pairs', {}).get('preferred_symbols', [])
    print(f"📝 Preferred symbols in config: {preferred}")
    
    # Initialize API client (needed for PairSelector)
    try:
        api_client = APIClient(config)
        print("✅ API client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize API client: {e}")
        return
    
    # Initialize PairSelector
    try:
        pair_selector = PairSelector(config, api_client)
        print("✅ PairSelector initialized")
        print(f"📁 Cache file path: {pair_selector.cache_file}")
    except Exception as e:
        print(f"❌ Failed to initialize PairSelector: {e}")
        return
    
    # Test getting selected pairs (should use cache first)
    try:
        selected_pairs = pair_selector.get_selected_pairs(force_update=False)
        print(f"🎯 Selected pairs (from cache): {selected_pairs}")
        
        if selected_pairs == preferred:
            print("✅ SUCCESS: Selected pairs match preferred symbols!")
        elif "KAIAUSDT" in selected_pairs:
            print("❌ PROBLEM: KAIAUSDT still in selected pairs")
            print("🔄 Forcing update to clear cache...")
            
            # Force update to refresh
            selected_pairs = pair_selector.get_selected_pairs(force_update=True)
            print(f"🎯 Selected pairs (after force update): {selected_pairs}")
            
            if selected_pairs == preferred:
                print("✅ SUCCESS: Force update fixed the issue!")
            else:
                print("❌ PROBLEM: Still not selecting preferred pairs")
        else:
            print("⚠️  WARNING: Selected pairs don't match preferred, but no KAIAUSDT found")
            
    except Exception as e:
        print(f"❌ Failed to get selected pairs: {e}")
        return
    
    # Check cache file contents
    try:
        import json
        if os.path.exists(pair_selector.cache_file):
            with open(pair_selector.cache_file, 'r') as f:
                cache_data = json.load(f)
            print(f"📄 Cache file contents: {cache_data}")
        else:
            print(f"❌ Cache file not found: {pair_selector.cache_file}")
    except Exception as e:
        print(f"❌ Failed to read cache file: {e}")
    
    print("\n🏁 Test completed!")

if __name__ == "__main__":
    main()