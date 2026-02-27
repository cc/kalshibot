from kalshibot.monitor import run_monitor

try:
    run_monitor()
except KeyboardInterrupt:
    print("\n[monitor] stopped")
