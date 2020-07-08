from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import udp
from ryu.lib.packet import tcp
from ryu.lib.packet import icmp


class TrafficSlicing(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TrafficSlicing, self).__init__(*args, **kwargs)
    
        # out_port = slice_to_port[dpid][in_port]
        # dpid corresponds to the destination switch
        self.slice_to_port = {
            1: {1: 2, 2: 1, 3: 4, 4: 3},
            #6: {1: 4, 2: 4, 3: 4},
            #9: {1: 4, 2: 4, 3: 4}
            #2: {2: 1, 3: 1}
            #4: {1: 3, 2: 3}
        }

        # outport = self.mac_to_port[dpid][mac_address]
        self.mac_to_port = {
            #1: {"00:00:00:00:00:01": 3, "00:00:00:00:00:04": 3, "00:00:00:00:00:05": 4},
            2: {"00:00:00:00:00:04": 1, "00:00:00:00:00:03": 4},
            5: {"00:00:00:00:00:02": 3},
            6: {"00:00:00:00:00:04": 4},
            9: {"00:00:00:00:00:05": 4}
        }
        self.slice_FTPdata = 20
        self.slice_RDPdata = 3389
        self.slice_IMAPdata = 993

        # outport = self.slice_ports[dpid][slicenumber]
        self.slice_ports = {2: {1: 3, 2: 2}, 5: {1: 2, 2: 1}, 6: {2: 3, 3: 2, 4: 1}, 9: {2: 3, 4: 1, 3: 2}}
        self.end_swtiches = [2, 5, 6, 9]
        # TODO: Accesso alla DMZ dal backend alla porta 3389 (rdp) su tcp e udp e 993 (IMAP)
        
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install the table-miss flow entry.
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # construct flow_mod message and send it.
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath, priority=priority, match=match, instructions=inst
        )
        datapath.send_msg(mod)

    def _send_package(self, msg, datapath, in_port, actions):
        data = None
        ofproto = datapath.ofproto
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
        dst = eth.dst
        src = eth.src
        ip=pkt.protocols[1]
        ip_dst=ip.dst
        ip_src=ip.src

        dpid = datapath.id

        if dpid in self.slice_to_port and in_port in self.slice_to_port[dpid]:
            out_port = self.slice_to_port[dpid][in_port]
            actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
            match = datapath.ofproto_parser.OFPMatch(in_port=in_port)
            self.add_flow(datapath, 1, match, actions)
            self._send_package(msg, datapath, in_port, actions)
        elif dpid in self.mac_to_port:
            if dst in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][dst]
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                match = datapath.ofproto_parser.OFPMatch(eth_dst=dst)
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            elif (pkt.get_protocol(tcp.tcp) and pkt.get_protocol(tcp.tcp).dst_port == self.slice_FTPdata):
                slice_number = 1
                #print("DPID:", dpid)
                #print("Slice:", slice_number)
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x06,  # tcp
                    tcp_dst=self.slice_FTPdata,
                    #https://ryu.readthedocs.io/en/latest/library_packet_ref/packet_tcp.html
                )

                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 2, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            elif (pkt.get_protocol(tcp.tcp) and (pkt.get_protocol(tcp.tcp).dst_port == self.slice_RDPdata or pkt.get_protocol(tcp.tcp).src_port == self.slice_RDPdata)):
                slice_number = 3
                #print("DPID:", dpid)
                #print("Slice:", slice_number)
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x06,  # tcp
                    tcp_dst=self.slice_FTPdata,
                )
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)
            
            elif (pkt.get_protocol(udp.udp) and pkt.get_protocol(udp.udp).dst_port == self.slice_RDPdata):
                slice_number = 3
                #print("DPID:", dpid)
                #print("Slice:", slice_number)
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x11,  # udp
                    tcp_dst=self.slice_RDPdata, #This is wrong
                    #https://ryu.readthedocs.io/en/latest/library_packet_ref/packet_tcp.html
                )

                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 2, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            elif (pkt.get_protocol(tcp.tcp) and (pkt.get_protocol(tcp.tcp).dst_port == self.slice_IMAPdata or pkt.get_protocol(tcp.tcp).src_port == self.slice_IMAPdata)):
                slice_number = 4
                #print("DPID:", dpid)
                #print("Slice:", slice_number)
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x06,  # tcp
                    tcp_dst=self.slice_IMAPdata,
                )
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            #TODO: complete RDP also for UDP

            elif (pkt.get_protocol(tcp.tcp) and pkt.get_protocol(tcp.tcp).dst_port != self.slice_FTPdata and pkt.get_protocol(tcp.tcp).dst_port != self.slice_RDPdata):
                slice_number = 2
                #print("DPID:", dpid)
                #print("Slice:", slice_number)
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x06,  # tcp
                    tcp_dst=pkt.get_protocol(tcp.tcp).dst_port,
                )
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            elif pkt.get_protocol(udp.udp):
                slice_number = 2
                #print("DPID:", dpid)
                #print("Slice:", slice_number)
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x11,  # udp
                    udp_dst=pkt.get_protocol(udp.udp).dst_port,
                )
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            elif pkt.get_protocol(icmp.icmp):
                #print("DPID:", dpid)
                #print("Slice:", slice_number)
                slice_number = 2
                #if ip_dst == "10.0.0.4" or ip_src == "10.0.0.4":
                #    slice_number = 3
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x01,  # icmp
                )
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

        elif dpid not in self.end_swtiches:
            out_port = ofproto.OFPP_FLOOD
            actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
            match = datapath.ofproto_parser.OFPMatch(in_port=in_port)
            self.add_flow(datapath, 1, match, actions)
            self._send_package(msg, datapath, in_port, actions)
