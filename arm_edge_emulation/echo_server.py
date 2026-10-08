import socket

UDP_IP = "0.0.0.0"
UDP_PORT = 5006

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"Telemetry Echo server ready on port {UDP_PORT}...")

while True:
    data, addr = sock.recvfrom(1024)
    # Echo the received timestamp packet back to the sender
    sock.sendto(data, addr)