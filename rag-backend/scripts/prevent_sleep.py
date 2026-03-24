import ctypes
import time
import os

# Windows Constants
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

def prevent_sleep():
    print("Inhibition started: Preventing system sleep...")
    # ES_SYSTEM_REQUIRED: Prevent sleep
    # ES_CONTINUOUS: Keep the state until changed or process ends
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
    
    try:
        while True:
            # Heartbeat to show it's running
            with open("sleep_inhibitor_status.txt", "w") as f:
                f.write(f"Active since {time.ctime()}\n")
            time.sleep(60)
    except KeyboardInterrupt:
        print("Inhibition stopped.")
    finally:
        # Reset to default
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)

if __name__ == "__main__":
    prevent_sleep()
