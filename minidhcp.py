#
# @(!--#) @(#) minidhcp.py, version 012, 16-january-2018
#
# a mini dhcp server in Python using sockets to serve
# just one host
#
# use Ctrl+Break instead of Ctrl^C to interrupt
#

##############################################################################

#
# Help from:
# ---------
#
#    https://pymotw.com/2/socket/tcp.html
#    https://pymotw.com/2/socket/udp.html
#    http://www.tcpipguide.com/free/t_DHCPMessageFormat.htm
#

#
# Packet format
# -------------
#
# Offset    Length   Notes
# ------    ------   -----
#
#   0       1        Operation code with 1 being request and 2 being response
#   1       1        Hardware type with 1 being "Ethernet 10Mb"
#   2       1        Hardware address length with 6 for Ethernet
#   3       1        Hops - usually 0 unless DHCP relaying in operation
#   4-7     4        Transaction ID (selected randomly by client)
#   8-9     2        Seconds - might be used by a server to prioritise requests
#  10-11    2        Flags (only most significan bit used for broadcast)
#  12-15    4        Client Internet address (might be requested by client)
#  16-19    4        Your Internet address (the IP assigned by the server)
#  20-23    4        Server Internet address (the IP of the server)
#  24-27    4        Gateway Internet address (if DHCP relaying in operation)
#  28-43    16       Client hardware address - only first 6 bytes used for Ethernet
#  44-107   64       Text name of server (optional)
# 108-235   128      Boot file name (optional - used for PXE booting)
# 236-239   4        Magic cookie (decimal values 99, 130, 83, 99 )
#

#
# DHCP option codes
# -----------------
#
# 1   - Subnet mask
# 3   - Router(s)
# 6   - DNS name server(s)
# 12  - Hostname
# 15  - Domain name
# 28  - Broadcast address
# 33  - Static route
# 42  - Network time protocol servers
# 51  - 
# 53  - DHCP Message Type (DHCPDISCOVER, DHCPOFFER, etc)
# 54  - Server identifier
# 55  - Parameter Request List
# 57  - Maximum DHCP Message Size
# 58  - Renewal (T1) time value
# 59  - Renewal (T2) time value
# 60  - Vendor Class Identifier
# 61  - Client Identifier
# 80  - 
# 116 - 
# 119 - 
# 145 -
# 167 - 
# 171 -  
#

#
# Lease times
# -----------
#
# 24 hours = 24 hours * 60 minutes * 60 seconds = 86400 seconds
#     86400 / 16777216 = 0   remainder 86400
#     86400 / 65536    = 1   remainder 20864
#     20864 / 256      = 81  remainder 128
#     128   / 1        = 128 remainder zero
# 24 hours lease = 0, 1, 81, 128 four byte word
#
# 21 hours = 21 hours * 60 minutes * 60 seconds = 75600 seconds
#     75600 / 16777216 = 0   remainder 86400
#     75600 / 65536    = 1   remainder 10064
#     10064 / 256      = 39  remainder 80
#     80    / 1        = 80  remainder zero
# 21 hours lease = 0, 1, 39, 80 four byte word
#
# 12 hours = 12 hours * 60 minutes * 60 seconds = 43200 seconds
#     43200 / 16777216 = 0   remainder 43200
#     43200 / 65536    = 0   remainder 43200
#     43200 / 256      = 168 remainder 192
#     192   / 1        = 192 remainder zero
# 12 hours lease = 0, 0, 168, 192 four byte word
#

##############################################################################

#
# imports
#

import socket
import sys

##############################################################################

#
# constants
#

OPT_DHCP_MESSAGE_TYPE = 53

##############################################################################

def showpacket(bytes):
    bpr = 32              # bpr is Bytes Per Row
    numbytes = len(bytes)

    if numbytes == 0:
        print("<empty packet>")
    else:
        i = 0
        while i < numbytes:
            if (i % bpr) == 0:
                print("{:04d} :".format(i), sep='', end='')

            print(" {:02X}".format(bytes[i]), sep='', end='')

            if ((i + 1) % bpr) == 0:
                print()

            i = i + 1

    if (numbytes % bpr) != 0:
        print()

