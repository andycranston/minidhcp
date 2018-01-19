# minidhcp

A miniature DHCP server run from the command line to assign
a IPv4 address to a single host identified by MAC address.

## What minidhcp does

The minidhcp program (which is written in Python 3 in a single file
called `minidhcp.py`) assigns an IPv4 address to a host via the DHCP
protocol.  It also assigns a subnet mask and a default gateway.

The IP address, subnet mask and default gateway are specified
as command line options.

## Why is minidhcp useful?

Because it gives you control over exactly what IP address is assigned
and makes sure only the device you name (by specifying the device
MAC address) is offered that IP address.

## How to get started

You need Python 3 installed in your environment.

You also need appropriate access priviledges to be able to send and receive
network packets on the well known DHCP TCP/IP port number 67.  Typically this means `root` access on UNIX/Linux and `Administrator` access on Windows.

If any firewalls are running they must allow DHCP traffic in and out
on the networ interface that minidhcp will bind to:

This is how I make use of `minidhcp` on my Windows 10 laptop.

I make sure I have set a static IP address on the ethernet port on my laptop.  I usually assign:

* Static IP: 192.168.2.53
* Subnet mask: 255.255.255.0
* Default gateway: 192.168.2.254

Next connect a network lead from the laptop ethernet port to the device you
want to assign an IP address to and power the device on.

Next open a command prompt on the laptop.

Change to the directory where the `minidhcp.py` script has been copied to.

Next run `minidhcp` as follows:

```
python minidhcp.py -m b8:27:eb:c3:27:b5 -b 192.168.2.53 -i 192.168.2.100 -s 255.255.255.0 -g 192.168.2.254
```

If all is well `minidhcp` listens for DHCP packets.  Any packets which are
not from the specified MAC address (command line option "-m") are ignored.
When a DHCP DISCOVER packet is recieved a DHCP OFFER packet is sent.
If the device likes the DHCP OFFER it should send a DHCP REQUEST packet.
On receipt of the DHCP REQUEST packet minidhcp sends a DHCP ACK packet.

At this stage the device should assign the IP address, subnet mask and
default gateway with a lease time of 24 hours.

Now try and access the device using IP address:

* 192.168.2.100

from the laptop.  If that works they `minidhcp` has done its work.
Stop the script running by typing Ctrl ^C (UNIX/Linix) or
Ctrl break (Windows).

## Warnings

Running any DHCP server (including `minidhcp`) requires care.  If the
server is run on a network segment that already has a DHCP server
running on it then bad things can (and usually do) happen.  Depending
on the environment you might end up get shouted at (easy) or losing
your job (disaster!) so ask the appropriate people such as your boss or
the network adminstrator if you have any doubts at all before running
`minidhcp`.

The `minidhcp` server only implements half of the DHCP protocol - the
bit where an IP address is initially allocated.  When the lease runs out
behaviour is unpredictable and will usually result in losing
network connection to the device.

The primary use of `minidhcp` is "get the device online so it can
be accessed and a static IP set so it does not need DHCP".

## Coding style

The Python 3 source code for `minidhcp.py` is not very "Pythonic".  Infact
there are probably lots of things it is not that it should be.

## Credits

The online [TCP/IP Guide](http://www.tcpipguide.com/) by Charles M. Kozierok
was invaluable.
