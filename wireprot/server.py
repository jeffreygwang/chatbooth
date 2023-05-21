import sys, socket
import time
import threading
from threading import Lock, Event
import re
import uuid
from wireprotocol import *
from typing import Tuple, Dict, List

class Server:
  # A mutex used to syncronize edits to state.
  mutex = Lock()

  # A map of usernames to undelivered messages
  client_messages: Dict[str, List[str]] = {}

  # A map of usernames to passwords, used for initial authentication.
  client_passwords: Dict[str, str] = {}

  # A map of usernames to auth tokens.
  client_tokens: Dict[str, bytes] = {}

  # A map of usernames to sockets, used for delivering messages.
  client_sockets: Dict[str, socket.socket] = {}

  # A map of sockets to the last time that a message was received on that socket.
  sockets_watchdog: Dict[socket.socket, float] = {}

  def send_body(self, s: socket.socket, action: int, body: int) -> None:
    """
    Send a message via wire protocol to client.
    """

    try:    # Send version #
      send_sized_int(s, 0, 1)
    except: # If client terminates connection suddenly
      print("ERROR - Connection lost to client.")
      del self.sockets_watchdog[s]
      return

    # Send action, length of body, and body.
    send_sized_int(s, action, 1)
    send_sized_int(s, len(body), 4)
    s.send(body)

  def send_error(self, s: socket.socket, action: int) -> None:
    """
    Server-specific method to send that an error occurred to the client.
    Same as send_body except sends a zero int.
    """
    try:    # Send version #
      send_sized_int(s, 0, 1)
    except: # If client terminates connection suddenly
      print("ERROR - Connection lost to client.")
      del self.sockets_watchdog[s]
      return

    send_sized_int(s, action, 1)
    send_sized_int(s, 0, 4)

  def check_authentication(self, s: socket.socket) -> None:
    """
    Check if user authentication token correct (for secure/pswd-protected features).
    """
    token = receive_sized(s, 16)
    for username in self.client_tokens:
      if self.client_tokens[username] == token:
        return username

  def test_close(self) -> None:
    """
    Closure (for unit tests). Not deployed in production.
    """
    to_remove = []

    for s in self.sockets_watchdog:
      s.shutdown(socket.SHUT_RDWR)
      s.close()
      to_remove.append(s)

    self.mutex.acquire()
    for s in to_remove:
      del self.sockets_watchdog[s]
    self.mutex.release()

  def watchdog(self) -> None:
    """
    Spawn a new thread, and poll every 5 seconds other threads for closure.
    Note that sockets_watchdog maintains the last connection by thread to server.
    """
    while True:
      time.sleep(5)
      to_remove = []
      for s in self.sockets_watchdog:
        timediff: float = time.time() - self.sockets_watchdog[s] # time difference b/t now and last client request

        if timediff > 600: # Kill threads inactive for > 600 seconds.
          print(f"Shutting down socket {str(s)}")
          s.shutdown(socket.SHUT_RDWR)
          s.close()
          to_remove.append(s)

      # Next, close any sockets that were marked as to remove.
      self.mutex.acquire()
      for r in to_remove:
        del self.sockets_watchdog[r]
        for u in list(self.client_sockets):
          if self.client_sockets[u] == s:
            del self.client_sockets[u]
      self.mutex.release()

  def server_client_loop(self, s: socket.socket) -> None:
    """
    Main server/client logic.
    """
    while True:
      if s not in self.sockets_watchdog:
        return

      version = receive_sized_int(s, 1)
      print('Incoming action...')

      # Update the watchdog time for this socket.
      self.mutex.acquire()
      self.sockets_watchdog[s] = time.time()
      self.mutex.release()

      if version == 0:
        action = receive_sized_int(s, 1)
        print(f'Received action {action}.')

        if action == 1:
          # Authenticate
          size = receive_sized_int(s, 4)
          body = receive_sized_string(s, size)

          # body contains username:password
          index_colon = body.index(':')
          username = body[:index_colon]
          password = body[index_colon+1:]

          if username in self.client_messages: # If user exists already...
            if self.client_passwords[username] == password:
              for other_username in list(self.client_sockets):
                if self.client_sockets[other_username] == s:
                  del self.client_sockets[other_username]
              self.client_sockets[username] = s
              self.send_body(s, 10, self.client_tokens[username])
              print(f'User {username} logged in successfully.')
            else:
              self.send_error(s, 10)
              print(f'User {username} failed to login.')
          else: # If user DNE
            if re.match('^[a-z_]+$', username) and len(password) > 0: # valid usernames must be alphabetical
              self.mutex.acquire()
              # Remove any other usernames tied to this socket, such as
              # if the user signed out and signed in again on the same socket.
              for other_username in list(self.client_sockets):
                if self.client_sockets[other_username] == s:
                  del self.client_sockets[other_username]

              # Create new keys in the state dictionaries
              self.client_sockets[username] = s
              self.client_messages[username] = []
              self.client_passwords[username] = password
              self.client_tokens[username] = uuid.uuid4().bytes
              self.mutex.release()
              self.send_body(s, 10, self.client_tokens[username])
              print(f'User {username} created successfully.')
            else:
              self.send_error(s, 10)
              print(f'User {username} failed to sign up.')

        elif action == 2:
          # List
          size = receive_sized_int(s, 4)
          body = receive_sized_string(s, size)
          username = self.check_authentication(s)

          if not username:
            self.send_error(s, 10)
            continue

          if body == "\n":
            print("No regex received from client. Returning all account usernames.")
            self.send_body(s, 10, bytes(','.join(self.client_messages.keys()), 'utf-8'))
          else:
            try:
              pattern = re.compile(body)
              matches = []
              for uname in self.client_messages.keys():
                if pattern.search(uname):
                  matches.append(uname)
              self.send_body(s, 10, bytes(','.join(matches), 'utf-8'))
              print('Sent usernames matching regex.')
            except re.error:
              self.send_error(s, 10)
        elif action == 3:
          # Send
          size = receive_sized_int(s, 4)
          body = receive_sized_string(s, size)
          username = self.check_authentication(s)

          if not username:
            self.send_error(s, 10)
            continue

          index = body.index(':')
          username = body[0:index]
          text = body[index+1:]

          if username not in self.client_messages:
            self.send_error(s, 10)
          else:
            self.mutex.acquire()
            self.client_messages[username].append(text)

            # If they have an active socket, we want to send those messages.
            if username in self.client_sockets:
              for message in self.client_messages[username]:
                print(f'Delivering message to {username}.')
                self.send_body(self.client_sockets[username], 11, bytes(message, 'utf-8'))
              self.client_messages[username] = []

            self.mutex.release()

            # Send the zero byte to indicate success.
            self.send_body(s, 10, ZERO_BYTE)
            print('Sent message.')
        elif action == 4:
          # Deliver
          size = receive_sized_int(s, 4)
          body = receive_sized_string(s, size)
          username = self.check_authentication(s)

          if not username:
            self.send_error(s, 10)
            continue

          if body not in self.client_messages:
            self.send_error(s, 10)
          else:
            # If they have an active socket, we want to send the messages.
            for message in self.client_messages[body]:
              if body in self.client_sockets:
                print(f'Delivering message to {body}.')
                self.send_body(self.client_sockets[body], 11, bytes(message, 'utf-8'))

            self.mutex.acquire()
            self.client_messages[body] = []
            self.mutex.release()

            # Send the zero byte to indicate success.
            self.send_body(s, 10, ZERO_BYTE)
            print('Delivered messages.')
        elif action == 5:
          # Delete
          size = receive_sized_int(s, 4)
          body = receive_sized_string(s, size)
          username = self.check_authentication(s)

          if not username:
            self.send_error(s, 10)
            continue

          self.mutex.acquire()
          del self.client_messages[body]
          del self.client_sockets[body]
          del self.client_passwords[body]
          del self.client_tokens[body]
          self.mutex.release()

          self.send_body(s, 10, ZERO_BYTE)
          print(f'Deleted account for {username}.')

  def start(self, port):
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.bind(('', port))
    serversocket.listen()

    threading.Thread(target=self.watchdog, daemon=True).start()

    while True:
      s, _ = serversocket.accept()
      self.mutex.acquire()
      self.sockets_watchdog[s] = time.time()
      self.mutex.release()
      threading.Thread(target=self.server_client_loop, args=(s,)).start()

