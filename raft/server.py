import sys, socket
import time
import threading
import re
import uuid
from concurrent import futures
import grpc
import service_pb2
import service_pb2_grpc
from threading import Lock, Event
from typing import List, Dict
import os
import os.path
import pickle
from raft_manager import *

class ReplicaUpdateData: # utility class to wrap up replica information
  def __init__(self, client_messages, client_passwords, client_tokens):
    self.client_messages = client_messages
    self.client_passwords = client_passwords
    self.client_tokens = client_tokens

# A GRPC Servicer that handles the server's actions.
class ServerServicer(service_pb2_grpc.MessageServiceServicer):
  def __init__(self, replica_id=None, leader_id=None, replicas={}, out_file=None):
    super().__init__()

    # A mutex used for accessing state dictionaries, to prevent overwrites.
    self.mutex = Lock() # TODO - need to mutex everything before saving? 

    # A map of client usernames to the messages they've received.
    self.client_messages: Dict[str, List[str]] = {}

    # A map of client usernames to their passwords.
    self.client_passwords: Dict[str, str] = {}

    # A map of client usernames to their authentication tokens, used instead of
    # passwords after the initial authentication.
    self.client_tokens: Dict[str, bytes] = {}

    # Create raft entity, with replica information
    self.raft_manager = RaftManager(replica_id, leader_id, replicas, self.load_raft_data, self.on_raft_data)
    self.out_file = out_file

    if self.out_file and os.path.isfile(self.out_file):
      self.load_file_data()

  def save_file_data(self):
    """
    Save to persistent memory by pickling.
    """
    if not self.out_file:
      return

    with open(self.out_file, 'wb') as file:
      pickle.dump(self.load_raft_data(), file)

  def load_file_data(self):
    """
    Mechanism to load persistent memory.
    """
    if not self.out_file:
      return

    with open(self.out_file, 'rb') as file:
      loaded = pickle.load(file)
      self.client_messages = loaded.client_messages
      self.client_passwords = loaded.client_passwords
      self.client_tokens = loaded.client_tokens

  def load_raft_data(self):
    """
    Mechanism to load raft data.
    """
    return ReplicaUpdateData(self.client_messages, self.client_passwords, self.client_tokens)

  def on_raft_data(self):
    """
    When it gets heartbeat with most recent data, updates replica. 
    """
    unloaded = self.raft_manager.latest_data
    self.client_messages = unloaded.client_messages
    self.client_passwords = unloaded.client_passwords
    self.client_tokens = unloaded.client_tokens
    self.save_file_data()

  def check_authentication(self, request):
    """
    Check if user is logged in (with authentication token sent in message).
    """
    for username in self.client_tokens:
      if self.client_tokens[username] == request.token:
        return username

  def RaftRequestVote(self, request, context): 
    """
    Server-side method for requesting votes from other replicas.
    """
    return self.raft_manager.on_request_vote(request)

  def RaftUpdateState(self, request, context):
    """
    TODO
    """
    return self.raft_manager.on_heartbeat(request)

  def Authenticate(self, request, context):
    """
    Authenticate a login, or create an account.
    """

    # If not leader, forward request.
    if not self.raft_manager.is_leader():
      response = self.raft_manager.leader_stub().Authenticate(service_pb2.AuthenticateRequest(username=request.username, password=request.username))
      return response

    username = request.username
    password = request.password

    # Check to see if the user already exists.
    if username in self.client_messages:
      # If so, try signin in.
      if self.client_passwords[username] == password:
        print(f'User {username} logged in successfully.')
        return service_pb2.StringResponse(success=True, response=self.client_tokens[username])
      else:
        print(f'User {username} failed to login.')
        return service_pb2.StringResponse(success=False, response="")
    else:
      # Otherwise, create an account, if they match the parameters.
      if re.match('^[a-zA-Z_]+$', username) and len(password) > 0:
        self.mutex.acquire()
        self.client_messages[username] = []
        self.client_passwords[username] = password
        self.client_tokens[username] = str(uuid.uuid4())
        self.save_file_data()
        self.mutex.release()
        print(f'User {username} created successfully.')
        return service_pb2.StringResponse(success=True, response=self.client_tokens[username])
      else:
        print(f'User {username} failed to sign up.')
        return service_pb2.StringResponse(success=False, response="")

  def List(self, request, context):
    """
    List accounts, separated by a comma.
    """
    if not self.raft_manager.is_leader():
      return self.raft_manager.leader_stub().List(service_pb2.ListRequest(token=request.token, request=request.request))

    # Requests must be authenticated.
    if not self.check_authentication(request):
      return service_pb2.StringResponse(success=False, response="")

    body = request.request
    if body == "\n":
      print("No regex received from client. Returning all account usernames.")
      return service_pb2.StringResponse(success=True, response=','.join(self.client_messages.keys()))
    else:
      try:
        pattern = re.compile(body)
        matches = []
        for uname in self.client_messages.keys():
          if pattern.search(uname):
            matches.append(uname)
        print('Sent usernames matching regex.')
        return service_pb2.StringResponse(success=True, response=','.join(matches))
      except re.error:
        return service_pb2.StringResponse(success=False, response="")

  def Send(self, request, context):
    """
    Add a message to someone's undelivered.
    """
    if not self.raft_manager.is_leader():
      return self.raft_manager.leader_stub().Send(service_pb2.SendRequest(token=request.token, username=request.username, body=request.body))

    # Requests must be authenticated.
    if not self.check_authentication(request):
      return service_pb2.EmptyResponse(success=False)

    if request.username not in self.client_messages:
      return service_pb2.EmptyResponse(success=False)
    else:
      self.mutex.acquire()
      self.client_messages[request.username].append(request.body)
      self.save_file_data()
      self.mutex.release()
      print('Sent message.')
      return service_pb2.EmptyResponse(success=True)

  def Deliver(self, request, context):
    """
    Pull user's undelivered messages and send to them.
    """
    if not self.raft_manager.is_leader():
      return self.raft_manager.leader_stub().Deliver(service_pb2.DeliverRequest(token=request.token))

    # Requests must be authenticated. In this case, we assume delivery to the
    # user who sent the request.
    matching_username = self.check_authentication(request)

    if not matching_username:
      return service_pb2.StringResponse(success=False, response="")

    response_str ="\n\n".join(self.client_messages[matching_username])
    self.mutex.acquire()
    self.client_messages[matching_username] = []
    self.save_file_data()
    self.mutex.release()

    return service_pb2.StringResponse(success=True, response=response_str)

  def Delete(self, request, context):
    """
    Delete account.
    """
    if not self.raft_manager.is_leader():
      return self.raft_manager.leader_stub().Deliver(service_pb2.DeleteRequest(token=request.token, username=request.username))

    # Requests must be authenticated. In this case, we assume deletion of the
    # account that sent the request.
    if not self.check_authentication(request):
      return service_pb2.EmptyResponse(success=False)

    if request.username not in self.client_messages:
      return service_pb2.EmptyResponse(success=False)

    self.mutex.acquire()
    del self.client_messages[request.username]
    del self.client_passwords[request.username]
    del self.client_tokens[request.username]
    self.save_file_data()
    self.mutex.release()

    print(f'Deleted account for {request.username}.')
    return service_pb2.EmptyResponse(success=True)

# A server that can start the GRPC servicer on a given port.
class Server():
  def __init__(self, replica_id=None, leader_id=None, replicas={}, out_file=None):
    self.servicer = ServerServicer(replica_id=replica_id, leader_id=leader_id, replicas=replicas, out_file=out_file)

  def start(self, port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    service_pb2_grpc.add_MessageServiceServicer_to_server(self.servicer, server)
    server.add_insecure_port('[::]:' + str(port))
    server.start()
    server.wait_for_termination()
  
  def force_close(self):
    sys.exit(0)
