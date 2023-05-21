# Engineering Notes

As we began considering this project, we began by outlining a list of design questions, in addition to the functionality built in the spec, as guiding principles for our implementations.

The spec as-is is fairly functional. However, one key flaw (in our eyes) is that there is no verification of users. Someone can send a message to "James", a username that exists, and someone else can easily pull the messages of "James". An additional UX problem that can crop up comes from the terminal interface we use for the application: sometimes, due to latency or rapid client actions, a long server response (like listing undelivered messages) can conflict with the next terminal prompt or user input. To address that, we added buffering on the client side.

## Actions

There are **two core layers of actions**: 1) those that require a body, and 2) those that are privileged.

Some client > server requests have a body, like sending a message or creating an account/logging in. These will have a 4-byte integer for the size of the body, followed by the body itself (so the server knows *precisely* how much to read).

Some client > server requests require authentication, like sending a message (which needs a message body) or deleting an account (which doesn't need a message body). After reading the body, depending on what action the client tries to take, the server will check for authentication. This will be a 16-byte secure randomized token given to the client upon creating an account or logging in (and stored on the server side).

There are two core actions the server performs: confirming the success of a client action (log in, account deletion, etc.) or 2) returning information to the client. There are methods for both.

## Action Codes

Each message sent between the client and the server has a corresponding code, represented as a single byte, that indicates the type of the message. These codes are explained as follows:

Code | Action | Body
---|---|---
1 | Authenticate | Username and password, colon-separated
2 | List users | Regex search or newline for all matches
3 | Send message | Username and message body, colon-separated
4 | Manually fetch messages | Username to deliver messages to
5 | Delete account  | Username to delete account for
10 (server to client) | Response to a client-initiated action, such as the list of active users for action 2 or the zero byte for action 3 | Response body from server
11 (server to client) | Incoming message  | Incoming message text


## Separation of Concerns (Important)

An important design aspect of our naive implementation is separation of concerns between server and client. An easy pitfall to fall into with the wire protocol is to perform all application logic on the server side and overload strings when returning messages back to the client. To that end, we only transfer data when **explicitly requested**; all error handling and string parsing is done on the client side.

For instance, when undelivered messages are requested, they are sent back. However, if a client tries to log in with an incorrect password, the server only returns an error token and error message handling is done on the client side. Importantly, we don't perform UX processing on the server side.

## Message Buffering

We considered two solutions to real-time message delivery for those already logged in:

**First Solution**: The first was to keep a background thread pulling messages, "buffering" those messages until the next time the client is available (e.g. not typing in a command), and delivering. This is a "streaming"-type solution, which we planned to implement by peaking into the socket with the `MSG_PEEK` flag. However, this is somewhat difficult in practice because any errors in buffering bytes (e.g. accidentally reading in another type of message, being off by one, etc.) can be catastrophic.

**Final Solution**: Functionally, however, the above solution just waits until the client has made some command line interaction and then drops in the messages. Instead, we pull for messages each time the client interacts with the command line and display any if they are queued. This is slightly more server calls but substantively easier to implement.

## Passwords

While the server is running, we want to keep user experiences more secure. To that end, we use passwords.

**The First Implementation**

We began with the following client/server implementation that performed an initial authentication of username/password:

```
- the CLIENT makes a request to the SERVER to:
    1) create an account
    2) log in to an account
- the SERVER verifies this action with information passed by the CLIENT.
- if successful, the CLIENT has a hidden field `signed_in_user` that populates with their username

From then on...
- On any actions that require verification (like message sending), the CLIENT passes `signed_in_user` to the server
- the SERVER accepts the username as proof that the CLIENT logged in, and performs the action.
- if the CLIENT wants to sign out, `signed_in_user` is cleared.
- if the CLIENT logs back in, `signed_in_user` is populated again.
```

At first glance, this seems like a reasonable way for someone to perform privileged actions without having to provide authentication (e.g. a username and password) each time. It is similar to some of the earlier solutions used to keep someone logged into a website; after log in, the website keeps a cookie in the user's session that is provided alongside any HTTP request to perform a privileged action. In our case, the "cookie" is just the username, and the usernames are all listable by any user! This means a malicious actor, if they knew the workings of the code and wire protocol, could make priviliged actions on behalf of any user. Not so good...

To protect against these attacks, we changed our implementation to give every client a secure 16-byte token randomized token that is required for privileged actions; this means random actors can't simply make server requests on others' behalf. See the next section for more details.

> It turns out that exploits of our first password implementation are similar in spirit to an early web attack. Early solutions for staying logged in throughout web sessions were unfortunately vulnerable to a key exploit: if users could be socially engineered to perform certain actions (like clicking a link somewhere), those actions could trigger a [**cross site request forgery (CRSF)**](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) attack. These attacks would then send a malicious POST request to the server using the user's credentials (basically taking advantage of the fact that the user, by logging in previously, was already in the "walled garden"). The **solution** to CRSF attacks is similar to what we did, which is that websites use [**authentication tokens**](https://crashtest-security.com/csrf-token-meaning/) for secure actions.

**The Second Implementation**

On a second go, our implemntation now looks like this:

```
- the CLIENT makes a request to the SERVER to:
    1) create an account
    2) log in to an account
- the SERVER verifies this action with information passed by the CLIENT.
- if successful, the SERVER passes an `auth_token` to the CLIENT.

From then on...
- On any actions that require verification (like message sending), the CLIENT passes an `auth_token` to the server.
- the SERVER accepts the token as proof that the CLIENT logged in, and performs the action.
- if the CLIENT wants to sign out, `auth_token` is cleared.
- if the CLIENT logs back in, `auth_token` is populated again with a new randomized bytestring.
```

This implementation is now secure against malicious requests!

## Improvements For The Future

To improve in the future, we would consider a few more robustness improvements on the server side:
- Persistent memory. Since Jim said that this application didn't need to have a database and could store everything in memory, that is what we do. However, it would make more sense at some point to introduce persistent memory so that passwords/accounts/etc are not completely wiped out when a server instance stops running.
- Graceful exits. In a live application, the servers sometimes need to be taken down for maintenance. In this case, creating a server call that can gracefully close all client connections and shut itself down would be useful.
