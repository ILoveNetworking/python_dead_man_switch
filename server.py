import os
import sys
import socket
import json
import argparse
from time import sleep
from datetime import datetime, timezone
import textwrap
import smtplib
from select import select

def send_email(FROM : str, TO : str, SUBJECT : str, TEXT : str, SERVER : str, PORT : int, CREDS : dict):
    """
    This function used to send the email to specified user from specified email
    """
    message = textwrap.dedent("""\
        From: %s
        To: %s
        Subject: %s
        %s
        """ % (FROM, ", ".join(TO), SUBJECT, TEXT))
    # Send the mail
    server = smtplib.SMTP(SERVER, PORT)
    server.starttls()
    server.login(CREDS["username"], CREDS["password"])
    server.sendmail(FROM, TO, message)
    server.quit()

def load_config(file_path : str) -> dict:
    # Get password, time to expect connection (in utc format) (begin - end), message contents from config file
    if os.path.exists(file_path):
        with open(file_path, "r") as cfgf:
            data = json.load(cfgf)
            return data
    else:
        print("[!] File not exists!")
        return None

def handle_connect(sock_type : socket.SocketKind, connection_data : tuple, time_limits : list, password : str, smtp_cfg : dict) -> None:
    """
    This function used to handle the client TCP or UDP connection and recieve data, in this case user specified password
    """
    print(f"[+] Starting listener at: {connection_data[0]}:{connection_data[1]} type: {'TCP' if sock_type == socket.SOCK_STREAM else 'UDP'}")
    server = socket.socket(socket.AF_INET, sock_type)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(connection_data)
    # We are accepting only one connection at the time
    server.listen(1)

    # Setting the variable to track if password was entered today or not
    password_entered = False

    while True:
        # Check for current time
        current_time = datetime.now(timezone.utc).time()
        if current_time > time_limits[0] and current_time < time_limits[1] and not password_entered:
            print("[+] Waiting for password...")
            # Which means it is exact timespan when connection is expected
            if sock_type == socket.SOCK_STREAM:
                client, addr = server.accept()
                # Preventing the blocking
                r, _, _ = select([client], [], [])
                if client in r:
                    message = client.recv(1024)
                    message = message.decode().strip().replace("\n", "")
                    if message == password: # Get password from config
                        client.send(b"OK")
                        password_entered = True
                        print(f"From: {addr}, Message: {message}")
                        client.close()
                    else:
                        client.close()
            else:
                message, addr = server.recvfrom(1024)
                message = message.decode().strip().replace("\n", "")
                if message == password: # Get password from config
                    password_entered = True
                    print(f"From: {addr}, Message: {message}")
        
        elif current_time > time_limits[1] and not password_entered:
            # Which means time is expired
            print("Time expired, sending the messages from smtp to specified accounts!")
            # Send the mails to specified users
            # Looping through the target users
            for t_user in smtp_cfg["clients"]:
                send_email(
                    smtp_cfg["from"],
                    t_user,
                    smtp_cfg["subject"],
                    smtp_cfg["message"],
                    smtp_cfg["smtp_server_name"],
                    smtp_cfg["smtp_server_port"],

                )
            
        elif password_entered:
            # Password was entered and it was exact same as config, waiting next day and revert password entered value
            print("[+] Password entered successfully, waiting the next day!")
            while str(current_time.hour) != "00":
                # Sleeping for 1 hour
                sleep(60 * 60 * 1000)
                current_time = datetime.now(timezone.utc).time()
            password_entered = False
        else:
            # Waiting for time when password must be entered
            print("[+] Waiting time to expect the password")
            while str(current_time.hour) + ":" + str(current_time.minute) != str(time_limits[0].hour) + ":" + str(time_limits[0].minute):
                # Sleep for 1 minute
                sleep(60 * 1000)
                current_time = datetime.now(timezone.utc).time()



def main() -> None:
    # Parsing command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address that server will be listen on")
    parser.add_argument("--port", type=int, default=56003, help="Port that server will be listening to")
    parser.add_argument("--proto", type=str, default="tcp", help="Socket protocol stack tcp or udp")
    parser.add_argument("--cfg", type=str, default="./config.json", help="Configuration file path")
    args = parser.parse_args()
    # Validating the arguments
    socket_type = socket.SOCK_STREAM if args.proto == "tcp" else socket.SOCK_DGRAM
    conn_data = (args.host, args.port)
    # Load config by specified path
    cfg = load_config(args.cfg)
    if not cfg:
        sys.exit(1)

    time_limits = [
        datetime.strptime(cfg["time_span"][0], "%H:%M:%S.%f").time(),
        datetime.strptime(cfg["time_span"][1], "%H:%M:%S.%f").time()
    ]

    smtp_data = {
        "smtp_server_name": cfg["smtp_server_name"],
        "smtp_server_port": cfg["smtp_server_port"],
        "smtp_server_cred": cfg["smtp_server_cred"],
        "subject": cfg["subject"],
        "message": cfg["message"],
        "from": cfg["from"],
        "clients": cfg["clients"]
    }

    handle_connect(socket_type, conn_data, time_limits, cfg["password"], smtp_data)
    

if __name__ == "__main__":
    main()
