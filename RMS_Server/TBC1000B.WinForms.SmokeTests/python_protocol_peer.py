import json
import socket
import sys


def send_registration(message_type, port):
    payload = {
        "type": message_type,
        "ip": "10.0.0.33",
        "port": port,
        "profile": "python-peer.ini",
        "system": "Python compatibility peer",
    }
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.sendto(json.dumps(payload).encode("utf-8"), ("127.0.0.1", 50000))


def main():
    port = int(sys.argv[1])
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", port))
        receiver.settimeout(0.5)
        try:
            packet = None
            for attempt in range(10):
                send_registration("register" if attempt == 0 else "heartbeat", port)
                try:
                    packet, _ = receiver.recvfrom(65535)
                    break
                except socket.timeout:
                    continue
            if packet is None:
                raise TimeoutError("C# master did not forward a packet")
            message = json.loads(packet.decode("utf-8"))
            print(json.dumps(message, ensure_ascii=False, separators=(",", ":")))
        finally:
            send_registration("unregister", port)


if __name__ == "__main__":
    main()