##############################################################################

def readablebytes(bytes):
    numbytes = len(bytes)

    if numbytes == 0:
        readable = "0xNull"
    else:
        readable = "0x"
        i = 0
        while i < numbytes:
            readable += "{:02X}".format(bytes[i])
            i += 1

    return readable

##############################################################################

def readablemacaddress(bytes):
    numbytes = len(bytes)

    if numbytes != 6:
        readable = "<invalid MAC>"
    else:
        readable = ""
        i = 0
        while i < 6:
            if i > 0:
                readable += ":"
            readable += "{:02X}".format(bytes[i])
            i += 1

    return readable            

##############################################################################

def showoptions(bytes):
    numbytes = len(bytes)

    i = 0
    while i < numbytes:
        option = bytes[i]
        if option == 0:
            print("PAD")
            i += 1
            continue

        if option == 255:
            print("END")
            break

        i += 1
        if i >= numbytes:
            print("Option:", option, "- premature EOF when expecting length byte")
            break

        optlen = bytes[i]
        i += 1

        if (i + optlen) >= numbytes:
            print("Option:", option, "with length", optlen, "- premature EOF when expecting option data")
            break

        optdata = bytes[i:i+optlen]
        print("Option:", option, "Length:", optlen, "Value:", readablebytes(optdata))

        i += optlen        

##############################################################################

def ip2bytearray(ipaddress):
    ba = bytearray(4)

    octets = ipaddress.split('.')

    if len(octets) < 4:
        return "Not enough octets in IP address", ba

    if len(octets) > 4:
        return "Too many octets in IP address", ba

    i = 0
    while i < 4:
        o = octets[i]

        if len(o) == 0:
            return "Badly formed IP address", ba

        if not o.isdigit():
            return "Octet in IP address is not all numbers", ba

        if int(o) < 0:
            return "Octet out of range (possibly negeative)", ba

        if int(o) > 255:
            return "Octet out of range (more than 255)", ba

        ba[i] = int(o)

        i += 1

    return "OK", ba

##############################################################################

def buildipaddr(ip1, ip2, ip3, ip4):
    ipaddr = bytearray(4)

    ipaddr[0] = ip1
    ipaddr[1] = ip2
    ipaddr[2] = ip3
    ipaddr[3] = ip4

    return ipaddr

##############################################################################

def cookieconstant():
    return buildipaddr(99, 130, 83, 99)

##############################################################################

def buildbyteoption(optnum, ba):
    lenba = len(ba)

    if (ba) == 0:
        opt = bytearray(1)
        opt[0] = optnum
    else:
        opt = bytearray(2 + lenba)
        opt[0] = optnum
        opt[1] = lenba
        opt[2:2+lenba] = ba

    return opt

##############################################################################

def build1byteoption(optnum, databyte):
    optbytes = bytearray(3)
    optbytes[0] = optnum
    optbytes[1] = 1
    optbytes[2] = databyte

    return optbytes

##############################################################################

def build4byteoption(optnum, d1, d2, d3, d4):
    optbytes = bytearray(6)
    optbytes[0] = optnum
    optbytes[1] = 4
    optbytes[2] = d1
    optbytes[3] = d2
    optbytes[4] = d3
    optbytes[5] = d4

    return optbytes

##############################################################################

def buildendoption():
    optbytes = bytearray(1)
    optbytes[0] = 255

    return optbytes

##############################################################################

#
# Main code
#

# extract program name
progname = sys.argv[0]

# print program name
### print("Python program \"", progname, "\" starting", sep='')

# extract number of arguments (ignoring program name)
numargs = len(sys.argv) - 1
### print("numargs =", numargs)

# if an odd number of arguments then something wrong
if (numargs % 2) != 0:
    print(progname, ": odd number of command line arguments", sep='')
    exit()

# set program defaults
macaddr = ""
ipbind = ""
ipaddr = ""
subnet = ""
gateway = ""

