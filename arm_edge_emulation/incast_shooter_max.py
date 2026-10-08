import socket

# Change this IP to the internal IP of Node-0 (Leader)
UDP_IP = "10.148.0.3" 
UDP_PORT = 5005
MESSAGE = b"X" * 4000 # 4000 Bytes Jumbo Payload

print(f"Maximal Incast Shooter initialized! Bombarding {UDP_IP}:{UDP_PORT} ...")
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

try:
    while True:
        # Send at maximum speed without sleep delay to saturate hardware and queues
        sock.sendto(MESSAGE, (UDP_IP, UDP_PORT))
except KeyboardInterrupt:
    print("\nShooter stopped.")