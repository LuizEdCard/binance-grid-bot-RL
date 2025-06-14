#!/usr/bin/env python3
"""
Hourly log monitoring until 7 AM
"""

import time
import datetime
import os
import re
import glob
import json
from collections import defaultdict

def analyze_logs():
    """Analyze bot logs for errors and important events."""
    print(f"\n📊 LOG ANALYSIS - {datetime.datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)
    
    log_file = "src/logs/bot.log"
    
    if not os.path.exists(log_file):
        print("❌ Log file not found")
        return
    
    # Read last 100 lines
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-100:]  # Last 100 lines
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
        return
    
    # Get current time - 1 hour for filtering
    one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
    
    # Analysis counters
    errors = []
    warnings = []
    orders = []
    trades = []
    agent_status = defaultdict(list)
    
    for line in recent_lines:
        line = line.strip()
        if not line:
            continue
            
        # Extract timestamp and check if recent
        timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if timestamp_match:
            try:
                log_time = datetime.datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
                if log_time < one_hour_ago:
                    continue  # Skip old logs
            except:
                pass  # Continue if can't parse timestamp
        
        # Categorize log entries
        if " - ERROR -" in line:
            errors.append(line)
        elif " - WARNING -" in line:
            warnings.append(line)
        elif "Order" in line and ("placed" in line or "filled" in line or "executed" in line):
            orders.append(line)
        elif "trade" in line.lower() and ("profit" in line or "loss" in line):
            trades.append(line)
        
        # Agent status
        for agent in ["ai_agent", "risk_agent", "sentiment_agent", "coordinator_agent", "data_agent"]:
            if agent in line:
                if "started" in line or "stopped" in line or "health" in line:
                    agent_status[agent].append(line)
    
    # Report findings
    print(f"🔍 Analysis of last hour:")
    print(f"  📝 Total recent log lines: {len(recent_lines)}")
    
    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for error in errors[-5:]:  # Show last 5 errors
            # Extract just the error message part
            parts = error.split(" - ERROR - ")
            if len(parts) > 1:
                print(f"  • {parts[1][:100]}...")
    else:
        print(f"\n✅ No errors in the last hour")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings[-3:]:  # Show last 3 warnings
            parts = warning.split(" - WARNING - ")
            if len(parts) > 1:
                print(f"  • {parts[1][:80]}...")
    else:
        print(f"\n✅ No warnings in the last hour")
    
    if orders:
        print(f"\n📋 ORDERS ({len(orders)}):")
        for order in orders[-3:]:  # Show last 3 orders
            if "Order" in order:
                print(f"  • {order.split(' - INFO - ')[1] if ' - INFO - ' in order else order}")
    else:
        print(f"\n📋 No order activity in the last hour")
    
    if trades:
        print(f"\n💰 TRADES ({len(trades)}):")
        for trade in trades:
            print(f"  • {trade}")
    else:
        print(f"\n💰 No trade activity in the last hour")
    
    # Agent health summary
    print(f"\n🤖 AGENT STATUS:")
    if agent_status:
        for agent, statuses in agent_status.items():
            latest = statuses[-1] if statuses else "No recent activity"
            if " - INFO - " in latest:
                status_msg = latest.split(" - INFO - ")[1][:60]
            elif " - WARNING - " in latest:
                status_msg = f"⚠️  {latest.split(' - WARNING - ')[1][:60]}"
            else:
                status_msg = latest[:60]
            print(f"  {agent}: {status_msg}...")
    else:
        print(f"  No agent status updates in the last hour")
    
    # Check for specific issues
    print(f"\n🔍 ISSUE DETECTION:")
    
    # Check for API issues
    api_errors = [e for e in errors if "API" in e or "connection" in e.lower()]
    if api_errors:
        print(f"  🚨 API Issues detected: {len(api_errors)}")
    
    # Check for balance issues
    balance_issues = [w for w in warnings if "balance" in w.lower() or "insufficient" in w.lower()]
    if balance_issues:
        print(f"  💰 Balance Issues detected: {len(balance_issues)}")
    
    # Check for stuck processes
    stuck_warnings = [w for w in warnings if "timeout" in w.lower() or "stuck" in w.lower()]
    if stuck_warnings:
        print(f"  ⏰ Timeout/Stuck Issues: {len(stuck_warnings)}")
    
    if not api_errors and not balance_issues and not stuck_warnings:
        print(f"  ✅ No major issues detected")
    
    print(f"\n" + "=" * 50)

