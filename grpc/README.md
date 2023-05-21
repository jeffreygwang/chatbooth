# chatbooth (gRPC)

This implementation uses gRPC and protocol buffers to transmit information/requests.

## Installation & Setup

There are only three dependencies:
- Python 3.8+ (3.7 should work too)
- grpcio
- protobuf

You can install these manually or use `conda`/`pip`. See the `yml` and `requirements.txt` files under `installation` (note that there are different env.yml files for conda depending on whether you use an x86 or Apple Silicon/ARM system). 

## To Run

Client: 
```
python main.py --host [host] --port [port]
```

Server: 
```
python main.py --server --port [port]
```

For instance:

```
# Client
python main.py --host 172.20.10.7:8080 --port 8000

# Server
python main.py --server --port 8080
```

## Packet Sizes

For an empirical comparison of the naïve implementation and the GRPC implementation, we started a `tcpdump` session and completed the following simple actions in both codebases:

1. Started the server and the client.
2. Created a user named `test` with password `password`.
3. Listed users.
4. Quit the client.

Our full `tcpdump` logs can be found in [tcpdump-grpc.txt]() and [tcpdump-naive.txt](). In summary, we found the following:

 | Naïve | GRPC
| -------| -------- |
Maximum packet length | 22 | 289
Average non-0 packet length | 6.9 | 64.7
Non-0 packet count | 20 | 30

As shown above, our naïve implementation uses both fewer and smaller packets. Intuitively, this makes sense, as our wire protocol was designed to use the minimum number of bytes possible to reasonably convey the given information, while the GRPC functionality for each message likely extends beyonds the needs of this project. In other words, while GRPC allows for more flexibility and a robust protobuf-based architecture, it also adds an additional byte overhead that can be removed using lower-level socket engineering.

## Comparing gRPC with a naive wire protocol

We found in **design** and **code** simplicity that gRPC was simplifing. However, one one downside of GRPC is that it requires additional dependencies both to compile the protobuf file and execute the resulting server code. Additionally, we found that GRCP had reduced flexibility when compard to the pure socket approach. For instance, when relying on sockets directly, we were able to arbitrarily deliver messages to the client at any time from the server. However, this is not possible using GRPC's standard RPC definitions, which rely on synchronous responses for each function in the service. GRPC does have a "stream" mode, but this still requires the client to initiate the RPC call, whereas sockets allow us to send messages to clients without their explicitly asking to receive them.

Lastly, the naïve approach allowed us to more quickly modify and debug our code, changing our wire protocol at will, whereas GRPC would require recompiling with each change to our protocol. This flexibility is both a pro and a con, as it makes dev work more agile but also more prone to breaking.





