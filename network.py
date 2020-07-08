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
        http_link_config = dict(bw=5)
        rdp_link_config = dict(bw=10)
        ftp_link_config = dict(bw=15)
        #full_bw_config = dict(bw=25)
        host_link_config = dict()

        # Create switch nodes
        for i in range(9):
            sconfig = {"dpid": "%016x" % (i + 1)}
            self.addSwitch("s%d" % (i + 1), **sconfig)

        # Create host nodes
        for i in range(5):
            self.addHost("h%d" % (i + 1), **host_config)

        # Tre switch (6/7/8) per dare connettivita' ai server nella dmz via imap e rdp, slicing con ip su h4, in modo che si fermi a quello
        # In alternativa, unificare h5 e h6 e fare in modo che il traffico da h4 ad h5 passi solo se rdp o imap
        # Qualcosa per dare egress (quindi porte 80/443) alla intranet

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
        #self.addLink("h4", "s1", **host_link_config)
        self.addLink("h4", "s6", **host_link_config)
        #self.addLink("h5", "s1", **host_link_config)
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