def display_pair_logs():
    """Display individual pair logs with trading metrics."""
    print(f"\n📈 PAIR TRADING STATUS - {datetime.datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Check for pair-specific logs
    pair_log_dir = "logs/pairs"
    if not os.path.exists(pair_log_dir):
        pair_log_dir = "src/logs/pairs"
    
    if not os.path.exists(pair_log_dir):
        print("📂 No pair-specific logs directory found")
        
        # Check for grid states as alternative
        grid_states_dir = "data/grid_states"
        if os.path.exists(grid_states_dir):
            print("🔍 Checking grid states for active pairs...")
            display_grid_states()
        return
    
    # Get all pair log files
    pair_logs = glob.glob(os.path.join(pair_log_dir, "*.log"))
    
    if not pair_logs:
        print("📝 No individual pair logs found")
        display_grid_states()
        return
    
    print(f"🔍 Found {len(pair_logs)} pair logs")
    
    for log_file in sorted(pair_logs):
        pair_name = os.path.basename(log_file).replace('.log', '').upper()
        
        try:
            # Read last 20 lines of each pair log
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-20:] if len(lines) > 20 else lines
            
            if not recent_lines:
                continue
                
            # Parse latest trading information
            latest_info = parse_pair_log_info(recent_lines, pair_name)
            display_pair_summary(pair_name, latest_info)
            
        except Exception as e:
            print(f"❌ Error reading {pair_name} log: {e}")
    
    print("=" * 80)

def display_grid_states():
    """Display information from grid state files."""
    grid_states_dir = "data/grid_states"
    
    if not os.path.exists(grid_states_dir):
        print("📂 No grid states directory found")
        return
    
    state_files = glob.glob(os.path.join(grid_states_dir, "*_state.json"))
    
    if not state_files:
        print("📊 No grid state files found")
        return
    
    print(f"🔍 Found {len(state_files)} grid states")
    
    for state_file in sorted(state_files):
        try:
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            pair_name = state_data.get('symbol', 'UNKNOWN')
            display_grid_state_summary(pair_name, state_data)
            
        except Exception as e:
            print(f"❌ Error reading grid state: {e}")

def parse_pair_log_info(lines, pair_name):
    """Parse trading information from pair log lines."""
    info = {
        'last_price': 0.0,
        'position_size': 0.0,
        'unrealized_pnl': 0.0,
        'volume_24h': 0.0,
        'price_change_24h': 0.0,
        'active_orders': 0,
        'grid_levels': 0,
        'last_activity': 'No recent activity',
        'tp_price': 0.0,
        'sl_price': 0.0
    }
    
    for line in lines:
        line = line.strip()
        
        # Extract price information
        if 'PREÇO:' in line:
            price_match = re.search(r'\$(\d+\.?\d*)', line)
            if price_match:
                info['last_price'] = float(price_match.group(1))
            
            change_match = re.search(r'([+-]\d+\.?\d*)%', line)
            if change_match:
                info['price_change_24h'] = float(change_match.group(1))
        
        # Extract position information
        if 'POSIÇÃO:' in line:
            pos_match = re.search(r'(\d+\.?\d*) ' + pair_name.replace('USDT', ''), line)
            if pos_match:
                info['position_size'] = float(pos_match.group(1))
        
        # Extract PNL
        if 'PNL:' in line:
            pnl_match = re.search(r'([+-]?\d+\.?\d*) USDT', line)
            if pnl_match:
                info['unrealized_pnl'] = float(pnl_match.group(1))
        
        # Extract TP/SL
        if 'TP:' in line:
            tp_match = re.search(r'TP:\s*\$(\d+\.?\d*)', line)
            if tp_match:
                info['tp_price'] = float(tp_match.group(1))
        
        if 'SL:' in line:
            sl_match = re.search(r'SL:\s*\$(\d+\.?\d*)', line)
            if sl_match:
                info['sl_price'] = float(sl_match.group(1))
        
        # Extract volume
        if 'VOLUME 24H:' in line:
            vol_match = re.search(r'(\d+(?:,\d+)*) USDT', line)
            if vol_match:
                info['volume_24h'] = float(vol_match.group(1).replace(',', ''))
        
        # Extract grid info
        if 'GRID:' in line:
            levels_match = re.search(r'Níveis:\s*(\d+)', line)
            if levels_match:
                info['grid_levels'] = int(levels_match.group(1))
            
            orders_match = re.search(r'Ordens:\s*(\d+)', line)
            if orders_match:
                info['active_orders'] = int(orders_match.group(1))
        
        # Track last activity
        if any(keyword in line for keyword in ['BUY', 'SELL', 'ORDER', 'FILLED']):
            info['last_activity'] = line[-100:]  # Last 100 chars
    
    return info

def display_pair_summary(pair_name, info):
    """Display a formatted summary for a trading pair."""
    
    # Format price change with color indicators
    change_indicator = "📈" if info['price_change_24h'] >= 0 else "📉"
    change_color = "+" if info['price_change_24h'] >= 0 else ""
    
    # Format PNL with indicators
    pnl_indicator = "💰" if info['unrealized_pnl'] >= 0 else "📉"
    pnl_color = "+" if info['unrealized_pnl'] >= 0 else ""
    
    # Position status
    pos_status = "🟢 LONG" if info['position_size'] > 0 else "🔴 SHORT" if info['position_size'] < 0 else "⚪ NONE"
    
    print(f"\n📊 {pair_name}")
    print(f"   💲 Preço: ${info['last_price']:.4f} ({change_color}{info['price_change_24h']:.2f}%) {change_indicator}")
    print(f"   📈 Volume 24h: {info['volume_24h']:,.0f} USDT")
    print(f"   📊 Posição: {pos_status} ({info['position_size']:.4f})")
    print(f"   💰 PNL: {pnl_color}{info['unrealized_pnl']:.4f} USDT {pnl_indicator}")
    
    if info['tp_price'] > 0:
        print(f"   🎯 TP: ${info['tp_price']:.4f}")
    if info['sl_price'] > 0:
        print(f"   🛡️ SL: ${info['sl_price']:.4f}")
    
    print(f"   🔲 Grid: {info['grid_levels']} níveis, {info['active_orders']} ordens ativas")

