# Importing the Bluetooth Socket library
import bluetooth

host = ""
port = 1  # Raspberry Pi uses port 1 for Bluetooth Communication
# Creaitng Socket Bluetooth RFCOMM communication
server = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
print('Bluetooth Socket Created')
try:
    server.bind((host, port))
    print("Bluetooth Binding Completed")
except:
    print("Bluetooth Binding Failed")

#for i in range(1,2):
server.listen(7)  # One connection at a time
# Server accepts the clients request and assigns a mac address.
client, address = server.accept()
print("Connected To", address)
print("Client:", client)

#server.listen(2)  # One connection at a time
# Server accepts the clients request and assigns a mac address.
client2, address2 = server.accept()
print("Connected To", address2)
print("Client:", client2)

# try:
#     #pass
#     write = 'String from Raspberry Pi'
#     print(write)
#     #print(write.encode('utf-8'))
#     client.send(write.encode('utf-8'))
# except:
#     pass

try:
    while True:
        # Receivng the data.
        data = client.recv(1024)  # 1024 is the buffer size.
        command = data.decode("utf-8")  # converts binary to string

        data2 = client2.recv(1024)  # 1024 is the buffer size.
        command2 = data2.decode("utf-8")  # converts binary to string
        #print(data)  # data is binary
        print(command)
        print(command2)

        if data == "1":
            send_data = "Light On "
        elif data == "0":
            send_data = "Light Off "
        else:
            send_data = "Type 1 or 0 "
        # Sending the data.
        client.send(send_data)

        write = 'String from Raspberry Pi after received message'
        #print(write)
        print(write.encode('utf-8'))
        client.send(write.encode('utf-8'))
except:
    # Closing the client and server connection
    client.close()
    server.close()