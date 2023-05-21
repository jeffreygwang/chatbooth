import sys
from client_cli import *
from server import *
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--server', default=False, action='store_true')
parser.add_argument('--host', default="localhost")
parser.add_argument('--port', type=int)
args = parser.parse_args()

if args.port == None:
  print('Please specify a port.')
else:
  if args.server:
    server = Server()
    server.start(args.port)
  else:
    cli = ClientCli()
    cli.main(args.host, args.port)
