# chatbooth: a real-time (distributed) chat app

Created for CS 262, Harvard's graduate-level distributed systems class. Engineering design, code, and notebooks done by Jeffrey Wang and Marco Burstein. 

**chatbooth** is an application that allows users to exchange messages via the command-line. Two versions of this application utilize a simple client-server paradigm, one with our own memory-efficient wire protocol and another using protocol buffers in gRPC, Google's remote procedure call framework, to serialize and transmit data. These are available in `wireprot` and `grpc`, respectively. 

The final version of this app builds on the gRPC implementation and adds fault-tolerance and persistence. This is done by building on the **Raft** consensus algorithm and adding the option of persistence (messages can be saved even when the server shuts down). 

**Functionality** Users can:
- Create/delete accounts with a username/password
- List other accounts (including by regex)
- Send/receive messages in real time (and receive messages missed when gone)

Run instructions and engineering writeups are available in each implementation's directory. 