### ipbind = "192.168.2.53"
### ipaddr = "192.168.2.100"
### subnet = "255.255.255.0"
### gateway = "192.168.2.254"

# loop through command line args
arg = 1
while arg < numargs:
    if sys.argv[arg] == "-m":
        macaddr = (sys.argv[arg+1]).upper()
    elif sys.argv[arg] == "-b":
        ipbind = sys.argv[arg+1]
    elif sys.argv[arg] == "-i":
        ipaddr = sys.argv[arg+1]
    elif sys.argv[arg] == "-s":
        subnet = sys.argv[arg+1]
    elif sys.argv[arg] == "-g":
        gateway = sys.argv[arg+1]
    else:
        print(progname, ": unrecognised command line argument \"", sys.argv[arg], "\"", sep='')
        exit()
    arg = arg + 2

# ensure macaddr was set
if macaddr == "":
    print(progname, ": MAC address not specified with -m command line option", sep='')
    exit()

# ensure IP bind address was set
if ipbind == "":
    print(progname, ": interface IP address to bind to not specified with -b command line option", sep='')
    exit()

# check for good bind to IP addreress
errmsg, baipbind = ip2bytearray(ipbind)
if errmsg != "OK":
    print(progname, ": ", errmsg, ": bad IP address for -b option", sep='')
    exit()

# check for good ip addreress
errmsg, baipaddr = ip2bytearray(ipaddr)
if errmsg != "OK":
    print(progname, ": ", errmsg, ": bad IP address for -i option", sep='')
    exit()

# check foir good subnet
errmsg, basubnet = ip2bytearray(subnet)
if errmsg != "OK":
    print(progname, ": ", errmsg, ": bad subnet mask for -s option", sep='')
    exit()

# check for good gateway
errmsg, bagateway = ip2bytearray(gateway)
if errmsg != "OK":
    print(progname, ": ", errmsg, ": bad gateway address for -g option", sep='')
    exit()

# print program globals
print("===============================================================================")
print("MAC address...: ", macaddr, sep='')
print("IP address....: ", ipaddr, " (", readablebytes(baipaddr), ")", sep='')
print("Bind address..: ", ipbind, " (", readablebytes(baipbind), ")", sep='')
print("Subnet mask...: ", subnet, " (", readablebytes(basubnet), ")", sep='')
print("Gateway.......: ", gateway," (", readablebytes(bagateway), ")",  sep='')
print("===============================================================================")

# create a TCP/IP socket for receiving DHCP packets on port 67
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# bind the socket to the port
server_address = (ipbind, 67)
### print("receive starting up on ", server_address)
sock.bind(server_address)

