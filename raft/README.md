# distributed chatbooth with Raft

Here, we took the GRPC version of chatbooth and created it to be persistent and fault tolerant. 

To do so, we implemented **Raft**, a distributed consensus algorithm, to handle leader elections, communication, and file replication between systems.

## Installation & Setup

There are only three dependencies:
- Python 3.8+ (3.7 should work too)
- grpcio
- protobuf

You can install these manually or use `conda`/`pip`. See the `yml` and `requirements.txt` files under `installation` (note that there are different env.yml files for conda depending on whether you use an x86 or Apple Silicon/ARM system). 

## Testing

Our system is easily testable on a local device. During initialization, we label the servers and whether they are leader/follower. We note that the order of initialization is important: we _require_ that the leader replica is booted up first, since it needs to communicate to all other follower replicas. This is important because if a follower replica is booted up first, it will attempt to ping the leader, get no response, assume it is dead, put itself up as a candidate, and then the remaining specifications for other machines will be wrong. As such, one would run each of these commands, in sequence, in the command line (one per window):

```
# servers
python3 main.py --server --server_id a --port 8001 --replica_ids b,c --replica_urls localhost:8002,localhost:8003
python3 main.py --server --server_id b --port 8002 --replica_ids a,c --replica_urls localhost:8001,localhost:8003 --leader_id a
python3 main.py --server --server_id c --port 8003 --replica_ids a,b --replica_urls localhost:8001,localhost:8002 --leader_id a

# client
python main.py --servers localhost:8001,localhost:8002,localhost:8003
[other client instances]
```

We can also test this between devices, except we change `localhost` to another computer IP. See below. 

**Persistence** is an option we have built into our code. This means users can activate it if they like. The regular run shown above does not use it; the one below does. 

```
# servers
python3 main.py --server --server_id a --port 8001 --replica_ids b,c --replica_urls localhost:8002,localhost:8003 --server_storage eighty_01
python3 main.py --server --server_id b --port 8002 --replica_ids a,c --replica_urls localhost:8001,localhost:8003 --leader_id a --server_storage eighty_02
python3 main.py --server --server_id c --port 8003 --replica_ids a,b --replica_urls localhost:8001,localhost:8002 --leader_id a --server_storage eighty_03

# client
python main.py --servers localhost:8001,localhost:8002,localhost:8003
```

Across multiple machines, this looks like:

```
# Marco
python3 main.py --server --server_id a --port 8001 --replica_ids b,c --replica_urls localhost:8002,10.250.11.117:8003 --server_storage a
python3 main.py --server --server_id b --port 8002 --replica_ids a,c --replica_urls localhost:8001,10.250.11.117:8003 --server_storage b --leader_id a
python3 main.py --servers localhost:8001,localhost:8002,10.250.11.117:8003

# Jeffrey
python3 main.py --server --server_id c --port 8003 --replica_ids a,b --replica_urls 10.250.188.35:8001,10.250.188.35:8002 --leader_id a --server_storage eighty_03
python main.py --servers 10.250.188.35:8001,10.250.188.35:8002,localhost:8003
```

**Client-side behavior**: We assume that the client knows all servers that exist. When the client's current server-in-communication times out, the client throws an error when it attempts to communicate to that server. It then "updates the active server by popping the current one in its list and going to the next one.

## High-Level Details

Here, we give a brief description of Raft and how it is used in our algorithm:
- Raft divides the distributed consensus problem into three subproblems: leader election, log replication, and safety.
- In Raft, there is a leader who is responsible for managing the replication of the log. Other nodes are followers who replicate the log. This is like the primary/secondary or leader/follower approach to consensus. 
- If the leader fails, a new leader is elected using a randomized timeout mechanism. In brief, whenever a replica does not get a heartbeat from a leader, it becomes a _candidate_ for the leader; if a majority of other nodes get its candidacy and vote for it, it becomes the leader. 
- The leader receives commands from clients and appends them to its log. The leader then replicates its log to followers, who in turn replicate it to other followers.
- Raft ensures safety by enforcing a rule that a log entry can only be committed if it has been replicated on a majority of the nodes.

One asterisk of our implementation is that all server-server communication is done via the heartbeats, since the data packages are so small. 

## Unit Testing

We implemented unit tests to test the functions of different client operations, as well as the persistence of memory. Briefly, this creates a server instance, creates two accounts on it, fires up another server instance that loads from the data of the first one, and checks if those two accounts are there. 

We _did not_ implement unit tests for failing machines because this felt antithetical to the very goal of building something resilient to unexpected failures. In lieu of modularized code unit tests, we tested Raft across a dynamic set of environments, which we believe encompass much of the "hair" of the implementation:

| Tests    | 3M:NM1 | 3M:NM2 | 3M:CR1 | 3M:CR2 | 5M:CR2 | 5M:CR4 |
| :---     |    :----:   |   :---: |    :----:   |    :----: |    :----: | :---: |
|    Status   |  ✅  | ✅   |  ✅  |  ✅  |  ✅ |  ✅  |

which corresponds to:
- 3M:NM1 - 3 Machines where a network failure cuts off 1 machines. 
- 3M:NM2 - 3 Machines where a network failure cuts off 2 machines.
- 3M:CR1 - 3 Machines where one machine crashes (cmd+c).
- 3M:CR2 - 3 Machines where two machines crash (cmd+c).
- 5M:CR2 - 5 Machines where two machines crash (cmd+c).
- 5M:CR4 - 5 Machines where four machines crash (cmd+c). 

## Style

For readability, we follow PEP-8, the Python style spec, where possible (e.g. docstrings, method formatting, etc.). 