def display_grid_state_summary(pair_name, state_data):
    """Display summary from grid state data."""
    print(f"\n📊 {pair_name}")
    print(f"   🔲 Grid Níveis: {state_data.get('num_levels', 'N/A')}")
    print(f"   📏 Espaçamento: {float(state_data.get('spacing_percentage', 0)) * 100:.2f}%")
    print(f"   🏪 Mercado: {state_data.get('market_type', 'Unknown').upper()}")
    print(f"   📅 Última Atualização: {state_data.get('last_updated', 'Unknown')}")
    
    # Active orders count
    active_orders = state_data.get('active_grid_orders', {})
    if isinstance(active_orders, dict):
        order_count = len(active_orders)
        print(f"   📋 Ordens Ativas: {order_count}")

def show_help():
    """Show available monitoring commands."""
    print("\n🔧 COMANDOS DISPONÍVEIS:")
    print("  logs    - Analisar logs principais do bot")
    print("  pairs   - Mostrar status detalhado dos pares")
    print("  states  - Mostrar estados dos grids ativos")
    print("  help    - Mostrar esta ajuda")
    print("  quit    - Sair do monitor")
    print("=" * 50)

def interactive_mode():
    """Interactive monitoring mode with commands."""
    print("🔧 MODO INTERATIVO DO MONITOR")
    print("Digite 'help' para ver comandos disponíveis")
    print("=" * 50)
    
    while True:
        try:
            command = input("\n> ").strip().lower()
            
            if command in ['quit', 'exit', 'q']:
                print("👋 Saindo do monitor...")
                break
            elif command == 'help':
                show_help()
            elif command == 'logs':
                analyze_logs()
            elif command == 'pairs':
                display_pair_logs()
            elif command == 'states':
                display_grid_states()
            elif command == '':
                continue  # Empty command, just continue
            else:
                print(f"❌ Comando desconhecido: '{command}'. Digite 'help' para ajuda.")
                
        except KeyboardInterrupt:
            print(f"\n🛑 Monitor interrompido pelo usuário")
            break
        except EOFError:
            print(f"\n👋 Saindo do monitor...")
            break

def main():
    """Main monitoring function with mode selection."""
    print("🕐 MONITOR DE LOGS DO BOT DE TRADING")
    print("=" * 50)
    
    # Check if running with arguments
    import sys
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == 'interactive':
            interactive_mode()
            return
        elif mode == 'pairs':
            display_pair_logs()
            return
        elif mode == 'states':
            display_grid_states()
            return
        elif mode == 'logs':
            analyze_logs()
            return
    
    print("Escolha o modo de operação:")
    print("1. Monitoramento automático por hora (até 7h)")
    print("2. Modo interativo com comandos")
    print("3. Verificação única dos logs")
    print("4. Status dos pares de trading")
    
    try:
        choice = input("\nEscolha (1-4): ").strip()
        
        if choice == '1':
            hourly_monitoring()
        elif choice == '2':
            interactive_mode()
        elif choice == '3':
            analyze_logs()
        elif choice == '4':
            display_pair_logs()
        else:
            print("❌ Opção inválida. Executando verificação única dos logs...")
            analyze_logs()
            
    except KeyboardInterrupt:
        print(f"\n🛑 Monitor interrompido pelo usuário")
    except EOFError:
        print(f"\n👋 Saindo do monitor...")

def hourly_monitoring():
    """Original hourly monitoring functionality."""
    print("🕐 Starting Hourly Log Monitoring")
    print("Will check logs every hour until 7:00 AM")
    print("=" * 50)
    
    target_hour = 7  # 7 AM
    
    while True:
        current_time = datetime.datetime.now()
        current_hour = current_time.hour
        
        # Stop at 7 AM
        if current_hour >= target_hour and current_hour < 12:  # Stop between 7 AM and noon
            print(f"\n🎯 Reached target time (7 AM). Monitoring complete.")
            analyze_logs()  # Final analysis
            break
        
        # Perform log analysis
        analyze_logs()
        
        # Calculate time to next hour
        next_hour = (current_time + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        sleep_time = (next_hour - current_time).total_seconds()
        
        print(f"\n⏰ Next check at {next_hour.strftime('%H:%M:%S')}")
        print(f"   Sleeping for {sleep_time/60:.1f} minutes...")
        
        try:
            time.sleep(sleep_time)
        except KeyboardInterrupt:
            print(f"\n🛑 Monitoring stopped by user")
            break

if __name__ == "__main__":
    main()