# main loop for DHCP server
while True:
    # Wait for a connection
    print("")
    print("waiting for a connection")
    packet, address = sock.recvfrom(32768)

    # get and report packet length
    lenpacket = len(packet)
    print("received a packet of length", lenpacket, "from address", address[0], "on port", address[1])
    
    # zero length packets don't work
    if lenpacket == 0:
        print("invalid packet - no bytes in packet")
        continue

    # display the incoming packet
    showpacket(packet)

    # packets < 241 bytes don't work either
    if lenpacket < 241:
        print("invalid packet - less than 241 bytes in packet")
        continue

    # extract op (operation code)
    op = packet[0]
    print("Op:", op)
    if (op != 1) and (op != 2):
        print("invalid packet - Op field not 1 (request) or 2 (reply)")
        continue

    # extract hardware type
    hardwaretype = packet[1]
    print("Hardware type:", hardwaretype)
    if hardwaretype != 1:
        print("ignoring packet - only hardware type 1 \"Ethernet (10 Mb)\" currently supported")
        continue

    # extract hardware addreess length
    lenhardwareaddress = packet[2]
    print("Hardware address length:", lenhardwareaddress)
    if lenhardwareaddress != 6:
        print("ignoring packet - only hardware address lengths of 6 bytes currently supported")
        continue

    # extract hops, transaction identfier, seconds and flags
    hops = packet[3]
    print("Hops:", hops)
    transactionid = packet[4:8]
    print("Transaction ID:", readablebytes(transactionid))
    seconds = packet[8:10]
    print("Seconds:", readablebytes(seconds))
    flags = packet[10:12]
    print("Flags:", readablebytes(flags))

    # extract addresses
    ciaddr = packet[12:16]
    yiaddr = packet[16:20]
    siaddr = packet[20:24]
    giaddr = packet[24:28]

    # extract MAC address
    thismacaddr = packet[28:34]
    print("MAC address:", readablemacaddress(thismacaddr))
    if readablemacaddress(thismacaddr) != macaddr:
        print("ignoring packet - MAC address does not match", macaddr, "from the command line")
        continue

    # extract cookie
    cookie = packet[236:240]
    print("Cookie:", readablebytes(cookie))
    if readablebytes(cookie) != "0x63825363":
        print("ignoring packet - options field does not begin with Magic Cookie 0x63825363")
        continue

    # option data

    # process options
    print("Processing options data")
    optiondata = packet[240:]
    numoptbytes = len(optiondata)
    opts = {}

    i = 0
    while i < numoptbytes:
        option = optiondata[i]
        if option == 0:
            print("PAD at index", i)
            i += 1
            continue

        if option == 255:
            break

        i += 1
        if i >= numoptbytes:
            print(progname, ": warning: option: ", option, " - premature EOF when expecting length byte", sep='')
            break

        optlen = optiondata[i]
        i += 1

        if (i + optlen) >= numoptbytes:
            print(progname, ": warning: option:", option, "with length", optlen, " - premature EOF when expecting option data", sep='')
            break

        optdata = optiondata[i:i+optlen]
        print("Option:", option, "Length:", optlen, "Value:", readablebytes(optdata))

        opts[option] = optdata

        i += optlen        

    ### print(opts)

    # see if there is a DHCP message type option
    if OPT_DHCP_MESSAGE_TYPE not in opts:
        print(progname, ": ignoring: packet does not have a DHCP Message Type option (code ", OPT_DHCP_MESSAGE_TYPE, ")", sep='')
        continue

    messagetype = opts[OPT_DHCP_MESSAGE_TYPE]
    if len(messagetype) != 1:
        print(progname, ": ignoring: packet DHCP Message Type is not a single byte", sep='')
        continue

    print("DHCP Message Type is:", messagetype)

    if (messagetype != b'\x01') and (messagetype != b'\x03'):
        print(progname, ": ignoring: DHCP message type not supported by this implementation", sep='')
        continue

    print("building response")
    offer = bytearray(240)

    # standard stuff
    offer[0]       = 2
    offer[1]       = 1
    offer[2]       = 6
    offer[3]       = 0
    offer[4:8]     = transactionid
    offer[10:12]   = flags

    # assigned IP
    offer[16:20] = baipaddr

    # next server IP
    offer[20:24] = baipbind

    # put the MAC address in
    offer[28:34] = thismacaddr

    # insert DHCP cookie
    offer[236:240] = cookieconstant()

    # add options
    if messagetype == b'\01':
        responsename = "DHCPOFFER"
        offer += build1byteoption(53, 2)             # DHCPOFFER

    if messagetype == b'\03':
        responsename = "DHCPACK"
        offer += build1byteoption(53, 5)             # DHCPACK

    offer += buildbyteoption(1, basubnet)            # Subnet mask
    offer += buildbyteoption(3, bagateway)           # Gateway
    offer += build4byteoption(51, 0, 1, 81, 128)     # Lease time (24 hours)
    offer += buildbyteoption(54, baipbind)           # Server Identfier
        
    # terminate options
    offer += buildendoption()        

    # show the packet
    showpacket(offer)

    # send it
    print("sending", responsename, "packet")
    sendsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sendsock.bind(('', 0))
    sendsock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    send_server_address = ('255.255.255.255', 68)
    sent = sendsock.sendto(offer, send_server_address)
    sendsock.close()
    print("sent", sent, "bytes")
   	
exit()

# end of file
