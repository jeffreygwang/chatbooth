import sys, socket
import time
import threading
from threading import Lock, Event
import re
from wireprotocol import *
from typing import List

class Client():
  s: socket.socket = None # client socket
  auth_token = None       # bytestring for authentication w/ server
  buffered_messages: List[str] = []

  def receive_response_from_server(self):
    """
    Get server response for action that requires response.
    """

    # Connect to server (make sure alive)
    try:
      version = receive_sized_int(self.s, 1)
    except:
      print("\n ERROR - Connection lost to server. Please reboot. \n")
      sys.exit(1)

    # Receive rest
    action = receive_sized_int(self.s, 1)
    size = receive_sized_int(self.s, 4)
    body = None
    if size > 0:
      body = receive_sized(self.s, size)

    # Action 11 is used to indicate an incoming message. If we get an action 11
    # message, we want to store it, but then receive the next response incoming
    # from the server, since by the time this function was called, we are expecting
    # an action 10 response.
    if action == 11:
      self.buffered_messages.append(str(body, 'utf-8'))
      return self.receive_response_from_server()

    return action, body

  def receive_success_from_server(self):
    """
    Get server response for action that requires no response. (Confirms byte delivery and exits)
    """
    _, body = self.receive_response_from_server()
    return body is not None

  def send_action_and_body(self, action, body=None, skip_auth_token=False):
    """
    Client-specific method to send an action (with a body, if needed).
    """

    # Connect to server (make sure alive)
    try:
      send_sized_int(self.s, 0, 1)
    except:
      print("\n ERROR - Connection lost to server. Please reboot. \n")
      sys.exit(1)

    send_sized_int(self.s, action, 1)

    # Send body and/or auth token, if needed.
    if body:
      send_sized_int(self.s, len(body), 4)
      self.s.send(body)

    # Some actions allow for skipping the auth token.
    if self.auth_token and not skip_auth_token:
      self.s.send(self.auth_token)

  def authenticate(self, username: str, password: str) -> None:
    """
    Get authentication token for username/password, to ensure current session working.
    """
    self.send_action_and_body(1, bytes(username + ':' + password, 'utf-8'), True)
    response_action, response_body = self.receive_response_from_server()
    self.auth_token = response_body
    return self.auth_token is not None

  def deauthenticate(self) -> None:
    """
    Get rid of secure token for a particular user (called when logging out).
    """
    self.auth_token = None

  def run(self, host, port):
    """
    Build socket and run.
    """
    self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.s.connect((host, port))

  def flush_messages(self) -> None:
    """
    Return buffered messages for display.
    """
    temp_messages = self.buffered_messages
    self.buffered_messages = []
    return temp_messages


