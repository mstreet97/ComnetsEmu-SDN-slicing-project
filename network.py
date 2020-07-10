#!/usr/bin/python3

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController
from mininet.cli import CLI
from mininet.link import TCLink


class NetworkSlicingTopo(Topo):
    def __init__(self):
        # Initialize topology
        Topo.__init__(self)

        # Create template host, switch, and link
        host_config = dict(inNamespace=True)
        http_link_config = dict(bw=5) #general traffic slice
        rdp_link_config = dict(bw=10) #rdp traffic slice
        ftp_link_config = dict(bw=15) #ftp traffic slice
        host_link_config = dict()

        # Create 9 switch nodes
        for i in range(9):
            sconfig = {"dpid": "%016x" % (i + 1)}
            self.addSwitch("s%d" % (i + 1), **sconfig)

        # Create 5 host nodes
        for i in range(5):
            self.addHost("h%d" % (i + 1), **host_config)

        # Add switch links
        self.addLink("s1", "s2", **http_link_config)
        self.addLink("s2", "s3", **http_link_config)
        self.addLink("s2", "s4", **ftp_link_config)
        self.addLink("s3", "s5", **http_link_config)
        self.addLink("s4", "s5", **ftp_link_config)
        self.addLink("s6", "s7", **http_link_config)
        self.addLink("s6", "s8", **rdp_link_config)
        self.addLink("s1", "s6", **http_link_config)
        self.addLink("s9", "s7", **http_link_config)
        self.addLink("s9", "s8", **rdp_link_config)
        self.addLink("s1", "s9", **http_link_config)

        # Add host links
        self.addLink("h1", "s1", **host_link_config)
        self.addLink("h2", "s5", **host_link_config)
        self.addLink("h3", "s2", **host_link_config)
        self.addLink("h4", "s6", **host_link_config)
        self.addLink("h5", "s9", **host_link_config)

topos = {"networkslicingtopo": (lambda: NetworkSlicingTopo())}

if __name__ == "__main__":
    topo = NetworkSlicingTopo()
    net = Mininet(
        topo=topo,
        switch=OVSKernelSwitch,
        build=False,
        autoSetMacs=True,
        autoStaticArp=True,
        link=TCLink,
    )
    controller = RemoteController("c1", ip="127.0.0.1", port=6633)
    net.addController(controller)
    net.build()
    net.start()
    CLI(net)
    net.stop()
