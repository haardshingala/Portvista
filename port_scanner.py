import platform
import subprocess
import socket
import threading
import argparse
import csv
from tqdm import tqdm
from datetime import datetime
from common_ports import PORT_SERVICE_MAP
from datetime import datetime

#DNS resolver

def grab_banner(ip, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect((ip, port))
            # Send minimal HTTP request on HTTP/HTTPS-like ports
            if port in [80, 8080, 443]:
                s.sendall(b"HEAD / HTTP/1.0\r\n\r\n")
            banner = s.recv(1024).decode(errors="ignore").strip()
            return banner if banner else "N/A"
    except Exception:
        return "N/A"

def resolve_target(target):
    try:
        ip = socket.gethostbyname(target)
        print(f"Resolved {target} to {ip}")
        return ip
    except socket.gaierror:
        print(f"Failed to resolve {target}. Please check the domain or IP.")
        exit(1)

#Host availability check
def is_host_up(ip):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    command = ["ping", param, "1", ip]
    try:
        return subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except Exception:
        return False


# Shared list to collect open ports
open_ports = []
lock = threading.Lock()

def scan_port(ip, port, timeout, progress):
    """Attempts to connect to a port and log it if open."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            if result == 0:
                 service = PORT_SERVICE_MAP.get(port, "Unknown")
                 banner = grab_banner(ip, port)
                 with lock:
                    open_ports.append((port, service, banner))
                    print(f"[✔] Port {port} OPEN ({service}) – Banner: {banner}")

    except Exception:
        pass
    finally:
        progress.update(1)

def write_results_csv(filename, results):
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Port", "Service", "Status", "Banner"])  
        for port, service, banner in results:                    
            writer.writerow([port, service, "OPEN", banner])


def write_summary(filename, target, total_scanned, results):
    with open(filename, "w") as f:
        f.write(f"Scan Summary for {target}\n")
        f.write(f"Scanned ports: {total_scanned}\n")
        f.write(f"Open ports found: {len(results)}\n")
        f.write("Open Ports:\n")
        for port, service, banner in results:                           # NEW
            f.write(f" - Port {port}: {service} | Banner: {banner}\n")  # NEW


def main():
    parser = argparse.ArgumentParser(description="Multithreaded TCP Port Scanner")
    parser.add_argument('--target', required=True, help="Target IP address (e.g., 192.168.1.1)")
    parser.add_argument('--start', type=int, default=1, help="Start port (default: 1)")
    parser.add_argument('--end', type=int, default=1024, help="End port (default: 1024)")
    parser.add_argument('--threads', type=int, default=100, help="Max concurrent threads (default: 100)")
    parser.add_argument('--timeout', type=float, default=1.0, help="Timeout per port (seconds)")
    parser.add_argument('--output', type=str, default="results.csv", help="CSV output file name")
    args = parser.parse_args()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

# If user didn’t override the default filename, add timestamp
    if args.output == "results.csv":
        args.output = f"results_{timestamp}.csv"
    summary_filename = f"summary_{timestamp}.txt"

    ip_address = resolve_target(args.target)

    if not is_host_up(ip_address):
        print(f" Host {ip_address} is unreachable. Skipping scan.")
        return
    else:
        print(f"\n Host {ip_address} is reachable.")
        print(f"Starting scan on {args.target} ({args.start}-{args.end})...\n")

    print(f"Using {args.threads} threads with {args.timeout}s timeout per port.\n")

    progress = tqdm(total=args.end - args.start + 1)
    threads = []

    for port in range(args.start, args.end + 1):
        thread = threading.Thread(target=scan_port, args=(ip_address, port, args.timeout, progress))

        threads.append(thread)
        thread.start()

        if len(threads) >= args.threads:
            for t in threads:
                t.join()
            threads = []

    # Join any remaining threads
    for t in threads:
        t.join()

    progress.close()
    print("\n Scan complete.")

    if open_ports:
        open_ports.sort()
        write_results_csv(args.output, open_ports)
        write_summary(summary_filename, args.target, args.end - args.start + 1, open_ports)
        print(f" Results saved to {args.output}")
        print(f"Summary saved to summary.txt")
    else:
        print("No open ports found.")

if __name__ == "__main__":
    main()
