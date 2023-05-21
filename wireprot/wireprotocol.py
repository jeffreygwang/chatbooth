"""
Chat Application Wire Protocol: 
(1) 1 byte version #
(2) 1 byte action #
(3) 4 bytes size of body
(4) [size] bytes body 
(5) 16 bytes of authentication, if necessary (only client > server does this)
"""

import sys

def receive_sized_int(s, size: int) -> int:
  """
  Convert [size] bytes to big-endian int. 
  """
  return int.from_bytes(receive_sized(s, size), 'big')

def receive_sized_string(s, size: int) -> str:
  """
  Convert [size] bytes to string.
  """
  return receive_sized(s, size).decode('utf-8')

def receive_sized(s, size: int) -> bytes:
  """
  Receive [size] bytes. Turn over to receive_sized_int or received_sized_string for decoding.
  """
  combined = b''

  while True:
    try:
      msg = s.recv(size)
    except: # this happens when the thread running the program is killed by the watchdog
      sys.exit(0)
    
    combined += msg
    if len(combined) >= size:
      return combined

def send_sized_int(s, num: int, size: int) -> None: 
  """
  Send an integer [num] of [size] bytes
  """
  s.send(num.to_bytes(size, 'big'))

ZERO_BYTE = int.to_bytes(0, 1, 'big')       # big-endian single byte rep of 0, used when no action taken
