# chatbooth "from scratch" 

This implementation of chatbooth uses our own wire protocol. 

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

## Wire Protocol Design

We had a few important goals in mind for our wire protocol design:
- **Clean/Space-Efficient**: Minimal wire protocol that keeps message sizes small.
- **Flexible with different messages/actions**: Something that can handle messages of any size and different client/server actions with minimal overhead.

To that end, this is what our protocol looks like:
```
(1) 1 byte version #
(2) 1 byte action #
(3) 4 bytes size of body
(4) [size] bytes body
(5) 16 bytes of authentication, if necessary
```

Every interaction between client and server will have a version #, an action #, and a size of body. The rest of the fields depend on client/server specifics.

All strings are formatted in `utf-8`, where each character is 1-4 bytes.

## Unit Tests

We sought to design unit tests that would isolate and test the functionality of individual network components. In particular, our unit tests test these items:
- Signing up
- Listing accounts
- Sending and delivering messages
- Account deletion

## Watchdog: Handling Multiple Connections

Our server spawns a new thread for each incoming connection. As sockets time out, we have a separate "watchdog" thread that monitors sockets that haven't been used and closes them after a certain period of time, along with their corresponding thread.

To handle client/server failures or timeouts, we implemented the following behavior:

Behavior | Client: Timeout | Client: Volunteer Exit | Client: Crash
------------ | ------------ | ------------ | -------------
Server | The server watchdog closes socket connection + thread. If client side tries to connect again, exception caught. | Functionally equivalent to a timeout. The client exits the CLI, causing their socket connection to grow stale. After a certain period of time, the server closes it and cleans up. | Same as the other two.

Notably, the server behavior when encountering different client "endings" is all the same. We decided to let the server simply do "garbage collection" because our client timeout period is short (O(1) minutes). In the future, we might add a "exit" call from the client on a voluntary exit rather than letting it also be swept up by the watchdog.

Behavior | Server: Timeout | Server: Crash
------------ | ------------ | -------------
Client | The client CLI hangs. It has no conception of whether the lag is caused by prolonged request processing or network latency. The user may consider restarting their application. | If the client attempts to read out of a closed socket, it gets caught in a try/except. They are told that connection was lost to the server.

Necessary multi-threaded safety features like mutexes and condition variables are used with the watchdog. 