import os
import sys
import time
import subprocess
import threading
import getpass
from datetime import datetime
import multiprocessing

def get_credentials():
    username = input("Enter username (add 86 prefix for Chinese mainland): ")
    password = getpass.getpass("Enter password: ")
    return f"{username}:{password}"

def log_output(timestamp, message):
    with open("wrapper_log.txt", "a") as log:
        log.write(f"[{timestamp}] {message}\n")

def handle_2fa():
    code = input("Enter 2FA code: ")
    return code + "\n"

def background_process(log_file):
    # Redirect standard file descriptors
    with open(os.devnull, 'r') as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    with open(log_file, 'a') as log:
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())

def read_output(process):
    m3u8_seen = False
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            line = line.decode('utf-8', errors='replace').strip()
            
            # Print to console only before backgrounding
            if not m3u8_seen:
                print(f"[{timestamp}] {line}")
            
            log_output(timestamp, line)
            
            # Check for login failure
            if "login failed" in line.lower():
                print("\nLogin failed. Exiting...")
                sys.stdout.flush()
                time.sleep(0.1)  # Give time for the message to be printed
                process.terminate()
                sys.exit(1)
            
            if "listening m3u8 request on" in line and not m3u8_seen:
                m3u8_seen = True
                print("\nService is ready. Moving to background...")
                sys.stdout.flush()
                
                # Create new background process using multiprocessing
                ctx = multiprocessing.get_context('spawn')
                p = ctx.Process(target=background_process, args=("wrapper_log.txt",))
                p.daemon = True
                p.start()
                
                # Exit the parent process
                os._exit(0)
                    
            if "2FA code:" in line or "verification code" in line:
                code = handle_2fa()
                process.stdin.write(code.encode())
                process.stdin.flush()

def main():
    try:
        # Change to wrapper directory
        os.chdir("wrapper")
        
        # Get credentials
        credentials = get_credentials()
        
        # Start wrapper process
        process = subprocess.Popen(
            ["./wrapper", "-D", "10020", "-M", "20020", "-L", credentials],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            universal_newlines=False
        )

        # Start output reading thread
        output_thread = threading.Thread(target=read_output, args=(process,))
        output_thread.daemon = True
        output_thread.start()

        # Wait for process to complete or error
        process.wait()
        
        # If process exits with non-zero status, exit the script
        if process.returncode != 0:
            sys.exit(process.returncode)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        if 'process' in locals() and process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    multiprocessing.set_start_method('spawn')
    main()
